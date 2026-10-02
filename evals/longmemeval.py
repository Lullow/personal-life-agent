"""Run a memory strategy headless on LongMemEval, under ADRs 0004–0009 and 0011.

Each question's history is replayed into a fresh strategy (0004), recalled at
23:59 on the question's day, answered by the model from what came back, and
graded (0008). Per question it logs recall and precision (0009), the distance
from the newest evidence to the question (0005), the tokens recalled against
the budget (0007), and what every model call cost (0006). For RetrievalMemory
it also logs recall with only the user turns written (0011). The agent is never
in the path: no ConversationAgent, no prompts.py.

The questions and their order come from evals/longmemeval_questions.json
(0005); the replay rules come from verify_adr_numbers.py. Rows go to
data/longmemeval/runs/ as JSON lines, one per question, written as they finish.

    .venv/bin/python evals/longmemeval.py --dry-run         # no model calls, no key needed
    .venv/bin/python evals/longmemeval.py                   # the M1 pilot, 10 per type; costs money
    .venv/bin/python evals/longmemeval.py --per-type 30
    .venv/bin/python evals/longmemeval.py --strategy retrieval --dry-run

--dry-run runs everything except the network. The answer call's prompt, and so
its input tokens, is exactly what a real run sends; the answers and verdicts
are placeholders, and no accuracy is reported.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
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
    DEFAULT_BUDGET_TOKENS, ApproxTokenCounter, ConversationMemory, MemoryRecord,
    RecentTurnsMemory, Retrieval, RetrievalMemory, TokenCounter, make_record_id,
)
from life_agent.agent.recording import LLMCall, RecordingLLMClient  # noqa: E402
from life_agent.config import get_settings  # noqa: E402
from life_agent.llm.client import LLMClient  # noqa: E402

QUESTIONS = ROOT / "evals" / "longmemeval_questions.json"
RUNS = ROOT / "data" / "longmemeval" / "runs"
MODEL = "openai/gpt-4o-2024-08-06"  # ADR 0008: the dated id, never an alias
ATTEMPTS = 3                        # ADR 0008: a call that returns None is tried twice more
# ADR 0008's prices in USD per million tokens. External: OpenRouter, 2026-09-26.
PRICE_IN, PRICE_OUT = 2.50, 10.00
# ADR 0006: the calls that count as a strategy's cost. "grade" never does.
STRATEGY_LABELS = ("answer", "consolidate")

# ADR 0008, copied from the record's code blocks, line breaks included.
ANSWER_SYSTEM_PROMPT = (
    "Below is your earlier conversation with the user. Answer the user's last\n"
    "question using only that conversation. If it does not contain the answer, say\n"
    'that you do not know. Reply with a JSON object: {"answer": "<your answer>"}.'
)
GRADE_SYSTEM_PROMPT = 'Reply with a JSON object: {"verdict": "yes"} or {"verdict": "no"}.'

# Each strategy is built fresh per replay, with the harness's counter.
STRATEGIES: dict[str, Callable[[TokenCounter], ConversationMemory]] = {
    # ADR 0007: no turn window; the budget is the only limit.
    "recent-turns": lambda counter: RecentTurnsMemory(max_turns=None, token_counter=counter),
    # ADR 0011: BM25 over every record, built with the counter and nothing else.
    "retrieval": lambda counter: RetrievalMemory(token_counter=counter),
}
# ADR 0011: the strategies whose recall is also computed with only user turns written.
USER_TURN_RECALL = ("retrieval",)


class DryRunClient:
    """Stands in for the model under --dry-run: every call returns *reply*."""

    def __init__(self, reply: dict) -> None:
        self._reply = reply

    def chat_json(self, system_prompt: str, messages: list[dict[str, str]]) -> dict:
        return dict(self._reply)


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


def real_client() -> LLMClient:
    s = get_settings()
    client = LLMClient(api_key=s.llm_api_key, base_url=s.llm_base_url, model=MODEL,
                       provider=s.llm_provider, timeout=60.0)
    if not client.enabled:
        raise SystemExit("no model configured: set LIFE_AGENT_LLM_BASE_URL and _API_KEY, or use --dry-run")
    if "openrouter.ai" not in (client.base_url or ""):
        raise SystemExit(f"ADR 0008 answers and grades through OpenRouter, not {client.base_url}")
    return client


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


def recall_of(x: dict, order: str, strategy: Callable[[TokenCounter], ConversationMemory],
              counter: TokenCounter, roles: tuple[str, ...] | None = None,
              ) -> tuple[Retrieval, set[str], list[MemoryRecord]]:
    records, ends, evidence = build_records(x, order)
    if len({r.id for r in records}) != len(records):
        raise ValueError(f"{x['question_id']}: two records share an id (ADR 0004)")
    memory = strategy(counter)
    replay(memory, records, ends, roles)
    retrieval = memory.retrieve(x["question"], at=question_time(x), budget_tokens=DEFAULT_BUDGET_TOKENS)
    # The budget counts the content of what came back and nothing else (ADR 0006).
    # A strategy that fell back on its own default counter shows up here.
    recount = sum(counter.count(m["content"]) for m in retrieval.messages)
    if retrieval.tokens_used != recount:
        raise ValueError(f"{x['question_id']}: tokens_used is {retrieval.tokens_used} but the messages "
                         f"hold {recount} tokens; the strategy is not counting with o200k_base")
    return retrieval, evidence, records


def recall_precision(sources: tuple[str, ...], evidence: set[str]) -> tuple[float, float]:
    """ADR 0009, for one question."""
    got = set(sources)
    hit = len(got & evidence)
    return hit / len(evidence), (hit / len(got) if got else 0.0)


def ku_breakdown(x: dict, sources: tuple[str, ...]) -> str | None:
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


def run_question(x: dict, position: int, strategy: Callable[[TokenCounter], ConversationMemory],
                 counter: TokenCounter, answer_llm: RecordingLLMClient, grade_llm: RecordingLLMClient,
                 log: list[LLMCall], meta: dict) -> dict:
    start = len(log)
    retrieval, evidence, records = recall_of(x, "clock", strategy, counter)
    recall, precision = recall_precision(retrieval.sources, evidence)
    distance = distance_tokens(records, evidence, counter)
    row = {
        **meta,
        "question_id": x["question_id"],
        "question_type": x["question_type"],
        "position": position,
        "question": x["question"],
        "question_date": x["question_date"],
        "gold_answer": str(x["answer"]),
        "evidence": sorted(evidence),
        "sources": list(retrieval.sources),
        "tokens_used": retrieval.tokens_used,
        "over_budget": retrieval.tokens_used > DEFAULT_BUDGET_TOKENS,
        "recall": recall,
        "precision": precision,
        "evidence_reached": bool(set(retrieval.sources) & evidence),
        # ADR 0009: only knowledge-update questions differ between the two orders.
        "ku_breakdown": None,
        "recall_list_order": None,
        "evidence_reached_list_order": None,
        # ADR 0011: only for a strategy that ranks; E stays as the dataset marks it.
        "recall_user_turns": None,
        "evidence_reached_user_turns": None,
        "distance_tokens": distance,
        "long_term": distance > DEFAULT_BUDGET_TOKENS,
        "history_tokens": sum(counter.count(r.content) for r in records),
        "records": len(records),
    }
    if x["question_type"] == KU:
        row["ku_breakdown"] = ku_breakdown(x, retrieval.sources)
        listed, listed_evidence, _ = recall_of(x, "list", strategy, counter)
        row["recall_list_order"] = recall_precision(listed.sources, listed_evidence)[0]
        row["evidence_reached_list_order"] = bool(set(listed.sources) & listed_evidence)
    if meta["strategy"] in USER_TURN_RECALL:
        users, _, _ = recall_of(x, "clock", strategy, counter, roles=("user",))
        row["recall_user_turns"] = recall_precision(users.sources, evidence)[0]
        row["evidence_reached_user_turns"] = bool(set(users.sources) & evidence)

    reply, row["answer_attempts"] = ask(answer_llm, ANSWER_SYSTEM_PROMPT, answer_messages(x, retrieval))
    row.update(answer=None, answer_is_string=None, verdict=None, correct=None, grade_attempts=0, status="error")
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

    calls = log[start:]
    paid = [c for c in calls if c.label in STRATEGY_LABELS and not c.failed]
    row["strategy_input_tokens"] = sum(c.input_tokens for c in paid)
    row["strategy_output_tokens"] = sum(c.output_tokens for c in paid)
    row["calls"] = [asdict(c) for c in calls]
    return row


# -- summary -----------------------------------------------------------------

def usd(tokens_in: float, tokens_out: float) -> float:
    return (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6


def summarize(rows: list[dict], pool_distances: dict[str, list[int]], dry_run: bool) -> None:
    mean = statistics.fmean
    for t in TYPES:
        rs = [r for r in rows if r["question_type"] == t]
        if not rs:
            continue
        n, ok = len(rs), [r for r in rs if r["status"] == "ok"]
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
        lines += [
            ("recall, mean", f"{mean(r['recall'] for r in rs):.3f}"),
            ("precision, mean", f"{mean(r['precision'] for r in rs):.4f}"),
            ("evidence reached", f"{sum(r['evidence_reached'] for r in rs)} of {n}"),
        ]
        if t == KU:
            lines += [
                ("recall, list order, mean", f"{mean(r['recall_list_order'] for r in rs):.3f}"),
                ("evidence reached, list order", f"{sum(r['evidence_reached_list_order'] for r in rs)} of {n}"),
            ]
        if rs[0]["recall_user_turns"] is not None:
            lines += [
                ("recall, user turns only, mean", f"{mean(r['recall_user_turns'] for r in rs):.3f}"),
                ("evidence reached, user turns only", f"{sum(r['evidence_reached_user_turns'] for r in rs)} of {n}"),
            ]
        lines += [
            ("messages recalled, mean / max", f"{mean(len(r['sources']) for r in rs):,.0f} / {max(len(r['sources']) for r in rs):,}"),
            ("tokens_used, mean / max", f"{mean(r['tokens_used'] for r in rs):,.0f} / {max(r['tokens_used'] for r in rs):,}"),
            ("over budget", f"{sum(r['over_budget'] for r in rs)}"),
            ("long-term, sample / whole list",
             f"{sum(r['long_term'] for r in rs)} of {n} / "
             f"{sum(d > DEFAULT_BUDGET_TOKENS for d in pool)} of {len(pool)}"),
            ("distance to evidence, median, sample / whole list",
             f"{statistics.median(r['distance_tokens'] for r in rs):,.0f} / {statistics.median(pool):,.0f}"),
            ("history tokens, mean", f"{mean(r['history_tokens'] for r in rs):,.0f}"),
        ]
        s_in = mean(r["strategy_input_tokens"] for r in rs)
        s_out = mean(r["strategy_output_tokens"] for r in rs)
        note = " (output is a dry-run placeholder)" if dry_run else ""
        lines.append(("strategy cost per question, mean",
                      f"{s_in:,.0f} in, {s_out:,.0f} out, ${usd(s_in, s_out):.4f}{note}"))
        for label, value in lines:
            print(f"  {label:52s} {value}")
        if t == KU:
            print(f"  {'breakdown, two evidence sessions (ADR 0009)':52s} questions" + ("" if dry_run else "  correct"))
            for group in ("neither", "earlier", "later", "both"):
                g = [r for r in rs if r["ku_breakdown"] == group]
                right = "" if dry_run else f"  {sum(bool(r['correct']) for r in g)}"
                print(f"    {group:50s} {len(g)}{right}")
            print(f"    {'not two evidence sessions (reported apart)':50s} {sum(r['ku_breakdown'] is None for r in rs)}")

    calls = [c for r in rows for c in r["calls"]]
    t_in, t_out = sum(c["input_tokens"] for c in calls), sum(c["output_tokens"] for c in calls)
    print(f"\nall calls: {len(calls)}, {sum(c['failed'] for c in calls)} failed; "
          f"{t_in:,} tokens in, {t_out:,} out; ${usd(t_in, t_out):.4f} at ADR 0008's prices"
          + (" (dry run: no call left this machine)" if dry_run else ""))


# -- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per-type", type=int, default=PILOT_PER_TYPE, help="N questions of each type")
    ap.add_argument("--dry-run", action="store_true", help="no model calls; placeholders for answers")
    ap.add_argument("--strategy", choices=sorted(STRATEGIES), default="recent-turns")
    ap.add_argument("--out", type=Path, help="JSON lines file for the rows")
    args = ap.parse_args(argv)

    data = load_pinned()
    lists = load_questions(args.per_type)
    counter = TiktokenCounter()
    require_real_counter(counter)
    if args.dry_run:
        answer_inner, grade_inner = DryRunClient({"answer": "(dry run)"}), DryRunClient({"verdict": "(dry run)"})
    else:
        answer_inner = grade_inner = real_client()
    log: list[LLMCall] = []
    answer_llm = RecordingLLMClient(answer_inner, label="answer", counter=counter, log=log)
    grade_llm = RecordingLLMClient(grade_inner, label="grade", counter=counter, log=log)
    meta = {"strategy": args.strategy, "model": None if args.dry_run else MODEL, "dry_run": args.dry_run,
            "commit": git_commit(), "budget_tokens": DEFAULT_BUDGET_TOKENS}

    suffix = "-dry-run" if args.dry_run else ""
    out = args.out or RUNS / f"{args.strategy}-{datetime.now():%Y%m%d-%H%M%S}{suffix}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    by_id = {x["question_id"]: x for x in data}
    strategy = STRATEGIES[args.strategy]
    rows: list[dict] = []
    with out.open("w", encoding="utf-8") as f:
        for t in TYPES:
            for position, qid in enumerate(lists[t][:args.per_type]):
                row = run_question(by_id[qid], position, strategy, counter, answer_llm, grade_llm, log, meta)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                rows.append(row)
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
