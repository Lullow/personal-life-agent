"""Write a question out as every measured strategy met it, side by side.

write_run_reading.py takes one run and shows everything its model saw. This
takes one question and puts the runs of results_table.RUNS next to each other:
the evidence, whether each strategy got it into the context, what the model
answered and how it was graded, and the notes ConsolidatingMemory showed first.
It reads the committed rows and the pinned dataset, calls no model and measures
nothing. The file goes under data/, which git ignores. Nothing is truncated.

    .venv/bin/python evals/write_question_comparison.py c8c3f81d
    .venv/bin/python evals/write_question_comparison.py c8c3f81d 3ba21379 4b24c848
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.results_table import NAMES, RUNS, rows  # noqa: E402
from evals.verify_adr_numbers import KU, ROOT, build_records, load_pinned  # noqa: E402

OUT = ROOT / "data" / "longmemeval"


def quote(text: str) -> list[str]:
    """A block quote wraps on a shared screen, where a code block scrolls sideways."""
    return [f"> {line}" for line in text.splitlines()] + [""]


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def question_section(x: dict, by_run: dict[str, dict]) -> list[str]:
    first = next(iter(by_run.values()))
    records = {rec.id: rec for rec in build_records(x, "clock")[0]}  # replay order
    date_of = dict(zip(x["haystack_session_ids"], x["haystack_dates"]))
    evidence = [i for i in records if i in set(first["evidence"])]
    sessions = list(dict.fromkeys(records[i].session_id for i in evidence))
    which = dict(zip(sessions, ("earlier", "later"))) if x["question_type"] == KU and len(sessions) == 2 else {}

    def label(i: str) -> str:
        return f", {which[records[i].session_id]} session" if which else ""

    lines = [
        f"## {first['question_id']}: {first['question_type']}", "",
        f"- question date: {first['question_date']}",
        f"- question: {first['question']}",
        f"- gold answer: {first['gold_answer']}",
        f"- {first['distance_tokens']:,} tokens between the newest evidence and the question"
        + (" (long-term)" if first["long_term"] else ""),
        "", "### Evidence, in replay order", "",
    ]
    for i in evidence:
        rec = records[i]
        lines += [f"#### {i}, {rec.role}{label(i)}, {date_of[rec.session_id]}", ""] + quote(rec.content)

    table = [("", [NAMES[name] for name in by_run])]
    for i in evidence:
        table.append((f"{i}{label(i)}: in context", ["yes" if i in r["sources"] else "no" for r in by_run.values()]))
    table += [
        ("context", [f"{len(r['sources'])} messages, {r['tokens_used']:,} tokens" for r in by_run.values()]),
        # ADR 0013: only the consolidating strategy's row says what its consolidator read.
        ("evidence read by the consolidator",
         [f"{r['evidence_consolidated']:.2f}" if r.get("summary") is not None else "" for r in by_run.values()]),
        ("model answer", [r["answer"] for r in by_run.values()]),
        ("verdict", [f"{r['verdict']}; correct: {r['correct']}" for r in by_run.values()]),
    ]
    lines += ["### The strategies", ""]
    for n, (name, cells) in enumerate(table):
        lines.append("| " + " | ".join(cell(c) for c in (name, *cells)) + " |")
        if n == 0:
            lines.append("|---" * (len(cells) + 1) + "|")
    lines.append("")

    for name, r in by_run.items():
        if r.get("summary") is None:
            continue
        lines += [
            f"### The notes {NAMES[name]} showed first, as one assistant message (ADR 0015)", "",
            f"{r['summary_tokens']:,} tokens; {r['consolidations']} consolidations, {r['summary_reasked']} asked again, "
            f"{r['summary_truncated']} cut, {r['consolidations_failed']} skipped.", "",
        ] + quote(r["summary"])
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("questions", nargs="+", help="question ids, in the order to read them")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    runs = {name: {r["question_id"]: r for r in rows(name)} for name in RUNS}
    for name, by_question in runs.items():
        missing = set(args.questions) - set(by_question)
        if missing:
            raise SystemExit(f"not in {RUNS[name]}: {', '.join(sorted(missing))}")
    by_id = {x["question_id"]: x for x in load_pinned()}

    lines = ["# One question, every strategy", ""]
    for name, by_question in runs.items():
        r = by_question[args.questions[0]]
        lines.append(f"- {NAMES[name]}: {RUNS[name]}, model {r['model']}, commit {r['commit']}")
    lines.append("")
    for q in args.questions:
        lines += question_section(by_id[q], {name: by_question[q] for name, by_question in runs.items()})

    out = args.out or OUT / f"comparison-{'-'.join(args.questions)}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(args.questions)} questions: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
