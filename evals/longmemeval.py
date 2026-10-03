"""Run a memory strategy headless on LongMemEval, under ADRs 0004–0009, 0011 and 0013–0017.

Each question's history is replayed into a fresh strategy (0004), recalled at
23:59 on the question's day, answered by the model from what came back, and
graded (0008). Per question it logs recall and precision (0009), the distance
from the newest evidence to the question (0005), the tokens recalled against
the budget (0007), and what every model call cost (0006), each call priced at
its own model (0015). For RetrievalMemory it also logs recall with only the
user turns written (0011); for ConsolidatingMemory, how much of the evidence
the consolidator read (0013). The agent is never in the path: no
ConversationAgent, no prompts.py.

The questions and their order come from evals/longmemeval_questions.json
(0005); the replay rules come from verify_adr_numbers.py. Rows go to
data/longmemeval/runs/ as JSON lines, one per question, in list order.

    .venv/bin/python evals/longmemeval.py --dry-run         # no model calls, no key needed
    .venv/bin/python evals/longmemeval.py                   # the M1 pilot, 10 per type; costs money
    .venv/bin/python evals/longmemeval.py --per-type 30
    .venv/bin/python evals/longmemeval.py --strategy retrieval --dry-run
    .venv/bin/python evals/longmemeval.py --strategy consolidating --per-type 61 --workers 4

--dry-run runs everything except the network. The answer call's prompt, and so
its input tokens, is exactly what a real run sends; the answers and verdicts
are placeholders, and no accuracy is reported. A consolidating strategy gets a
placeholder summary of about S tokens, so its recall is close to the real run's
(0013).

--workers runs that many questions at once. Each question has its own call log
and its own strategy, so the rows are the same whatever the number; only the
order calls hit the provider changes.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.longmemeval_grading import grading_prompt  # noqa: E402
from evals.verify_adr_numbers import (  # noqa: E402
    DATASET_SHA256, KU, PILOT_PER_TYPE, ROOT, SSU, TYPES, TiktokenCounter, build_records,
    evidence_sessions, load_pinned, question_time, replay_order,
)
from life_agent.agent.memory import (  # noqa: E402
    DEFAULT_BUDGET_TOKENS, SUMMARY_TARGET_TOKENS, ApproxTokenCounter, ConsolidatingMemory,
    ConsolidationError, Consolidator, ConversationMemory, MemoryRecord, RecentTurnsMemory,
    Retrieval, RetrievalMemory, TokenCounter, make_record_id,
)
from life_agent.agent.recording import LLMCall, RecordingLLMClient  # noqa: E402
from life_agent.config import get_settings  # noqa: E402
from life_agent.llm.client import LLMClient, _extract_json  # noqa: E402

QUESTIONS = ROOT / "evals" / "longmemeval_questions.json"
RUNS = ROOT / "data" / "longmemeval" / "runs"
MODEL = "openai/gpt-4o-2024-08-06"  # ADR 0008: the dated id, never an alias
CONSOLIDATOR_MODEL = "openai/gpt-4o-mini-2024-07-18"  # ADR 0015, as 0010 assumed
ATTEMPTS = 3                        # ADR 0008: a call that returns None is tried twice more
# Prices in USD per million tokens, by model. External: OpenRouter, 2026-09-26
# (0008) and 2026-10-03 (0015). PRICE_IN/PRICE_OUT stay as the answering
# model's for the scripts that import them.
PRICES = {MODEL: (2.50, 10.00), CONSOLIDATOR_MODEL: (0.15, 0.60)}
PRICE_IN, PRICE_OUT = PRICES[MODEL]
# ADR 0006: the calls that count as a strategy's cost. "grade" never does, and
# neither does the list-order replay's consolidation (0009, 0015).
STRATEGY_LABELS = ("answer", "consolidate")
LIST_ORDER_LABEL = "consolidate-list-order"

# ADR 0008, copied from the record's code blocks, line breaks included.
ANSWER_SYSTEM_PROMPT = (
    "Below is your earlier conversation with the user. Answer the user's last\n"
    "question using only that conversation. If it does not contain the answer, say\n"
    'that you do not know. Reply with a JSON object: {"answer": "<your answer>"}.'
)
GRADE_SYSTEM_PROMPT = 'Reply with a JSON object: {"verdict": "yes"} or {"verdict": "no"}.'

# Each strategy is built fresh per replay, with the harness's counter and a
# consolidator client the two that make no model call ignore.
Factory = Callable[[TokenCounter, Consolidator], ConversationMemory]
STRATEGIES: dict[str, Factory] = {
    # ADR 0007: no turn window; the budget is the only limit.
    "recent-turns": lambda counter, _: RecentTurnsMemory(max_turns=None, token_counter=counter),
    # ADR 0011: BM25 over every record, built with the counter and nothing else.
    "retrieval": lambda counter, _: RetrievalMemory(token_counter=counter),
    # ADR 0015: a rolling summary from the consolidator, over a recent window.
    "consolidating": lambda counter, llm: ConsolidatingMemory(llm, token_counter=counter),
}
# ADR 0011: the strategies whose recall is also computed with only user turns written.
USER_TURN_RECALL = ("retrieval",)
# ADR 0009: the strategies that call a model while replaying. Their list-order
# replay is made on the knowledge-update pilot questions only.
MODEL_CALL_STRATEGIES = ("consolidating",)


class DryRunClient:
    """Stands in for the model under --dry-run: every call returns *reply*."""

    def __init__(self, reply: dict) -> None:
        self._reply = reply

    def chat_json(self, system_prompt: str, messages: list[dict[str, str]]) -> dict:
        return dict(self._reply)


def dry_run_summary(counter: TokenCounter) -> str:
    """A placeholder of at most S tokens: the window is about the real run's size (0013),
    and the dry run neither asks again nor cuts (0015)."""
    piece, text = "(dry run) notes. ", ""
    while counter.count(text + piece) <= SUMMARY_TARGET_TOKENS:
        text += piece
    return text


# -- setup -------------------------------------------------------------------

def require_real_counter(counter: TokenCounter) -> None:
    """ADR 0003: a published count never comes from the four-character estimate."""
    if isinstance(counter, ApproxTokenCounter):
        raise TypeError("ApproxTokenCounter is an estimate; the harness counts with o200k_base (ADR 0003, 0006)")


def load_questions(per_type: int) -> dict[str, list[str]]:
    """The whole ordered list of each type. A run takes the first *per_type*."""
    doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if doc["dataset_sha256"] != DATASET_SHA256:
        raise SystemExit(f"{QUESTIONS.name} was drawn from another file than the one ADR 0004 pins")
    cap = min(len(doc[t]) for t in TYPES)
    if not 1 <= per_type <= cap:
        raise SystemExit(f"--per-type must be 1 to {cap}: every type gets the same N")
    return {t: doc[t] for t in TYPES}


FAILURES = RUNS / "failures.log"


class DiagnosedClient:
    """``chat_json`` with the same contract as ``LLMClient``'s, plus a line per failure.

    ``LLMClient.chat_json`` returns None for a network error, a provider error
    and an unparseable reply alike (0008). A rerun under 0008 needs to know
    which, so every failure is appended to data/longmemeval/runs/failures.log
    with the model, the exception or the raw text, and the first line of the
    message that provoked it. The call itself is unchanged.
    """

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.model = inner.model

    def chat_json(self, system_prompt: str, messages: list[dict[str, str]]) -> dict | None:
        raw: str | None = None
        try:
            raw = self._inner._chat_completion_messages(system_prompt, messages, json_mode=True)
            result = _extract_json(raw)
        except Exception as e:  # noqa: BLE001 — the client's own contract swallows everything
            result, raw = None, f"{type(e).__name__}: {str(e)[:500]}"
            body = getattr(e, "read", None)
            if callable(body):
                try:
                    raw += " " + body().decode("utf-8", "replace")[:800]
                except Exception:  # noqa: BLE001
                    pass
        if result is None:
            head = (messages[-1]["content"] if messages else "")[:120].replace("\n", " ")
            with FAILURES.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "model": self.model,
                                    "input_head": head, "raw": raw}, ensure_ascii=False) + "\n")
        return result


def real_client(model: str = MODEL) -> DiagnosedClient:
    s = get_settings()
    client = LLMClient(api_key=s.llm_api_key, base_url=s.llm_base_url, model=model,
                       provider=s.llm_provider, timeout=60.0)
    if not client.enabled:
        raise SystemExit("no model configured: set LIFE_AGENT_LLM_BASE_URL and _API_KEY, or use --dry-run")
    if "openrouter.ai" not in (client.base_url or ""):
        raise SystemExit(f"ADR 0008 answers and grades through OpenRouter, not {client.base_url}")
    return DiagnosedClient(client)


def git_commit() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return git("rev-parse", "--short", "HEAD") + ("+dirty" if git("status", "--porcelain") else "")


# -- replay and recall -------------------------------------------------------

def replay(memory: ConversationMemory, records: list[MemoryRecord], ends: set[int],
           roles: tuple[str, ...] | None = None) -> None:
    """Write every record; end the session after each session's last one (ADR 0004).

    With *roles*, only records of those roles are written (ADR 0011's secondary
    figure). The session boundaries stay where they were.
    """
    for k, record in enumerate(records, start=1):
        if roles is None or record.role in roles:
            memory.write(record)
        if k in ends:
            memory.end_session()


def recall_of(x: dict, order: str, build: Callable[[TokenCounter], ConversationMemory],
              counter: TokenCounter, roles: tuple[str, ...] | None = None,
              ) -> tuple[Retrieval, set[str], list[MemoryRecord], ConversationMemory]:
    records, ends, evidence = build_records(x, order)
    if len({r.id for r in records}) != len(records):
        raise ValueError(f"{x['question_id']}: two records share an id (ADR 0004)")
    memory = build(counter)
    replay(memory, records, ends, roles)
    retrieval = memory.retrieve(x["question"], at=question_time(x), budget_tokens=DEFAULT_BUDGET_TOKENS)
    # The budget counts the content of what came back and nothing else (ADR 0006).
    # A strategy that fell back on its own default counter shows up here.
    recount = sum(counter.count(m["content"]) for m in retrieval.messages)
    if retrieval.tokens_used != recount:
        raise ValueError(f"{x['question_id']}: tokens_used is {retrieval.tokens_used} but the messages "
                         f"hold {recount} tokens; the strategy is not counting with o200k_base")
    return retrieval, evidence, records, memory


def summaries_shown(memory: ConversationMemory, sources: tuple[str, ...]) -> list[MemoryRecord]:
    """The summary records among *sources*, read from the strategy's own store (ADR 0013)."""
    got = set(sources)
    return [r for r in getattr(memory, "records", []) if r.kind == "summary" and r.id in got]


def consolidated(memory: ConversationMemory, sources: tuple[str, ...]) -> set[str]:
    """ADR 0013's C: every id a summary in the context derives from."""
    return {rid for s in summaries_shown(memory, sources) for rid in s.derived_from}


def recall_precision(sources: tuple[str, ...], evidence: set[str]) -> tuple[float, float]:
    """ADR 0009, for one question."""
    got = set(sources)
    hit = len(got & evidence)
    return hit / len(evidence), (hit / len(got) if got else 0.0)


def ku_breakdown(x: dict, sources: tuple[str, ...] | set[str]) -> str | None:
    """ADR 0009: which of the two evidence sessions, in replay order, reached the context."""
    ev = evidence_sessions(x)
    if len(ev) != 2:
        return None
    order = replay_order(x, "clock")
    got = set(sources)

    def reached(i: int) -> bool:
        sid = x["haystack_session_ids"][i]
        return any(make_record_id(sid, j) in got
                   for j, t in enumerate(x["haystack_sessions"][i]) if t.get("has_answer"))

    earlier, later = sorted(ev, key=order.index)
    return {(False, False): "neither", (True, False): "earlier",
            (False, True): "later", (True, True): "both"}[(reached(earlier), reached(later))]


def distance_tokens(records: list[MemoryRecord], evidence: set[str], counter: TokenCounter) -> int:
    """ADR 0005: tokens of conversation between the newest evidence turn and the question."""
    newest = max(i for i, r in enumerate(records) if r.id in evidence)
    return sum(counter.count(r.content) for r in records[newest + 1:])


# -- one question ------------------------------------------------------------

def answer_messages(x: dict, retrieval: Retrieval) -> list[dict[str, str]]:
    """ADR 0008: the recalled messages unchanged, then the question with its date."""
    question = {"role": "user", "content": f"Current date: {x['question_date']}\nQuestion: {x['question']}"}
    return [*retrieval.messages, question]


def ask(client: RecordingLLMClient, system_prompt: str,
        messages: list[dict[str, str]]) -> tuple[dict | None, int]:
    for attempt in range(1, ATTEMPTS + 1):
        reply = client.chat_json(system_prompt, messages)
        if reply is not None:
            return reply, attempt
    return None, ATTEMPTS


def tokens_by_label(calls: list[LLMCall], label: str) -> tuple[int, int]:
    paid = [c for c in calls if c.label == label and not c.failed]
    return sum(c.input_tokens for c in paid), sum(c.output_tokens for c in paid)


def run_question(x: dict, position: int, name: str, counter: TokenCounter,
                 inner: dict[str, object], models: dict[str, str | None], meta: dict) -> dict:
    """One question, with its own call log, so questions can run side by side."""
    log: list[LLMCall] = []

    def recording(key: str, label: str) -> RecordingLLMClient:
        return RecordingLLMClient(inner[key], label=label, counter=counter, log=log, model=models[key])

    answer_llm = recording("answer", "answer")
    grade_llm = recording("grade", "grade")
    factory = STRATEGIES[name]
    # ADR 0015: the clock-order replay's consolidation is the strategy's cost;
    # the list-order replay's is logged apart and is not.
    build = lambda c: factory(c, recording("consolidate", "consolidate"))  # noqa: E731
    build_list = lambda c: factory(c, recording("consolidate", LIST_ORDER_LABEL))  # noqa: E731

    row = {
        **meta,
        "question_id": x["question_id"],
        "question_type": x["question_type"],
        "position": position,
        "question": x["question"],
        "question_date": x["question_date"],
        "gold_answer": str(x["answer"]),
    }
    recall_fields = ("evidence", "sources", "tokens_used", "over_budget", "recall", "precision",
                     "evidence_reached", "ku_breakdown", "recall_list_order", "evidence_reached_list_order",
                     "recall_user_turns", "evidence_reached_user_turns", "evidence_consolidated",
                     "evidence_consolidated_or_reached", "ku_breakdown_consolidated", "summary_tokens",
                     "summary", "summary_reasked", "summary_truncated", "consolidations", "consolidations_failed",
                     "distance_tokens", "long_term", "history_tokens", "records")
    row.update(dict.fromkeys(recall_fields))
    row.update(answer_attempts=0, answer=None, answer_is_string=None, verdict=None, correct=None,
               grade_attempts=0, status="error", error=None, list_order_error=None)

    try:
        retrieval, evidence, records, memory = recall_of(x, "clock", build, counter)
        recall, precision = recall_precision(retrieval.sources, evidence)
        distance = distance_tokens(records, evidence, counter)
        row.update({
            "evidence": sorted(evidence),
            "sources": list(retrieval.sources),
            "tokens_used": retrieval.tokens_used,
            "over_budget": retrieval.tokens_used > DEFAULT_BUDGET_TOKENS,
            "recall": recall,
            "precision": precision,
            "evidence_reached": bool(set(retrieval.sources) & evidence),
            "distance_tokens": distance,
            "long_term": distance > DEFAULT_BUDGET_TOKENS,
            "history_tokens": sum(counter.count(r.content) for r in records),
            "records": len(records),
        })
        # ADR 0009: only knowledge-update questions differ between the two orders.
        # ADR 0009, 0015: a strategy that calls a model while replaying is replayed
        # in list order on the pilot questions only.
        if x["question_type"] == KU:
            row["ku_breakdown"] = ku_breakdown(x, retrieval.sources)
            if name not in MODEL_CALL_STRATEGIES or position < PILOT_PER_TYPE:
                # A secondary figure: its consolidation failing leaves it None and
                # does not void the question.
                try:
                    listed, listed_evidence, _, _ = recall_of(x, "list", build_list, counter)
                except ConsolidationError as e:
                    row["list_order_error"] = str(e)
                else:
                    row["recall_list_order"] = recall_precision(listed.sources, listed_evidence)[0]
                    row["evidence_reached_list_order"] = bool(set(listed.sources) & listed_evidence)
        # ADR 0011: only for a strategy that ranks; E stays as the dataset marks it.
        if name in USER_TURN_RECALL:
            users, _, _, _ = recall_of(x, "clock", build, counter, roles=("user",))
            row["recall_user_turns"] = recall_precision(users.sources, evidence)[0]
            row["evidence_reached_user_turns"] = bool(set(users.sources) & evidence)
        # ADR 0015, 0016: how often the size had to be held, and how many sessions
        # the consolidator could not summarise. Only a strategy that consolidates has them.
        done = getattr(memory, "consolidations", None)
        if done is not None:
            row["consolidations"] = len(done)
            row["summary_reasked"] = sum(c.reasked for c in done)
            row["summary_truncated"] = sum(c.truncated for c in done)
            row["consolidations_failed"] = sum(c.failed for c in done)
        # ADR 0013: only for a strategy that summarises; C from its own records.
        shown = summaries_shown(memory, retrieval.sources)
        if shown:
            c = consolidated(memory, retrieval.sources)
            both = c | set(retrieval.sources)
            row["evidence_consolidated"] = len(c & evidence) / len(evidence)
            row["evidence_consolidated_or_reached"] = bool(both & evidence)
            row["summary_tokens"] = sum(counter.count(s.content) for s in shown)
            row["summary"] = "\n\n".join(s.content for s in shown)  # the text the model saw (0015)
            if x["question_type"] == KU:
                row["ku_breakdown_consolidated"] = ku_breakdown(x, both)
    except ConsolidationError as e:
        # ADR 0015: the question is an error and is run again before any figure is reported.
        row["error"] = str(e)
        row["calls"] = [asdict(c) for c in log]
        return row

    reply, row["answer_attempts"] = ask(answer_llm, ANSWER_SYSTEM_PROMPT, answer_messages(x, retrieval))
    if reply is not None:
        # ADR 0008: a reply in the wrong shape is still an answer; the grader sees all of it.
        row["answer_is_string"] = isinstance(reply.get("answer"), str)
        row["answer"] = reply["answer"] if row["answer_is_string"] else json.dumps(reply, ensure_ascii=False)
        prompt = grading_prompt(x["question_type"], x["question"], str(x["answer"]), row["answer"])
        verdict, row["grade_attempts"] = ask(grade_llm, GRADE_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])
        if verdict is not None:
            row["verdict"] = verdict.get("verdict")
            row["correct"] = None if meta["dry_run"] else row["verdict"] == "yes"
            row["status"] = "ok"

    paid = [c for c in log if c.label in STRATEGY_LABELS and not c.failed]
    row["strategy_input_tokens"] = sum(c.input_tokens for c in paid)
    row["strategy_output_tokens"] = sum(c.output_tokens for c in paid)
    row["answer_input_tokens"], row["answer_output_tokens"] = tokens_by_label(log, "answer")
    row["consolidate_input_tokens"], row["consolidate_output_tokens"] = tokens_by_label(log, "consolidate")
    row["strategy_cost_usd"] = cost_of(paid)
    row["calls"] = [asdict(c) for c in log]
    return row


# -- summary -----------------------------------------------------------------

def usd(tokens_in: float, tokens_out: float, model: str = MODEL) -> float:
    price_in, price_out = PRICES[model]
    return (tokens_in * price_in + tokens_out * price_out) / 1e6


def cost_of(calls: list[LLMCall] | list[dict]) -> float:
    """Every call at its own model's price (ADR 0015). A call without a model is the answering model's."""
    total = 0.0
    for c in calls:
        c = asdict(c) if isinstance(c, LLMCall) else c
        total += usd(c["input_tokens"], c["output_tokens"], c.get("model") or MODEL)
    return total


def summarize(rows: list[dict], pool_distances: dict[str, list[int]], dry_run: bool) -> None:
    mean = statistics.fmean

    def of(rs: list[dict], key: str) -> list[dict]:
        return [r for r in rs if r[key] is not None]

    for t in TYPES:
        rs = [r for r in rows if r["question_type"] == t]
        if not rs:
            continue
        n, ok = len(rs), [r for r in rs if r["status"] == "ok"]
        measured = of(rs, "recall")  # a consolidation that failed has no recall to report
        pool = pool_distances[t]
        print(f"\n{t}: {n} questions (a pilot at this size: one question moves a share by {1 / n:.2f})")
        lines = [("errors (left out of accuracy)", f"{n - len(ok)}")]
        if dry_run:
            lines.append(("accuracy", "not measured (dry run)"))
        else:
            right = sum(r["correct"] for r in ok)
            lines.append(("accuracy", f"{right} of {len(ok)}" + (f" ({right / len(ok):.2f})" if ok else "")))
            lines.append(("verdict neither yes nor no", f"{sum(r['verdict'] not in ('yes', 'no') for r in ok)}"))
            lines.append(("answer not a string", f"{sum(not r['answer_is_string'] for r in ok)}"))
        if not measured:
            for label, value in lines:
                print(f"  {label:52s} {value}")
            continue
        m = len(measured)
        lines += [
            ("recall, mean", f"{mean(r['recall'] for r in measured):.3f}" + (f" (over {m})" if m != n else "")),
            ("precision, mean", f"{mean(r['precision'] for r in measured):.4f}"),
            ("evidence reached", f"{sum(r['evidence_reached'] for r in measured)} of {m}"),
        ]
        if t == KU:
            listed = of(measured, "recall_list_order")
            if listed:
                lines += [
                    ("recall, list order, mean", f"{mean(r['recall_list_order'] for r in listed):.3f}"
                     + (f" (over {len(listed)})" if len(listed) != m else "")),
                    ("evidence reached, list order",
                     f"{sum(r['evidence_reached_list_order'] for r in listed)} of {len(listed)}"),
                ]
        users = of(measured, "recall_user_turns")
        if users:
            lines += [
                ("recall, user turns only, mean", f"{mean(r['recall_user_turns'] for r in users):.3f}"),
                ("evidence reached, user turns only", f"{sum(r['evidence_reached_user_turns'] for r in users)} of {len(users)}"),
            ]
        summarised = of(measured, "evidence_consolidated")
        if summarised:
            lines += [
                ("evidence consolidated, mean (ADR 0013)", f"{mean(r['evidence_consolidated'] for r in summarised):.3f}"),
                ("evidence consolidated or reached",
                 f"{sum(r['evidence_consolidated_or_reached'] for r in summarised)} of {len(summarised)}"),
                ("summary tokens, mean / max", f"{mean(r['summary_tokens'] for r in summarised):,.0f} / "
                 f"{max(r['summary_tokens'] for r in summarised):,}"),
                ("consolidations asked again / cut / skipped / all (0015, 0016)",
                 f"{sum(r['summary_reasked'] for r in summarised)} / {sum(r['summary_truncated'] for r in summarised)}"
                 f" / {sum(r['consolidations_failed'] for r in summarised)} / {sum(r['consolidations'] for r in summarised)}"),
            ]
        lines += [
            ("messages recalled, mean / max", f"{mean(len(r['sources']) for r in measured):,.0f} / {max(len(r['sources']) for r in measured):,}"),
            ("tokens_used, mean / max", f"{mean(r['tokens_used'] for r in measured):,.0f} / {max(r['tokens_used'] for r in measured):,}"),
            ("over budget", f"{sum(r['over_budget'] for r in measured)}"),
            ("long-term, sample / whole list",
             f"{sum(r['long_term'] for r in measured)} of {m} / "
             f"{sum(d > DEFAULT_BUDGET_TOKENS for d in pool)} of {len(pool)}"),
            ("distance to evidence, median, sample / whole list",
             f"{statistics.median(r['distance_tokens'] for r in measured):,.0f} / {statistics.median(pool):,.0f}"),
            ("history tokens, mean", f"{mean(r['history_tokens'] for r in measured):,.0f}"),
        ]
        priced = [r for r in rs if "strategy_cost_usd" in r]
        if priced:
            note = " (output is a dry-run placeholder)" if dry_run else ""
            lines.append(("answer call per question, mean",
                          f"{mean(r['answer_input_tokens'] for r in priced):,.0f} in, "
                          f"{mean(r['answer_output_tokens'] for r in priced):,.0f} out"))
            if any(r["consolidate_input_tokens"] for r in priced):
                lines.append(("consolidation per question, mean (ADR 0010)",
                              f"{mean(r['consolidate_input_tokens'] for r in priced):,.0f} in, "
                              f"{mean(r['consolidate_output_tokens'] for r in priced):,.0f} out, "
                              f"{mean(len([c for c in r['calls'] if c['label'] == 'consolidate']) for r in priced):.1f} calls"))
            lines.append(("strategy cost per question, mean",
                          f"${mean(r['strategy_cost_usd'] for r in priced):.4f}, each call at its model's price{note}"))
        for label, value in lines:
            print(f"  {label:52s} {value}")
        if t == KU:
            for key, title in (("ku_breakdown", "breakdown, two evidence sessions (ADR 0009)"),
                               ("ku_breakdown_consolidated", "breakdown, consolidated or reached (ADR 0013)")):
                if key == "ku_breakdown_consolidated" and not summarised:
                    continue
                print(f"  {title:52s} questions" + ("" if dry_run else "  correct"))
                for group in ("neither", "earlier", "later", "both"):
                    g = [r for r in measured if r[key] == group]
                    right = "" if dry_run else f"  {sum(bool(r['correct']) for r in g)}"
                    print(f"    {group:50s} {len(g)}{right}")
                print(f"    {'not two evidence sessions (reported apart)':50s} {sum(r[key] is None for r in measured)}")

    calls = [c for r in rows for c in r["calls"]]
    by_label = {}
    for c in calls:
        tin, tout, cost = by_label.get(c["label"], (0, 0, 0.0))
        by_label[c["label"]] = (tin + c["input_tokens"], tout + c["output_tokens"], cost + cost_of([c]))
    print(f"\nall calls: {len(calls)}, {sum(c['failed'] for c in calls)} failed; "
          f"{sum(c['input_tokens'] for c in calls):,} tokens in, {sum(c['output_tokens'] for c in calls):,} out; "
          f"${cost_of(calls):.4f}, each call at its model's price"
          + (" (dry run: no call left this machine)" if dry_run else ""))
    for label, (tin, tout, cost) in sorted(by_label.items()):
        print(f"  {label:20s} {tin:>12,} in {tout:>10,} out  ${cost:.4f}")


# -- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per-type", type=int, default=PILOT_PER_TYPE, help="N questions of each type")
    ap.add_argument("--dry-run", action="store_true", help="no model calls; placeholders for answers")
    ap.add_argument("--strategy", choices=sorted(STRATEGIES), default="recent-turns")
    ap.add_argument("--workers", type=int, default=1, help="questions run at once; rows stay in list order")
    ap.add_argument("--out", type=Path, help="JSON lines file for the rows")
    args = ap.parse_args(argv)
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    data = load_pinned()
    lists = load_questions(args.per_type)
    counter = TiktokenCounter()
    require_real_counter(counter)
    consolidates = args.strategy in MODEL_CALL_STRATEGIES
    if args.dry_run:
        inner = {"answer": DryRunClient({"answer": "(dry run)"}), "grade": DryRunClient({"verdict": "(dry run)"}),
                 "consolidate": DryRunClient({"summary": dry_run_summary(counter)})}
    else:
        inner = {"answer": real_client(), "grade": real_client()}
        inner["consolidate"] = real_client(CONSOLIDATOR_MODEL) if consolidates else None
    # The row's model fields stay None in a dry run, as before; the calls are
    # still logged under the model they would be made with, so that a dry
    # run's cost is priced as the real run's will be (ADR 0015).
    meta = {"strategy": args.strategy, "model": None if args.dry_run else MODEL,
            "consolidator": CONSOLIDATOR_MODEL if consolidates and not args.dry_run else None,
            "dry_run": args.dry_run, "commit": git_commit(), "budget_tokens": DEFAULT_BUDGET_TOKENS}
    models = {"answer": MODEL, "grade": MODEL, "consolidate": CONSOLIDATOR_MODEL if consolidates else None}

    suffix = "-dry-run" if args.dry_run else ""
    out = args.out or RUNS / f"{args.strategy}-{datetime.now():%Y%m%d-%H%M%S}{suffix}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    by_id = {x["question_id"]: x for x in data}
    jobs = [(t, position, qid) for t in TYPES for position, qid in enumerate(lists[t][:args.per_type])]
    rows: list[dict] = []
    with out.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_question, by_id[qid], position, args.strategy, counter, inner, models, meta)
                   for _, position, qid in jobs]
        for (t, position, qid), future in zip(jobs, futures):
            row = future.result()
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            if row["recall"] is None:
                print(f"{'SSU' if t == SSU else 'KU '} {position + 1:>2}/{args.per_type} {qid:<12} error: {row['error']}")
                continue
            print(f"{'SSU' if t == SSU else 'KU '} {position + 1:>2}/{args.per_type} {qid:<12} "
                  f"reached={'yes' if row['evidence_reached'] else 'no ':3} recall={row['recall']:.2f} "
                  f"tokens={row['tokens_used']:>5} {row['status']}"
                  + ("" if args.dry_run else f" correct={row['correct']}"))

    # ADR 0005: whether the sample sits nearer the evidence than the list it came from.
    pool_distances = {}
    for t in TYPES:
        pool_distances[t] = []
        for qid in lists[t]:
            records, _, evidence = build_records(by_id[qid], "clock")
            pool_distances[t].append(distance_tokens(records, evidence, counter))
    summarize(rows, pool_distances, args.dry_run)
    print(f"\nrows: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
