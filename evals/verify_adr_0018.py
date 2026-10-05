"""Recompute the figures in ADRs 0018 and 0019 from the pinned dataset, the spike's saved replies and the committed rows.

For 0018 the figures describe what the fact extraction gave on the eight
histories no run measures, and what the record's rule does when round three's
saved replies are replayed under it: what is stored, what is replaced, and
what a retrieve would show. For 0019 they are the three measured strategies on
the pilot's 20 questions and an estimate of what the pilot costs. Nothing here
calls a model, answers a question or grades one.

The replies were made under round three's rule, not under the record's: the
replay shows what the record's rule does to those replies, not what the model
would have replied under it.

With --facts round two's replies are replayed under the same rule as well,
the numbers its model named left aside, and the two rounds are printed side
by side. The record states no figure from round two's replay. Its replies
are further from the rule than round three's: its prompt does not say that a
name replaces, and each call saw the facts left by what the model had named.

    .venv/bin/python evals/verify_adr_0018.py
    .venv/bin/python evals/verify_adr_0018.py --facts    # rounds two and three under the rule: stored, replaced, shown
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import CHOSEN_N  # noqa: E402
from evals.longmemeval import QUESTIONS, cost_of, load_questions, usd  # noqa: E402
from evals.results_table import RESULTS, RUNS, rows as run_rows  # noqa: E402
from evals.spike_fact_graph import PROMPTS, key_of, norm, prompt_id, replacements  # noqa: E402
from evals.verify_adr_numbers import (  # noqa: E402
    ADR_DIR, KU, PILOT_PER_TYPE, SSU, TYPES, Claim, TiktokenCounter, build_records, evidence_sessions, fmt, judge,
    load_pinned, replay_order,
)
from life_agent.agent.memory import MemoryRecord, RetrievalMemory, _terms  # noqa: E402

SPIKE = RESULTS / "spike"  # the spike's replies, copied from data/longmemeval/spike/ to be committed
M1_PILOT = "recent-turns-20260927-132525.jsonl"
FACT_TOKENS = 1000  # ADR 0018's F; the class takes the constant over when it is built
# What each spike question's answer needs, read by hand from its reference
# answer. A definition, not a fact: "the fact holding the answer" is a fact
# whose relation or value contains this.
ANSWER = {"5c40ec5b": "twice", "6a1eabeb": "25:50", "41698283": "70-200", "42ec0761": "spare",
          "dfde3500": "wednesday", "184da446": "220", "dad224aa": "7:30", "9ea5eabc": "paris"}
# The value each spike question is about, before and after it changes: what
# marks the old fact in the earlier evidence session and the new one in the
# later, read by hand from the evidence turns. Also a definition: the changed
# value "kept its name" in a round when two such facts share subject and
# relation, so a value that was not extracted counts as not kept.
CHANGED = {"5c40ec5b": ("alex", "twice"), "6a1eabeb": ("27:12", "25:50"), "41698283": ("50mm", "70-200"),
           "42ec0761": ("screwdriver", "spare"), "dfde3500": ("wednesday", "thursday"), "184da446": ("200", "220"),
           "dad224aa": ("8:30", "7:30"), "9ea5eabc": ("hawaii", "paris")}
MARKERS = "by the CHANGED markers in this script; the reading is evals/results/spike/reading.md"
# The words of the prompt's examples; none may occur in a question of the list or in its answer.
EXAMPLE_WORDS = ("blood", "dentist", "sibling", "allerg")
HAND = "read by hand 2026-10-05, not recomputed"


def adr_text(number: str) -> str:
    paths = sorted(ADR_DIR.glob(f"{number}-*.md"))
    if not paths:
        raise SystemExit(f"no ADR {number} to check")
    return paths[0].read_text(encoding="utf-8")


def system_prompt(text: str) -> str:
    """The first fenced block after "word for word:", as the record states it."""
    m = re.search(r"word for word:\s*```\n(.*?)```", text, re.DOTALL)
    if m is None:
        raise SystemExit("ADR 0018 has no system prompt block")
    return m.group(1).strip()


def saved(round_: int, qid: str) -> list[dict]:
    path = SPIKE / f"{qid}-{prompt_id(PROMPTS[round_])}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def line_of(fact: dict) -> str:
    """A fact as ADR 0018 shows it, to the extraction call and to the answering model."""
    return f"{fact['subject']} / {fact['relation']} = {fact['value']}"


def same_fact(a: dict, b: dict) -> bool:
    return key_of(a) == key_of(b) and norm(a["value"]) == norm(b["value"])


def content_key(session: list[dict]) -> str:
    """Names a session by what was said in it: the dataset reuses a conversation under more than one id."""
    turns = [(t["role"], t["content"]) for t in session]
    return hashlib.sha256(json.dumps(turns, ensure_ascii=False).encode("utf-8")).hexdigest()


# -- ADR 0018's rule, replayed over saved replies ------------------------------

def stored_facts(rows: list[dict]) -> tuple[list[dict], int]:
    """The replacement rule of ADR 0018 over one history's replies, session by session.

    Returns the facts stored, in order, each with the fact that replaced it if
    any, and how many facts were not stored because they were said again.
    """
    stored: list[dict] = []
    said_again = 0
    for row in rows:
        held = [f for f in stored if f["replaced_by"] is None]
        new: list[dict] = []
        confirmed: set[str] = set()
        for entry in row["facts"]:
            fact = dict(entry, session_id=row["session_id"], at=row["at"], replaced_by=None, replaced_at=None,
                        evidence_turn=entry["turn"] in row["evidence_turns"],
                        evidence_session=bool(row["evidence_turns"]))
            again = [old for old in held if same_fact(old, fact)]
            if again or any(same_fact(other, fact) for other in new):
                confirmed.update(old["id"] for old in again)
                said_again += 1
                continue
            fact["id"] = f"fact:{row['session_id']}:{len(new)}"
            new.append(fact)
        for fact in new:
            for old in held:
                if old["replaced_by"] is None and key_of(old) == key_of(fact) and old["id"] not in confirmed:
                    old["replaced_by"], old["replaced_at"] = fact["id"], row["at"]
        stored += new
    return stored, said_again


def facts_shown(question: str, held: list[dict], turn_text: dict[tuple[str, int], str],
                counter: TiktokenCounter, with_turn: bool = True) -> tuple[list[int], list[int]]:
    """What ADR 0018's retrieve takes of the facts that hold: positions by rank, and those taken, in stored order.

    The ranking is ADR 0011's, read off RetrievalMemory so that it is the same
    code; *with_turn* False ranks a fact on its line alone, the rejected rule.
    """
    index = RetrievalMemory(token_counter=counter)
    for i, fact in enumerate(held):
        text = line_of(fact) + (" " + turn_text[(fact["session_id"], fact["turn"])] if with_turn else "")
        index.write(MemoryRecord(id=str(i), role="assistant", content=text, kind="message",
                                 at=datetime.fromisoformat(fact["at"]), session_id=fact["session_id"]))
    scores = index._scores(question, list(range(len(held))))
    ranked = sorted((i for i in scores if scores[i] > 0), key=lambda i: (-scores[i], -i))
    taken: list[int] = []
    for i in ranked:
        trial = sorted(taken + [i])
        if counter.count("\n".join(line_of(held[j]) for j in trial)) <= FACT_TOKENS:
            taken = trial
    return ranked, taken


def has_answer(qid: str, fact: dict) -> bool:
    return ANSWER[qid] in f"{fact['relation']} = {fact['value']}".casefold()


def name_kept(round_: int, qid: str) -> bool:
    """Whether the changed value has one subject and relation in both evidence sessions of a round's replies."""
    earlier, later = (r for r in saved(round_, qid) if r["evidence_turns"])
    old, new = CHANGED[qid]
    marked = lambda row, marker: {key_of(f) for f in row["facts"]  # noqa: E731
                                  if marker in f"{f['relation']} = {f['value']}".casefold()}
    return bool(marked(earlier, old) & marked(later, new))


def replay(x: dict, rows: list[dict], counter: TiktokenCounter) -> dict:
    """One spike history under ADR 0018: what is stored, and what the question would be shown."""
    qid = x["question_id"]
    turn_text = {(sid, j): t["content"] for sid, session in zip(x["haystack_session_ids"], x["haystack_sessions"])
                 for j, t in enumerate(session)}
    evidence = {(r["session_id"], t) for r in rows for t in r["evidence_turns"]}
    stored, said_again = stored_facts(rows)
    by_id = {f["id"]: f for f in stored}
    held = [f for f in stored if f["replaced_by"] is None]
    out = dict(qid=qid, stored=len(stored), said_again=said_again, replaced=len(stored) - len(held), held=len(held),
               held_tokens=counter.count("\n".join(line_of(f) for f in held)))
    from_evidence_sessions = [f for f in stored if f["evidence_session"]]
    by_filler = [f for f in from_evidence_sessions
                 if f["replaced_by"] and not by_id[f["replaced_by"]]["evidence_session"]]
    out.update(evidence_session_facts=len(from_evidence_sessions),
               replaced_by_filler=sum(norm(f["value"]) != norm(by_id[f["replaced_by"]]["value"]) for f in by_filler))
    from_evidence_turns = [f for f in stored if f["evidence_turn"]]
    out.update(evidence_turn_facts=len(from_evidence_turns),
               evidence_turn_replaced=sum(f["replaced_by"] is not None for f in from_evidence_turns),
               evidence_to_evidence=sum(f["replaced_by"] is not None and by_id[f["replaced_by"]]["evidence_turn"]
                                        for f in from_evidence_turns),
               relations=Counter(f["relation"] for f in stored if f["replaced_by"] is not None),
               evidence_turn_pairs=[(line_of(f), line_of(by_id[f["replaced_by"]]), by_id[f["replaced_by"]]["evidence_turn"])
                                    for f in from_evidence_turns if f["replaced_by"] is not None])
    for with_turn in (False, True):
        ranked, taken = facts_shown(x["question"], held, turn_text, counter, with_turn)
        rank = min((n for n, i in enumerate(ranked, start=1) if has_answer(qid, held[i])), default=None)
        tag = "turn" if with_turn else "line"
        out[f"answer_rank_{tag}"] = rank
        out[f"answer_shown_{tag}"] = any(has_answer(qid, held[i]) for i in taken)
        out[f"no_term_{tag}"] = len(held) - len(ranked)
    shown = [held[i] for i in taken]
    sessions_shown = {f["session_id"] for f in shown}
    out.update(shown=len(shown), matching=len(ranked), evidence_turn_shown=sum(f["evidence_turn"] for f in shown),
               shown_lines=[line_of(f) for f in shown],
               shown_tokens=counter.count("\n".join(line_of(f) for f in shown)),
               evidence_turns=len(evidence),
               evidence_consolidated=sum(sid in sessions_shown for sid, _ in evidence))
    return out


# -- everything computed -------------------------------------------------------

def spike_rounds(histories: list[str], data: dict) -> dict:
    """The three rounds as they ran, from their saved replies."""
    f: dict = {}
    for round_ in PROMPTS:
        per_history = {q: saved(round_, q) for q in histories}
        rows = [r for q in histories for r in per_history[q]]
        facts = [(q, r, fact) for q in histories for r in per_history[q] for fact in r["facts"]]
        calls = [c for r in rows for c in r["calls"]]
        sessions_of_pair: dict[tuple, set[str]] = {}
        for q, r, fact in facts:
            sessions_of_pair.setdefault((q, *key_of(fact)), set()).add(r["session_id"])
        replaced = same_value = from_evidence = evidence_to_evidence = 0
        most_in_one = 0
        relations: Counter[str] = Counter()
        narrow_by: Counter[str] = Counter()
        for q in histories:
            numbered = {fact["number"]: (r, fact) for r in per_history[q] for fact in r["facts"] if "number" in fact}
            found = replacements(per_history[q])
            replaced += len(found)
            most_in_one = max(most_in_one, len(found))
            for old, (by_row, by) in found.items():
                old_row, old_fact = numbered[old]
                same_value += norm(old_fact["value"]) == norm(by["value"])
                relations[old_fact["relation"]] += 1
                if old_fact["turn"] in old_row["evidence_turns"]:
                    from_evidence += 1
                    evidence_to_evidence += by["turn"] in by_row["evidence_turns"]
            # The narrower rule 0018 rejects: one fact under the name before the session, one in it.
            current: dict[int, dict] = {}
            for r in per_history[q]:
                before = dict(current)
                in_session = Counter(key_of(fact) for fact in r["facts"])
                for fact in r["facts"]:
                    if "number" not in fact:
                        continue
                    alone = sum(key_of(g) == key_of(fact) for g in before.values()) == 1 and in_session[key_of(fact)] == 1
                    for old in fact.get("replaces", []):
                        if current.pop(old, None) is not None and alone:
                            narrow_by[fact["relation"]] += 1
                    current[fact["number"]] = fact
        answer_extracted = sum(any(has_answer(q, fact) for r in per_history[q] if r["evidence_turns"] for fact in r["facts"])
                               for q in histories)
        evidence_rows = [r for r in rows if r["evidence_turns"]]
        assistant_turn = sum(data[q]["haystack_sessions"][data[q]["haystack_session_ids"].index(r["session_id"])]
                             [fact["turn"]]["role"] == "assistant" for q, r, fact in facts)
        f[round_] = dict(
            prompt=prompt_id(PROMPTS[round_]), sessions=len(rows), calls=len(calls),
            failed=sum(c["failed"] for c in calls) + sum(r["failed"] for r in rows),
            facts=len(facts), pairs=len(sessions_of_pair),
            pairs_repeated=sum(len(s) > 1 for s in sessions_of_pair.values()),
            replaced=replaced, same_value=same_value, most_in_one=most_in_one, relations=relations,
            from_evidence=from_evidence, evidence_to_evidence=evidence_to_evidence,
            narrow=sum(narrow_by.values()), narrow_by=narrow_by,
            user_subject=sum(norm(fact["subject"]) == "user" for _, _, fact in facts),
            answer_extracted=answer_extracted, evidence_sessions=len(evidence_rows),
            pointed=sum(any(fact["turn"] in r["evidence_turns"] for fact in r["facts"]) for r in evidence_rows),
            assistant_turn=assistant_turn, most_shown=max((r.get("facts_shown", 0) for r in rows)),
            cost=cost_of(calls), tokens_in=statistics.fmean(c["input_tokens"] for c in calls),
            tokens_out=statistics.fmean(c["output_tokens"] for c in calls),
        )
    # Round three: facts with no word of their value in the user's turns of their session.
    unsaid = 0
    for q in histories:
        x = data[q]
        said = {sid: " ".join(t["content"] for t in session if t["role"] == "user").casefold()
                for sid, session in zip(x["haystack_session_ids"], x["haystack_sessions"])}
        for r in saved(3, q):
            for fact in r["facts"]:
                words = [w for w in _terms(fact["value"]) if len(w) > 2 or w.isdigit()]
                unsaid += bool(words) and not any(w in said[r["session_id"]] for w in words)
    f["unsaid"] = unsaid
    return f


def shared_sessions(histories: list[str], data: dict, lists: dict) -> dict:
    """How many of the spike's sessions also occur, by content, in a measured history."""
    measured, pilot, evidence = set(), set(), set()
    for t in TYPES:
        for position, qid in enumerate(lists[t][:CHOSEN_N]):
            x = data[qid]
            holds_evidence = set(evidence_sessions(x))
            for i, session in enumerate(x["haystack_sessions"]):
                key = content_key(session)
                measured.add(key)
                if position < PILOT_PER_TYPE:
                    pilot.add(key)
                if i in holds_evidence:
                    evidence.add(key)
    sessions = shared = in_pilot = with_evidence = 0
    for qid in histories:
        x = data[qid]
        holds_evidence = set(evidence_sessions(x))
        for i in replay_order(x, "clock"):
            key = content_key(x["haystack_sessions"][i])
            sessions += 1
            shared += key in measured
            in_pilot += key in pilot
            with_evidence += key in measured and (i in holds_evidence or key in evidence)
    return dict(sessions=sessions, shared=shared, shared_pilot=in_pilot, shared_evidence=with_evidence)


def pilot_figures(data: dict, lists: dict, per_session: float) -> dict:
    """ADR 0019: the measured strategies on the pilot's 20 questions, and what the pilot is estimated to cost."""
    correct = {}
    for name in RUNS:
        rs = run_rows(name)
        correct[name] = tuple(sum(bool(r["correct"]) for r in rs if r["question_type"] == t and r["position"] < PILOT_PER_TYPE)
                              for t in TYPES)
    first = [json.loads(line) for line in (RESULTS / M1_PILOT).read_text(encoding="utf-8").splitlines()]
    again = {r["question_id"]: r for r in run_rows("recent-turns")}
    sessions = {t: [len(build_records(data[q], "clock")[1]) for q in lists[t][:CHOSEN_N]] for t in TYPES}
    pilot_sessions = sum(sum(v[:PILOT_PER_TYPE]) for v in sessions.values())
    list_order = sum(len(build_records(data[q], "list")[1]) for q in lists[KU][:PILOT_PER_TYPE])
    every = sum(sum(v) for v in sessions.values())

    def per_question(label: str) -> float:
        return statistics.fmean(usd(sum(c["input_tokens"] for c in r["calls"] if c["label"] == label and not c["failed"]),
                                    sum(c["output_tokens"] for c in r["calls"] if c["label"] == label and not c["failed"]))
                                for r in run_rows("retrieval"))

    answer, grade = per_question("answer"), per_question("grade")
    questions = PILOT_PER_TYPE * len(TYPES)
    extraction = (pilot_sessions + list_order) * per_session
    answers = questions * (answer + grade)
    return dict(correct=correct, repeat_agrees=sum(r["correct"] == again[r["question_id"]]["correct"] for r in first),
                repeat_of=len(first), questions=questions, pilot_sessions=pilot_sessions, list_order=list_order,
                answer=answer, grade=grade, extraction=extraction, answers=answers, pilot=extraction + answers,
                every=CHOSEN_N * len(TYPES) * (answer + grade) + (every + list_order) * per_session,
                run_days=sorted({RUNS[name].split("-")[-2][6:8].lstrip("0") for name in RUNS}))


def compute(text: str) -> dict:
    data = {x["question_id"]: x for x in load_pinned()}
    lists = load_questions(CHOSEN_N)
    doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    histories = [q for t in TYPES for q in doc[t][CHOSEN_N:]]
    counter = TiktokenCounter()
    f = spike_rounds(histories, data)
    f.update(histories=histories, pool_ku=len(doc[KU]), unmeasured=len(histories), unmeasured_ssu=len(doc[SSU][CHOSEN_N:]),
             kept={round_: [q for q in histories if name_kept(round_, q)] for round_ in PROMPTS},
             alex={norm(fact["relation"]) for r in saved(3, "5c40ec5b") for fact in r["facts"] if norm(fact["value"]) == "alex"},
             prompt_in_spike=system_prompt(text) == PROMPTS[3],
             prompt_tokens=counter.count(system_prompt(text)),
             examples_unused=not any(w in f"{data[q]['question']} {data[q]['answer']}".casefold()
                                     for t in TYPES for q in doc[t] for w in EXAMPLE_WORDS),
             shared=shared_sessions(histories, data, lists),
             replays=[replay(data[q], saved(3, q), counter) for q in histories],
             # Not in the record: round two's replies under the same rule, for --facts.
             replays_two=[replay(data[q], saved(2, q), counter) for q in histories],
             spike_cost=sum(f[r]["cost"] for r in PROMPTS))
    f["pilot"] = pilot_figures(data, lists, f[3]["cost"] / f[3]["calls"])
    return f


# -- claims --------------------------------------------------------------------

def claims_0018(f: dict) -> list[Claim]:
    one, two, three, shared, replays, kept = f[1], f[2], f[3], f["shared"], f["replays"], f["kept"]
    replays_two = f["replays_two"]
    total = lambda key: sum(r[key] for r in replays)  # noqa: E731
    total_two = lambda key: sum(r[key] for r in replays_two)  # noqa: E731
    lost = [q for q in kept[2] if q not in kept[3]]
    paris = next(r for r in replays if r["qid"] == "9ea5eabc")["shown_lines"]
    span = lambda key: (min(r[key] for r in replays), max(r[key] for r in replays))  # noqa: E731
    return [
        Claim("0018", "the unmeasured histories", r"the last (\d+) of the (\d+) in the list", (f["unmeasured"], f["pool_ku"])),
        Claim("0018", "…their ids", r"`(\w{8})`, `(\w{8})`,\s*`(\w{8})`, `(\w{8})`, `(\w{8})`, `(\w{8})`, `(\w{8})` and `(\w{8})`\. No",
              tuple(f["histories"])),
        Claim("0018", "sessions per round; no failed call", r"same (\d+) sessions, one call per session, and no call failed",
              (one["sessions"],) if {f[r]["sessions"] for r in PROMPTS} == {one["calls"]} and not any(f[r]["failed"] for r in PROMPTS)
              else ("differs",)),
        Claim("0018", "the three prompt ids", r"prompt `(\w{8})`.*prompt `(\w{8})`.*prompt `(\w{8})`: each call given",
              (one["prompt"], two["prompt"], three["prompt"])),
        Claim("0018", "round one: facts, pairs, repeated", r"([\d,]+) facts under ([\d,]+) distinct pairs of subject and relation, (\d+) of them in more than one session",
              (one["facts"], one["pairs"], one["pairs_repeated"])),
        Claim("0018", "round one: the changed value's name kept", r"kept its name between its two sessions in (\d+) of the (\d+) histories",
              (len(kept[1]), f["unmeasured"]), note=MARKERS),
        Claim("0018", "round two: facts, replaced", r"(\d+) facts, (\d+) replaced, and in none of the \d+ did a fact from an evidence turn replace",
              (two["facts"], two["replaced"]) if two["evidence_to_evidence"] == 0 else ("differs",)),
        Claim("0018", "round two: the 8 replacements, by hand", r"(\d+) of the 8 was right, (\d+) restated the same value with more detail and (\d+) were wrong",
              kind="external", note="the author's reading of evals/results/spike/reading.md, part A"),
        Claim("0018", "round two: the changed value's name kept", r"names: by the hand reading the changed value kept its name in (\d+) of the (\d+) histories",
              (len(kept[2]), f["unmeasured"]), note=MARKERS),
        Claim("0018", "round three: facts, replaced, same value, one history",
              r"(\d+) facts, (\d+) replaced, (\d+) of them by the same value and (\d+) of them in one history",
              (three["facts"], three["replaced"], three["same_value"], three["most_in_one"])),
        Claim("0018", "round three: the names that replace most", r"`recent_activity` (\d+) times, `plan` (\d+), `upcoming_trip` (\d+)",
              tuple(three["relations"][k] for k in ("recent_activity", "plan", "upcoming_trip")),
              note="the three most common: " + ", ".join(k for k, _ in three["relations"].most_common(3))),
        Claim("0018", "round three: evidence-turn facts replaced", r"(\d+) facts from an evidence turn were replaced, (\d+) of them by a fact from an evidence turn",
              (three["from_evidence"], three["evidence_to_evidence"])),
        Claim("0018", "round three: old value replaced, by hand", r"the new value replaced it in (\d+), in part in (\d+) and not in (\d+)",
              kind="external", note=HAND),
        Claim("0018", "round three: the changed value's name kept", r"By the hand reading the changed value kept its name in (\d+) of the (\d+)\. Every",
              (len(kept[3]), f["unmeasured"]), note=MARKERS),
        Claim("0018", "round three: every subject is user", r"Every one of the (\d+) facts has `user` as its subject",
              (three["user_subject"],) if three["user_subject"] == three["facts"] else ("differs",)),
        Claim("0018", "the answer's value extracted in every round", r"the value each of the eight questions asks for was extracted from an evidence session",
              all(f[r]["answer_extracted"] == f["unmeasured"] for r in PROMPTS), note="by the ANSWER markers in this script"),
        Claim("0018", "answer found, ranked on the line", r"shares a word with the question in (\d+) of the (\d+) histories",
              (sum(r["answer_rank_line"] is not None for r in replays), len(replays))),
        Claim("0018", "replaced by the same value; 9ea5eabc", r"(\d+) facts were replaced by a fact with the same value. In `(\w{8})`",
              (three["same_value"], "9ea5eabc")),
        Claim("0018", "evidence-session facts replaced by a filler", r"Of the (\d+) facts from evidence sessions, (\d+) were replaced with another value",
              (total("evidence_session_facts"), total("replaced_by_filler"))),
        Claim("0018", "the turn pointer", r"in (\d+) of the (\d+) evidence sessions at least one fact points at an evidence turn",
              (three["pointed"], three["evidence_sessions"])),
        Claim("0018", "sessions shared with measured histories", r"(\d+) of their (\d+) sessions also occur in one of the (\d+) measured histories, (\d+) of them in one of the pilot's (\d+)",
              (shared["shared"], shared["sessions"], CHOSEN_N * len(TYPES), shared["shared_pilot"], PILOT_PER_TYPE * len(TYPES))),
        Claim("0018", "…none of them evidence", r"None of the (\d+) holds evidence",
              (shared["shared"],) if shared["shared_evidence"] == 0 else ("differs",)),
        Claim("0018", "Neo4j image and digest", r"`neo4j:([\d.]+)` with digest `sha256:([0-9a-f]{64})`", kind="external",
              note="docker image inspect, 2026-10-05"),
        Claim("0018", "driver version", r"Python driver `neo4j`, version (\d+\.\d+\.\d+)", kind="external", note="pip show neo4j, 2026-10-05"),
        Claim("0018", "the prompt is round three's", r"round three's, word for word", f["prompt_in_spike"],
              note=f"spike_fact_graph.KEYED_SYSTEM_PROMPT, {f['prompt_tokens']} tokens"),
        Claim("0018", "the prompt's examples are in no question", r"\(blood_type, dentist_name, number_of_siblings\)", f["examples_unused"],
              note=f"{', '.join(EXAMPLE_WORDS)} in none of the list's questions or answers"),
        Claim("0018", "F", r"counts at most F = ([\d,]+) tokens", (FACT_TOKENS,)),
        Claim("0018", "rejected: the model names what is replaced",
              r"It did so (\d+) times in (\d+) sessions, and no question's new value replaced its old one",
              (two["replaced"], two["sessions"]) if two["evidence_to_evidence"] == 0 else ("differs",),
              note="no fact from an evidence turn replaced one from an evidence turn"),
        Claim("0018", "rejected: the narrower rule", r"leaves (\d+) of the (\d+) replacements: it takes out (\d+) of the (\d+) under `recent_activity` and leaves all (\d+) under `plan`",
              (three["narrow"], three["replaced"], three["relations"]["recent_activity"] - three["narrow_by"]["recent_activity"],
               three["relations"]["recent_activity"], three["narrow_by"]["plan"])
              if three["narrow_by"]["plan"] == three["relations"]["plan"] else ("differs",)),
        Claim("0018", "rejected: the pointer misses", r"misses in (\d+) of (\d+) evidence sessions",
              (three["evidence_sessions"] - three["pointed"], three["evidence_sessions"])),
        Claim("0018", "rejected: round two's prompt, the name kept", r"keep the name of the changed value in (\d+) of the 8 histories against (\d+)",
              (len(kept[2]), len(kept[3])), note=MARKERS),
        Claim("0018", "rejected: round two's prompt, replaced by a filler",
              r"and (\d+) of the (\d+) facts from evidence sessions are replaced with another value by a session without evidence against (\d+)",
              (total_two("replaced_by_filler"), total_two("evidence_session_facts"), total("replaced_by_filler"))),
        Claim("0018", "rejected: round two's prompt, replaced in all",
              r"(\d+) facts against (\d+), (\d+) of them under `recent_activity` and (\d+) in one history, which is left with (\d+) facts that hold",
              (total_two("replaced"), total("replaced"), sum((r["relations"] for r in replays_two), Counter())["recent_activity"],
               max(r["replaced"] for r in replays_two), max(replays_two, key=lambda r: r["replaced"])["held"])),
        Claim("0018", "rejected: round two's prompt, the author's bar", r"at least (\d+) of 8, and fewer than (\d+) of 69", kind="external",
              note="the author's bar, as the author states it"),
        Claim("0018", "…the first was met, the second was not", r"The second was not met",
              len(kept[2]) >= 4 and not total_two("replaced_by_filler") < 4),
        Claim("0018", "…the prompt kept meets neither", r"The prompt that is kept meets neither",
              len(kept[3]) < 4 and not total("replaced_by_filler") < 4,
              note=f"{len(kept[3])} of 8 and {total('replaced_by_filler')} of {total('evidence_session_facts')}"),
        Claim("0018", "…three names changed between the rounds", r"where (\w+) of the changed values changed their name from one round to the next",
              (len(lost),), note=MARKERS),
        Claim("0018", "rejected: a second Alex, by hand", r"A second Alex in one of the eight histories", kind="external", note=HAND),
        Claim("0018", "replay: said again, stored, replaced", r"(\d+) facts are not stored because they were said again, (\d+) are\s+stored and (\d+) are replaced",
              (total("said_again"), total("stored"), total("replaced"))),
        Claim("0018", "replay: evidence-session facts replaced by a filler", r"of the (\d+) facts from evidence sessions, (\d+) are replaced with another value",
              (total("evidence_session_facts"), total("replaced_by_filler"))),
        Claim("0018", "replay: the answer's rank and whether it is shown", r"among the first (\w+) in all (\d+) histories and is shown in all (\d+)",
              (max(r["answer_rank_turn"] or 999 for r in replays), len(replays), sum(r["answer_shown_turn"] for r in replays))),
        Claim("0018", "replay: facts shown, facts that hold", r"holds (\d+) to (\d+) of the (\d+) to (\d+) facts that hold", span("shown") + span("held")),
        Claim("0018", "replay: tokens of the facts that hold", r"which count ([\d,]+) to ([\d,]+) tokens in all", span("held_tokens")),
        Claim("0018", "replay: the facts message stays within F", r"counts at most F = ([\d,]+) tokens",
              all(r["shown_tokens"] <= FACT_TOKENS for r in replays), note=f"{fmt(span('shown_tokens'))} tokens shown"),
        Claim("0018", "replay: evidence consolidated", r"that is (\d+) of the\s+(\d+) evidence turns",
              (total("evidence_consolidated"), total("evidence_turns"))),
        Claim("0018", "replay: facts shown, against precision", r"(\d+) to (\d+) of them in the replay", span("shown")),
        Claim("0018", "no subject but user in round three", r"If the model named a person, two people of one name would share a node\. In round three it never did",
              three["user_subject"] == three["facts"]),
        Claim("0018", "…two people share a value node in 5c40ec5b", r"in `5c40ec5b`, the friend Alex and the partner Alex",
              {"friend_name", "home_buying_partner"} <= f["alex"], note="the relations whose value is Alex: " + ", ".join(sorted(f["alex"]))),
        Claim("0018", "the list given to a call", r"at\s+most (\d+) facts in the spike", (three["most_shown"],)),
        Claim("0018", "facts not said by the user; assistant turns", r"(\d+) of\s+the (\d+) facts of round three have no word of their value.*and (\d+) point at an assistant turn",
              (f["unsaid"], three["facts"], three["assistant_turn"])),
        Claim("0018", "the overwrite with the prompt chosen", r"found the changed value in (\d+) of the (\d+) spike histories",
              (len(kept[3]), f["unmeasured"]), note=MARKERS),
        Claim("0018", "…both values shown in 9ea5eabc", r"`recent_family_trip = Hawaii` stands next to `recent_trip = family trip to Paris`",
              {"user / recent_family_trip = Hawaii", "user / recent_trip = family trip to Paris"} <= set(paris)),
        Claim("0018", "the ranking's 8 of 8 is in sample", r"The 8 of 8 for the ranking is measured on the same eight histories",
              all(r["answer_shown_turn"] for r in replays) and len(replays) == 8),
        Claim("0018", "facts sharing no term with the question", r"(\d+) of the (\d+) facts that hold share none, against (\d+) on the line alone",
              (total("no_term_turn"), total("held"), total("no_term_line"))),
        Claim("0018", "no single-session-user history in the spike", r"The spike had no `single-session-user` history", f["unmeasured_ssu"] == 0),
        Claim("0018", "names differ between rounds", r"(\w+) of the eight changed values kept their name in round two and lost it in round three \(`(\w{8})`, `(\w{8})` and `(\w{8})`\)",
              (len(lost), *lost), note=MARKERS),
        Claim("0018", "a question for the earlier value, by hand", r"one of the eight spike questions is of that kind", kind="external",
              note="dfde3500, " + HAND),
        Claim("0018", "round three's cost", r"cost \$(\d+\.\d+) for the eight histories, about \$(\d+\.\d+) a history",
              (f"{three['cost']:.4f}", f"{three['cost'] / f['unmeasured']:.3f}")),
        Claim("0018", "…tokens per call", r"([\d,]+) tokens in and (\d+) out per call", (round(three["tokens_in"]), round(three["tokens_out"]))),
        Claim("0018", "the three rounds' cost", r"The three rounds cost \$(\d+\.\d+) together", (f"{f['spike_cost']:.2f}",)),
    ]


def claims_0019(f: dict) -> list[Claim]:
    p, three = f["pilot"], f[3]
    left = 101.00 - 26.90 - f["spike_cost"]  # the three external figures the record states
    return [
        Claim("0019", "the pilot's questions", r"The first ten questions of each type.*are the (\d+) of the M1 pilot", (p["questions"],)),
        Claim("0019", "RecentTurnsMemory on the 20", r"`RecentTurnsMemory` answered (\d+) of 10 `single-session-user`\s+and (\d+) of 10 `knowledge-update`",
              p["correct"]["recent-turns"]),
        Claim("0019", "RetrievalMemory on the 20", r"`RetrievalMemory`\s+(\d+) and (\d+)", p["correct"]["retrieval"]),
        Claim("0019", "ConsolidatingMemory on the 20", r"`ConsolidatingMemory` (\d+) and (\d+)", p["correct"]["consolidating"]),
        Claim("0019", "the repeat of the pilot", r"agreed with the M1 pilot on (\d+) of the same (\d+) questions", (p["repeat_agrees"], p["repeat_of"])),
        Claim("0019", "round three's calls and cost", r"made (\d+) extraction calls for \$(\d+\.\d+)", (three["calls"], f"{three['cost']:.4f}")),
        Claim("0019", "sessions: the 20 histories, list order", r"histories hold (\d+) sessions.*adds (\d+) more", (p["pilot_sessions"], p["list_order"])),
        Claim("0019", "an answer and its grading", r"answer cost \$(\d+\.\d+) a question and its grading \$(\d+\.\d+)",
              (f"{p['answer']:.4f}", f"{p['grade']:.4f}")),
        Claim("0019", "spent at M3's close", r"measurement at \$(\d+\.\d+) when M3 closed", kind="external", note="docs/vg-project.md"),
        Claim("0019", "the spike's cost", r"the\s+spike cost \$(\d+\.\d+) by its own count", (f"{f['spike_cost']:.2f}",)),
        Claim("0019", "the cap", r"0010's cap of \$(\d+\.\d+)", kind="external", note="ADR 0010; evals/estimate_cost.py --check"),
        Claim("0019", "credits left", r"read \$(\d+\.\d+) of credits left", kind="external", note="the author's reading on OpenRouter, 2026-10-05"),
        Claim("0019", "a share at ten questions", r"one question moves a\s+share by ([\d.]+)", (1 / PILOT_PER_TYPE,)),
        Claim("0019", "the repeat changed one answer", r"a repeat of the same 20 questions changed (\w+) answer", (p["repeat_of"] - p["repeat_agrees"],)),
        Claim("0019", "the pilot's estimate", r"estimated at \$(\d+\.\d+)\. Its two parts, each rounded, are \$(\d+\.\d+) for the extraction.*and \$(\d+\.\d+) for the answers",
              (f"{p['pilot']:.2f}", f"{p['extraction']:.2f}", f"{p['answers']:.2f}"),
              note="round three's cost per call on every session, the retrieval run's answer and grading"),
        Claim("0019", "all 122, estimated", r"All 122 are\s+estimated at \$(\d+\.\d+)", (f"{p['every']:.2f}",)),
        Claim("0019", "shared filler sessions", r"share (\d+) filler sessions with these 20", (f["shared"]["shared_pilot"],)),
        Claim("0019", "when the other rows were run", r"rows from runs made on (\d+) and (\d+) October", tuple(p["run_days"])),
        Claim("0019", "both estimates against the cap", r"under a\s+tenth of what is left under the cap", (p["pilot"] + p["every"]) / left < 0.1,
              note=f"${p['pilot'] + p['every']:.2f} of ${left:.2f}"),
    ]


def print_facts(f: dict) -> None:
    """Rounds two and three under ADR 0018's rule, side by side: the totals, then each history."""
    rounds = {"round two": f["replays_two"], "round three": f["replays"]}
    total = lambda rs, key: sum(r[key] for r in rs)  # noqa: E731
    span = lambda rs, key: f"{min(r[key] for r in rs):,} to {max(r[key] for r in rs):,}"  # noqa: E731
    of = lambda rs, key, whole: f"{total(rs, key)} of {total(rs, whole)}"  # noqa: E731

    def names(rs: list[dict]) -> str:
        relations = sum((r["relations"] for r in rs), Counter())
        return ", ".join(f"{k} {v}" for k, v in relations.most_common(3)) or "—"

    lines = [
        ("facts in the replies", lambda rs: total(rs, "stored") + total(rs, "said_again")),
        ("not stored, said again", lambda rs: total(rs, "said_again")),
        ("stored", lambda rs: total(rs, "stored")),
        ("replaced", lambda rs: total(rs, "replaced")),
        ("… most in one history", lambda rs: max(r["replaced"] for r in rs)),
        ("facts from an evidence turn, replaced", lambda rs: of(rs, "evidence_turn_replaced", "evidence_turn_facts")),
        ("… of them by a fact from an evidence turn", lambda rs: total(rs, "evidence_to_evidence")),
        ("facts from an evidence turn, shown", lambda rs: of(rs, "evidence_turn_shown", "evidence_turn_facts")),
        ("facts from evidence sessions replaced with another", None),
        ("  value by a session without evidence", lambda rs: of(rs, "replaced_by_filler", "evidence_session_facts")),
        ("facts that hold at the question, per history", lambda rs: span(rs, "held")),
        ("… their tokens", lambda rs: span(rs, "held_tokens")),
        ("facts shown, per history", lambda rs: span(rs, "shown")),
        (f"… their tokens, against F = {FACT_TOKENS}", lambda rs: span(rs, "shown_tokens")),
        ("answer's fact has a score, ranked on its line", lambda rs: f"{sum(r['answer_rank_line'] is not None for r in rs)} of {len(rs)}"),
        ("answer's fact shown, ranked on line and turn", lambda rs: f"{sum(r['answer_shown_turn'] for r in rs)} of {len(rs)}"),
        ("… its worst rank, where it holds", lambda rs: max(r["answer_rank_turn"] for r in rs if r["answer_rank_turn"])),
        ("evidence turns whose session gave a fact shown", lambda rs: of(rs, "evidence_consolidated", "evidence_turns")),
    ]
    print("the saved replies under ADR 0018's rule; round two's replaces-numbers are left aside")
    print(f"  {'':52s} " + "".join(f"{name:>18s}" for name in rounds))
    for label, value in lines:
        print(f"  {label:52s} " + ("" if value is None else "".join(f"{str(value(rs)):>18s}" for rs in rounds.values())))
    for name, rs in rounds.items():
        print(f"  the names that replace most, {name}: {names(rs)}")
    print()
    for name, rs in rounds.items():
        print(f"facts from an evidence turn that are replaced, {name}")
        for r in rs:
            for old, new, from_evidence in r["evidence_turn_pairs"]:
                print(f"  {r['qid']}: {old}  ->  {new}" + ("  (from an evidence turn)" if from_evidence else ""))
        print()
    for name, rs in rounds.items():
        print(f"per history, {name}")
        for r in rs:
            print(f"  {r['qid']}: stored {r['stored']}, said again {r['said_again']}, replaced {r['replaced']}, hold {r['held']} "
                  f"({r['held_tokens']:,} tokens); shown {r['shown']} of {r['matching']} matching ({r['shown_tokens']} tokens); "
                  f"answer at rank {r['answer_rank_turn']} (on the line alone: {r['answer_rank_line']}), "
                  f"{'shown' if r['answer_shown_turn'] else 'NOT shown'}; "
                  f"evidence consolidated {r['evidence_consolidated']} of {r['evidence_turns']}")
        print()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    raw = adr_text("0018")
    f = compute(raw)
    if "--facts" in args:
        print_facts(f)
    checks = [(c, re.sub(r"\s+", " ", raw)) for c in claims_0018(f)]
    checks += [(c, re.sub(r"\s+", " ", adr_text("0019"))) for c in claims_0019(f)]
    for c, body in checks:
        judge(c, body)
        print(f"{c.adr} {c.status:12s} {c.label:52s} text {fmt(c.groups) if c.groups else '—':40s} "
              f"computed {fmt(c.computed)}{'  ' + c.note if c.note else ''}")
    tally = Counter(c.status for c, _ in checks)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
