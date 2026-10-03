"""Recompute the figures in ADR 0012 from the pinned dataset and the M2 rows.

The figures describe the sessions the consolidator will read: how many there
are, how large the largest is, how many calls the two replay orders take, and
what ADR 0010's cost model says for the design. Nothing here consolidates
anything.

    .venv/bin/python evals/verify_adr_0012.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import CHOSEN_N, CONSOLIDATOR, ORDER_REPLAYS, PROMPT, compute as cost  # noqa: E402
from evals.longmemeval import load_questions  # noqa: E402
from evals.verify_adr_numbers import (  # noqa: E402
    ADR_DIR, KU, TYPES, Claim, TiktokenCounter, build_records, fmt, judge, load_pinned,
)

RESULTS = Path(__file__).resolve().parent / "results"
M2_RUNS = ("retrieval-20261002-193417.jsonl", "recent-turns-20261002-193902.jsonl")
SUMMARY_TOKENS = 1000  # the S ADR 0012 fixes
WORDS_ASKED = 750      # what the prompt asks the model for


def adr_text() -> str:
    paths = sorted(ADR_DIR.glob("0012-*.md"))
    if not paths:
        raise SystemExit("no ADR 0012 to check")
    return paths[0].read_text(encoding="utf-8")


def system_prompt(text: str) -> str:
    """The first fenced block after "The system prompt is:", as the record states it."""
    m = re.search(r"The system\s+prompt is:\s*```\n(.*?)```", text, re.DOTALL)
    if m is None:
        raise SystemExit("ADR 0012 has no system prompt block")
    return m.group(1).strip()


def compute(text: str) -> dict:
    data = {x["question_id"]: x for x in load_pinned()}
    lists = load_questions(CHOSEN_N)
    counter = TiktokenCounter()
    sessions_per_history: list[int] = []
    largest_session = largest_history = 0
    words = tokens = 0
    for t in TYPES:
        for qid in lists[t][:CHOSEN_N]:
            records, ends, _ = build_records(data[qid], "clock")
            sessions_per_history.append(len(ends))
            sizes = [counter.count(r.content) for r in records]
            largest_history = max(largest_history, sum(sizes))
            words += sum(len(r.content.split()) for r in records)
            tokens += sum(sizes)
            start = 0
            for end in sorted(ends):
                largest_session = max(largest_session, sum(sizes[start:end]))
                start = end
    list_order = sum(len(build_records(data[q], "clock")[1]) for q in lists[KU][:ORDER_REPLAYS])
    calls_per_run = []
    for name in M2_RUNS:
        rows = [json.loads(line) for line in (RESULTS / name).read_text(encoding="utf-8").splitlines()]
        calls_per_run.append(sum(len(r["calls"]) for r in rows))
    c = cost()
    design = c["grid"][(CHOSEN_N, CONSOLIDATOR, SUMMARY_TOKENS)]
    return dict(histories=len(sessions_per_history), sessions=sum(sessions_per_history),
                sessions_min=min(sessions_per_history), sessions_max=max(sessions_per_history),
                largest_session=largest_session, largest_history=largest_history,
                clock_calls=sum(sessions_per_history), list_calls=list_order,
                calls_per_m2_run=calls_per_run, prompt_tokens=counter.count(system_prompt(text)),
                words_to_tokens=WORDS_ASKED * tokens / words,
                consolidate=design["consolidate"], total=design["total"], share=design["share"],
                gpt4o_500_share=c["grid"][(CHOSEN_N, "gpt-4o-2024-08-06", 500)]["share"],
                check=c["check"][SUMMARY_TOKENS])


def claims(f: dict) -> list[Claim]:
    return [
        Claim("0012", "histories measured", r"Measured on the (\d+) histories of 0010", (f["histories"],)),
        Claim("0012", "sessions: total, min, max", r"([\d,]+) sessions, (\d+) to (\d+) per history",
              (f["sessions"], f["sessions_min"], f["sessions_max"])),
        Claim("0012", "largest session / history", r"largest session holds ([\d,]+) tokens and the largest history ([\d,]+)",
              (f["largest_session"], f["largest_history"])),
        Claim("0012", "context length", r"takes ([\d,]+) tokens of context", kind="external",
              note="OpenRouter /api/v1/models, 2026-10-03"),
        Claim("0012", "prices in / out", r"\$([\d.]+) per million input tokens and \$([\d.]+) per million output",
              kind="external", note="OpenRouter /api/v1/models, 2026-10-03"),
        Claim("0012", "instruction shorter than 0010's", r"instruction is shorter than its (\d+) tokens",
              f["prompt_tokens"] < PROMPT, note=f"prompt counts {f['prompt_tokens']} tokens"),
        Claim("0012", "750 words is about 1000 tokens", r"asks for (\d+) words, about ([\d,]+) tokens",
              (WORDS_ASKED, f["words_to_tokens"]), kind="approx",
              note=f"{f['words_to_tokens']:.0f} tokens at the dataset's words-per-token"),
        Claim("0012", "tokens per word in the dataset", r"this dataset's ([\d.]+) tokens per word",
              (round(f["words_to_tokens"] / WORDS_ASKED, 1),)),
        Claim("0012", "consolidation / total / share at S=1000",
              r"puts consolidation at \$([\d.]+) and the whole comparison at \$([\d.]+), (\d+)% of the cap",
              (f"{f['consolidate']:.2f}", f"{f['total']:.2f}", round(100 * f["share"]))),
        Claim("0012", "gpt-4o at S=500, share of cap", r"fits the cap only with S = 500, at (\d+)%",
              (round(100 * f["gpt4o_500_share"]),)),
        Claim("0012", "rewrites a first-session fact survives", r"survived up to (\d+) rewrites",
              (f["sessions_max"] - 1,)),
        Claim("0012", "gpt-4o check at S=1000", r"\$([\d.]+) at S = 1000", (f"{f['check']:.2f}",)),
        Claim("0012", "consolidation calls: all, clock, list",
              r"([\d,]+) consolidation calls, ([\d,]+) in clock order and ([\d,]+) in list order",
              (f["clock_calls"] + f["list_calls"], f["clock_calls"], f["list_calls"])),
        Claim("0012", "calls per M2 run", r"against ([\d,]+) calls in each of M2's two runs",
              (f["calls_per_m2_run"][0],), note=f"runs: {f['calls_per_m2_run']}"),
        Claim("0012", "both M2 runs made the same number of calls", r"in each of M2's two runs",
              len(set(f["calls_per_m2_run"])) == 1),
    ]


def main() -> int:
    raw = adr_text()
    text = re.sub(r"\s+", " ", raw)
    cs = claims(compute(raw))
    for c in cs:
        judge(c, text)
        print(f"{c.status:12s} {c.label:44s} text {fmt(c.groups) if c.groups else '—':34s} "
              f"computed {fmt(c.computed)}{'  ' + c.note if c.note else ''}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
