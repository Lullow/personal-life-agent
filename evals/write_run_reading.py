"""Write a run's rows out for reading by hand, as ADR 0008 requires.

The rows name the evidence and the recalled records by id only. This joins them
with the dataset, so each question can be judged from the text: what the
evidence says and whether it reached the context, what the model answered and
how it was graded, and what the conversation it was continuing asked of it.
The file goes under data/, which git ignores. Nothing is truncated.

Per question it shows the evidence turns in replay order, each marked with
whether it was in the context; the first turn in the context of every session
there, which is where a filler conversation says what it wants of the
assistant; and the last messages before the question. --full-context prints
every message the model saw instead.

For the fact graph (ADR 0018) it also shows the facts message the model saw
first, and, when evals/export_fact_graphs.py has written the run's facts next
to its rows, every fact of the evidence sessions with whether it was shown and
whether it holds, and every fact that was replaced with what replaced it.
--all-facts lists every fact of the history instead of the evidence sessions'.

    .venv/bin/python evals/write_run_reading.py evals/results/<run>.jsonl
    .venv/bin/python evals/write_run_reading.py evals/results/<run>.jsonl --only 0f05491a --full-context
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import KU, ROOT, build_records, load_pinned  # noqa: E402
from life_agent.agent.memory import MemoryRecord  # noqa: E402

OUT = ROOT / "data" / "longmemeval"
TAIL = 4  # messages shown from the end of the context


def fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def text_block(content: str) -> list[str]:
    f = fence(content)
    return [f + "text", content, f, ""]


def turn_index(record: MemoryRecord) -> int:
    return int(record.id.rsplit(":", 1)[1])


def exported_facts(rows_path: Path) -> dict[str, list[dict]]:
    """The facts evals/export_fact_graphs.py wrote for this run, by tag; empty when it has not."""
    path = rows_path.with_name(f"{rows_path.stem}-facts.jsonl")
    by_tag: dict[str, list[dict]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            fact = json.loads(line)
            by_tag.setdefault(fact["tag"], []).append(fact)
    return by_tag


def line_of(fact: dict) -> str:
    return f"{fact['subject']} / {fact['relation']} = {fact['value']}"


def fact_sections(r: dict, facts: list[dict], all_facts: bool) -> list[str]:
    """ADR 0019's questions for a reading: was the value among the facts, was it shown, was the old one replaced."""
    by_id = {f["id"]: f for f in facts}
    shown, evidence = set(r["sources"]), set(r["evidence"])
    evidence_sessions = {i.rsplit(":", 1)[0] for i in evidence}

    def entry(f: dict) -> str:
        state = "holds"
        if f["replaced_by"]:
            by = by_id[f["replaced_by"]]
            state = f"REPLACED {f['replaced_at'][:10]} by `{line_of(by)}` (from {by['turn_id']})"
        named = f["turn_id"] + (", an evidence turn" if f["turn_id"] in evidence else "")
        return f"- {'SHOWN' if f['id'] in shown else 'not shown'}; {state}; stored {f['at'][:10]}, names {named}: `{line_of(f)}`"

    chosen = facts if all_facts else [f for f in facts if f["session_id"] in evidence_sessions]
    title = "Every fact of the history" if all_facts else "The facts of the evidence sessions"
    lines = [f"### {title}, in the order stored", ""]
    lines += [entry(f) for f in chosen] or ["None."]
    replaced = [f for f in facts if f["replaced_by"]]
    lines += ["", "### Every fact that was replaced when the question was asked", ""]
    lines += [entry(f) for f in replaced] or ["None."]
    return lines + [""]


def question_section(n: int, r: dict, x: dict, full_context: bool, facts: list[dict] | None = None,
                     all_facts: bool = False) -> list[str]:
    records = {rec.id: rec for rec in build_records(x, "clock")[0]}  # replay order
    date_of = dict(zip(x["haystack_session_ids"], x["haystack_dates"]))
    context = set(r["sources"])
    evidence = [i for i in records if i in set(r["evidence"])]
    lines = [
        f"## {n}. {r['question_id']}: {r['question_type']}, position {r['position']}", "",
        f"- question date: {r['question_date']}",
        f"- question: {r['question']}",
        f"- gold answer: {r['gold_answer']}",
        f"- model answer: {r['answer']}",
        f"- verdict: {r['verdict']}; correct: {r['correct']}; status: {r['status']}",
        f"- evidence reached: {r['evidence_reached']}; recall {r['recall']:.2f}"
        + (f"; breakdown: {r['ku_breakdown']}" if r["ku_breakdown"] else ""),
        # A facts message is one message with an id per fact, so a row since ADR 0018 counts its messages itself.
        f"- context: {r.get('messages') or len(r['sources'])} messages, {r['tokens_used']:,} tokens; "
        f"{r['distance_tokens']:,} tokens between the newest evidence and the question"
        + (" (long-term)" if r["long_term"] else ""),
    ]
    if r.get("summary") is not None:
        # ADRs 0013, 0015–0017: the consolidating strategy's row carries the notes the model saw.
        lines += [
            f"- consolidated: evidence read by the consolidator {r['evidence_consolidated']:.2f}"
            + (f"; breakdown with the notes: {r['ku_breakdown_consolidated']}" if r.get("ku_breakdown_consolidated") else "")
            + f"; {r['consolidations']} consolidations, {r['summary_reasked']} asked again, "
            f"{r['summary_truncated']} cut, {r['consolidations_failed']} skipped; notes {r['summary_tokens']:,} tokens",
        ]
    if r.get("facts_stored") is not None:
        # ADRs 0018, 0019: the fact graph's row carries the facts message the model saw and what the graph held.
        lines += [
            f"- fact graph: {r['facts_stored']} facts stored, {r['facts_replaced']} replaced, {r['facts_held']} held, "
            f"{r['facts_shown']} shown in {r['facts_message_tokens']:,} tokens; {r['facts_said_again']} said again, "
            f"{r['entries_dropped']} entries dropped, {r['extractions_failed']} of {r['extractions']} sessions skipped",
            f"- facts naming an evidence turn: {r['evidence_turn_facts']}, {r['evidence_turn_facts_replaced']} replaced, "
            f"{r['evidence_turn_facts_shown']} shown; evidence turns whose session gave a fact shown "
            f"{r['evidence_consolidated']:.2f}"
            + (f"; breakdown with the facts: {r['ku_breakdown_consolidated']}" if r.get("ku_breakdown_consolidated") else ""),
        ]
    lines += ["", "### Evidence, in replay order", ""]
    sessions = list(dict.fromkeys(records[i].session_id for i in evidence))
    which = dict(zip(sessions, ("earlier", "later"))) if x["question_type"] == KU and len(sessions) == 2 else {}
    for i in evidence:
        rec = records[i]
        where = "IN CONTEXT" if i in context else "not in context"
        label = f", {which[rec.session_id]} session" if which else ""
        lines += [f"#### {i}, {rec.role}{label}: {where}", "",
                  f"Session date {date_of[rec.session_id]}.", ""] + text_block(rec.content)

    seen = [records[i] for i in r["sources"] if i in records]  # a summary's id is not a turn
    if r.get("summary") is not None:
        lines += ["### The notes the model saw first, as one assistant message (ADR 0015)", ""] + text_block(r["summary"])

    if r.get("facts_message") is not None:
        lines += ["### The facts the model saw first, as one assistant message (ADR 0018)", ""] + text_block(r["facts_message"])
    if facts is not None:
        lines += fact_sections(r, facts, all_facts)
    elif r.get("graph_tag"):
        lines += ["The run's facts are not exported: evals/export_fact_graphs.py writes them next to the rows.", ""]

    def message(rec: MemoryRecord) -> list[str]:
        mark = " (evidence)" if rec.id in r["evidence"] else ""
        return [f"#### {rec.id}, {rec.role}{mark}", ""] + text_block(rec.content)

    if full_context:
        lines += ["### Everything the model saw, oldest first", ""]
        for rec in seen:
            lines += message(rec)
        return lines

    lines += ["### Sessions in the context, by their first turn there", ""]
    for sid in dict.fromkeys(rec.session_id for rec in seen):
        in_context = [rec for rec in seen if rec.session_id == sid]
        first = in_context[0]
        cut = "" if turn_index(first) == 0 else "; the session starts before the context does"
        lines += [f"#### {sid}, {date_of[sid]}: {len(in_context)} messages in the context{cut}", "",
                  f"First turn there: {first.id}, {first.role}.", ""] + text_block(first.content)
    lines += [f"### The last {TAIL} messages before the question", ""]
    for rec in seen[-TAIL:]:
        lines += message(rec)
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", type=Path, help="a run's JSON lines file")
    ap.add_argument("--only", help="comma-separated question ids, in the order to read them")
    ap.add_argument("--full-context", action="store_true", help="every message the model saw")
    ap.add_argument("--all-facts", action="store_true", help="every fact of the history, not only the evidence sessions'")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    rows = [json.loads(line) for line in args.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.only:
        wanted = args.only.split(",")
        missing = set(wanted) - {r["question_id"] for r in rows}
        if missing:
            raise SystemExit(f"not in {args.rows.name}: {', '.join(sorted(missing))}")
        rows = sorted((r for r in rows if r["question_id"] in wanted), key=lambda r: wanted.index(r["question_id"]))
    by_id = {x["question_id"]: x for x in load_pinned()}
    facts = exported_facts(args.rows)

    first = rows[0]
    lines = [f"# Reading {args.rows.name}", "",
             f"Strategy {first['strategy']}, model {first['model']}, commit {first['commit']}"
             + (", DRY RUN" if first["dry_run"] else "") + ".", "",
             "| # | question | type | reached | breakdown | verdict | correct |",
             "|---|---|---|---|---|---|---|"]
    for n, r in enumerate(rows, start=1):
        kind = "SSU" if r["question_type"] != KU else "KU"
        lines.append(f"| {n} | {r['question_id']} | {kind} | {r['evidence_reached']} | "
                     f"{r['ku_breakdown'] or ''} | {r['verdict']} | {r['correct']} |")
    lines.append("")
    for n, r in enumerate(rows, start=1):
        lines += question_section(n, r, by_id[r["question_id"]], args.full_context,
                                  facts.get(r.get("graph_tag") or ""), args.all_facts)

    suffix = (("-" + "-".join(wanted) if args.only else "") + ("-full" if args.full_context else "")
              + ("-all-facts" if args.all_facts else ""))
    out = args.out or OUT / f"reading-{args.rows.stem}{suffix}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} questions: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
