"""Recompute the figures in ADR 0015 from the pinned dataset, the M2 rows and the smoke test.

The figures describe the sessions the consolidator will read: how many there
are, how large the largest is, how many calls the two replay orders take, and
what ADR 0010's cost model says for the design. Nothing here consolidates
anything.

    .venv/bin/python evals/verify_adr_0015.py
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
from life_agent.agent.memory import CONSOLIDATION_SYSTEM_PROMPT, SUMMARY_TARGET_TOKENS  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
M2_RUNS = ("retrieval-20261002-193417.jsonl", "recent-turns-20261002-193902.jsonl")
SMOKE = "consolidating-20261003-192859-smoke.jsonl"  # the run under 0012 that 0015 reopens it for
SECONDS_PER_CALL = 8  # the six-session check under the stricter prompt, measured in session
SUMMARY_TOKENS = 1000  # the S ADR 0012 fixes
WORDS_ASKED = 750      # what the prompt asks the model for


def adr_text() -> str:
    paths = sorted(ADR_DIR.glob("0015-*.md"))
    if not paths:
        raise SystemExit("no ADR 0015 to check")
    return paths[0].read_text(encoding="utf-8")


def system_prompt(text: str) -> str:
    """The first fenced block after "The system prompt is:", as the record states it."""
    m = re.search(r"The system\s+prompt is:\s*```\n(.*?)```", text, re.DOTALL)
    if m is None:
        raise SystemExit("ADR 0015 has no system prompt block")
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
    smoke = json.loads((RESULTS / SMOKE).read_text(encoding="utf-8").splitlines()[0])
    outs = [k["output_tokens"] for k in smoke["calls"] if k["label"] == "consolidate"]
    c = cost()
    design = c["grid"][(CHOSEN_N, CONSOLIDATOR, SUMMARY_TOKENS)]
    return dict(histories=len(sessions_per_history), sessions=sum(sessions_per_history),
                sessions_min=min(sessions_per_history), sessions_max=max(sessions_per_history),
                largest_session=largest_session, largest_history=largest_history,
                clock_calls=sum(sessions_per_history), list_calls=list_order,
                calls_per_m2_run=calls_per_run, prompt_tokens=counter.count(system_prompt(text)),
                prompt_in_code=system_prompt(text) == CONSOLIDATION_SYSTEM_PROMPT,
                words_to_tokens=WORDS_ASKED * tokens / words,
                consolidate=design["consolidate"], total=design["total"], share=design["share"],
                gpt4o_500_share=c["grid"][(CHOSEN_N, "gpt-4o-2024-08-06", 500)]["share"],
                check=c["check"][SUMMARY_TOKENS],
                smoke_id=smoke["question_id"], smoke_calls=len(outs), smoke_first=outs[0], smoke_last=outs[-1],
                smoke_growth=(outs[-1] - outs[0]) / (len(outs) - 1), smoke_summary=smoke["summary_tokens"],
                smoke_sources=len(smoke["sources"]), smoke_over=smoke["over_budget"], smoke_correct=smoke["correct"],
                smoke_cost=smoke["strategy_cost_usd"],
                hours_one_thread=(sum(sessions_per_history) + list_order) * SECONDS_PER_CALL / 3600)


def claims(f: dict) -> list[Claim]:
    return [
        Claim("0015", "sessions: total, min, max", r"the ([\d,]+) sessions in the (\d+) histories, (\d+) to (\d+) per history",
              (f["sessions"], f["histories"], f["sessions_min"], f["sessions_max"])),
        Claim("0015", "largest session / history", r"largest session at ([\d,]+) tokens and the largest history at (\d[\d,]*\d)",
              (f["largest_session"], f["largest_history"])),
        Claim("0015", "context length", r"the ([\d,]+)-token context of the model", kind="external",
              note="OpenRouter /api/v1/models, 2026-10-03"),
        Claim("0015", "prices in / out", r"prices of \$([\d.]+) and \$([\d.]+) per million tokens",
              kind="external", note="OpenRouter /api/v1/models, 2026-10-03"),
        Claim("0015", "smoke test: question, sessions", r"On `([0-9a-f]{8})`, (\d+) sessions",
              (f["smoke_id"], f["smoke_calls"])),
        Claim("0015", "smoke test: growth per session", r"grew by about (\d+) tokens a session",
              (round(f["smoke_growth"]),), kind="approx"),
        Claim("0015", "smoke test: first and last output", r"([\d,]+) tokens after the first and ([\d,]+) after the last",
              (f["smoke_first"], f["smoke_last"])),
        Claim("0015", "smoke test: summary shown", r"the summary shown to the answering model held ([\d,]+) tokens",
              (f["smoke_summary"],)),
        Claim("0015", "smoke test: window empty, over budget, right",
              r"the window was empty, `sources` held one id, and the row was over budget. The answer was right",
              f["smoke_sources"] == 1 and f["smoke_over"] and f["smoke_correct"] is True),
        Claim("0015", "smoke test: cost of the question", r"cost \$([\d.]+) for the question",
              (f"{f['smoke_cost']:.2f}",)),
        Claim("0015", "six-session check", r"from 630 to 2,165 tokens .* from 121 to 664 tokens", kind="external",
              note="measured in session 2026-10-03, not reproducible: the model is not deterministic"),
        Claim("0015", "the prompt in code is the record's", r"The system\s+prompt is:",
              f["prompt_in_code"], note="memory.CONSOLIDATION_SYSTEM_PROMPT"),
        Claim("0015", "S in code is the record's", r"The size S is ([\d,]+) tokens", (SUMMARY_TARGET_TOKENS,),
              note="memory.SUMMARY_TARGET_TOKENS"),
        Claim("0015", "750 words is about 1000 tokens", r"asks for (\d+) words, about ([\d,]+) tokens",
              (WORDS_ASKED, f["words_to_tokens"]), kind="approx",
              note=f"{f['words_to_tokens']:.0f} tokens at the dataset's words-per-token"),
        Claim("0015", "tokens per word in the dataset", r"this dataset's ([\d.]+) tokens per word",
              (round(f["words_to_tokens"] / WORDS_ASKED, 1),)),
        Claim("0015", "prompt tokens (information)", r"The system\s+prompt is:", True,
              note=f"prompt counts {f['prompt_tokens']} tokens; 0010's model assumed {PROMPT}"),
        Claim("0015", "gpt-4o check at S=1000", r"\$([\d.]+) at S = 1000", (f"{f['check']:.2f}",)),
        Claim("0015", "consolidation calls and hours", r"the ([\d,]+) consolidation calls take about (\d+) hours in one thread",
              (f["clock_calls"] + f["list_calls"], round(f["hours_one_thread"])),
              note=f"at {SECONDS_PER_CALL} s per call, measured in session"),
        Claim("0015", "0010 figures at S=1000 (information)", r"0010 stands\.", True,
              note=f"estimate_cost.py: consolidation ${f['consolidate']:.2f}, total ${f['total']:.2f}, {f['share']:.0%} of cap"),
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
