"""The results table: every strategy measured so far, per question type.

Reads the committed rows in evals/results/ and prints the figures the report
quotes: accuracy, recall, precision, how often the evidence reached the
context, what a recall held, and what a question cost, counted by the harness
(ADR 0006) and with the framing the provider adds (ADR 0010). Every figure in
docs/results.md must come from here.

    .venv/bin/python evals/results_table.py            # the tables
    .venv/bin/python evals/results_table.py --check    # docs/results.md against this script
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import FRAMING_PER_CALL, FRAMING_PER_MESSAGE  # noqa: E402
from evals.longmemeval import PRICE_IN, PRICE_OUT, STRATEGY_LABELS, usd  # noqa: E402
from evals.verify_adr_numbers import KU, ROOT, SSU, TYPES, Claim, fmt, judge  # noqa: E402

RESULTS = ROOT / "evals" / "results"
DOC = ROOT / "docs" / "results.md"
# The run that stands for each strategy, in the order of the table.
RUNS = {
    "recent-turns": "recent-turns-20261002-193902.jsonl",
    "retrieval": "retrieval-20261002-193417.jsonl",
}
NAMES = {"recent-turns": "RecentTurnsMemory", "retrieval": "RetrievalMemory"}
GROUPS = ("neither", "earlier", "later", "both")


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (RESULTS / RUNS[name]).read_text(encoding="utf-8").splitlines()]


def framing(r: dict, label: str) -> int:
    """Input tokens the provider adds to one call: the system prompt and the question count as messages."""
    messages = 2 + len(r["sources"]) if label == "answer" else 2
    return FRAMING_PER_MESSAGE * messages + FRAMING_PER_CALL


def cell(rs: list[dict]) -> dict:
    mean = statistics.fmean
    ok = [r for r in rs if r["status"] == "ok"]
    paid = [(r, c) for r in rs for c in r["calls"] if c["label"] in STRATEGY_LABELS and not c["failed"]]
    tin = sum(c["input_tokens"] for _, c in paid)
    tout = sum(c["output_tokens"] for _, c in paid)
    framed = tin + sum(framing(r, c["label"]) for r, c in paid)
    out = dict(
        n=len(rs), errors=len(rs) - len(ok),
        correct=sum(r["correct"] for r in ok),
        reached=sum(r["evidence_reached"] for r in rs),
        recall=mean(r["recall"] for r in rs),
        precision=mean(r["precision"] for r in rs),
        messages=mean(len(r["sources"]) for r in rs),
        tokens_used=mean(r["tokens_used"] for r in rs),
        input_per_q=tin / len(rs), output_per_q=tout / len(rs),
        cost_per_q=usd(tin, tout) / len(rs), framed_per_q=usd(framed, tout) / len(rs),
        idk=sum("not know" in (r["answer"] or "").lower() for r in ok),
    )
    if rs[0]["question_type"] == KU:
        out["breakdown"] = {g: (sum(r["ku_breakdown"] == g for r in rs),
                               sum(r["ku_breakdown"] == g and bool(r["correct"]) for r in rs)) for g in GROUPS}
        out["apart"] = sum(r["ku_breakdown"] is None for r in rs)
        out["reached_list_order"] = sum(r["evidence_reached_list_order"] for r in rs)
    if rs[0]["recall_user_turns"] is not None:
        out["reached_user_turns"] = sum(r["evidence_reached_user_turns"] for r in rs)
        out["recall_user_turns"] = mean(r["recall_user_turns"] for r in rs)
    return out


def compute() -> dict:
    f: dict = {"cells": {}, "runs": {}}
    for name in RUNS:
        rs = rows(name)
        f["runs"][name] = dict(commit={r["commit"] for r in rs}, model={r["model"] for r in rs},
                               calls=sum(len(r["calls"]) for r in rs),
                               failed=sum(c["failed"] for r in rs for c in r["calls"]),
                               cost=usd(sum(c["input_tokens"] for r in rs for c in r["calls"]),
                                        sum(c["output_tokens"] for r in rs for c in r["calls"])))
        for t in TYPES:
            f["cells"][(name, t)] = cell([r for r in rs if r["question_type"] == t])
    f["total_cost"] = sum(v["cost"] for v in f["runs"].values())
    return f


def print_tables(f: dict) -> None:
    c = f["cells"]
    print("| | single-session-user | knowledge-update |")
    print("|---|---:|---:|")
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"| `{NAMES[name]}`, correct | {s['correct']} of {s['n']} ({s['correct'] / s['n']:.2f}) | {k['correct']} of {k['n']} ({k['correct'] / k['n']:.2f}) |")
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"| `{NAMES[name]}`, evidence reached | {s['reached']} of {s['n']} | {k['reached']} of {k['n']} |")
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"| `{NAMES[name]}`, recall / precision | {s['recall']:.3f} / {s['precision']:.4f} | {k['recall']:.3f} / {k['precision']:.4f} |")
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"| `{NAMES[name]}`, messages / tokens recalled | {s['messages']:.0f} / {s['tokens_used']:,.0f} | {k['messages']:.0f} / {k['tokens_used']:,.0f} |")
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"| `{NAMES[name]}`, cost per question, counted / with framing | ${s['cost_per_q']:.4f} / ${s['framed_per_q']:.4f} | ${k['cost_per_q']:.4f} / ${k['framed_per_q']:.4f} |")
    print()
    print("knowledge-update breakdown (ADR 0009): questions, correct")
    print("| | " + " | ".join(GROUPS) + " | not two sessions |")
    print("|---|" + "---:|" * (len(GROUPS) + 1))
    for name in RUNS:
        k = c[(name, KU)]
        print(f"| `{NAMES[name]}` | " + " | ".join(f"{k['breakdown'][g][0]}, {k['breakdown'][g][1]}" for g in GROUPS) + f" | {k['apart']} |")
    print()
    for name in RUNS:
        s, k = c[(name, SSU)], c[(name, KU)]
        print(f"{NAMES[name]}: 'I do not know' answers {s['idk']} + {k['idk']}; list-order reach on KU {k['reached_list_order']} of {k['n']}"
              + (f"; user-turn reach {s['reached_user_turns']} of {s['n']} and {k['reached_user_turns']} of {k['n']}" if "reached_user_turns" in s else ""))
    print()
    for name, v in f["runs"].items():
        print(f"{name}: commit {fmt(sorted(v['commit']))}, model {fmt(sorted(v['model']))}, {v['calls']} calls, {v['failed']} failed, ${v['cost']:.4f} counted")
    print(f"both runs: ${f['total_cost']:.2f} counted at ${PRICE_IN}/M in and ${PRICE_OUT}/M out")


def claims(f: dict) -> list[Claim]:
    c = f["cells"]
    b, r = (c[("recent-turns", SSU)], c[("recent-turns", KU)]), (c[("retrieval", SSU)], c[("retrieval", KU)])
    money = lambda v: f"{v:.4f}"  # noqa: E731
    return [
        Claim("results", "RetrievalMemory correct", r"`RetrievalMemory`, correct \| (\d+) of (\d+) \(([\d.]+)\) \| (\d+) of (\d+) \(([\d.]+)\)",
              (r[0]["correct"], r[0]["n"], f"{r[0]['correct'] / r[0]['n']:.2f}", r[1]["correct"], r[1]["n"], f"{r[1]['correct'] / r[1]['n']:.2f}")),
        Claim("results", "RecentTurnsMemory correct", r"`RecentTurnsMemory`, correct \| (\d+) of (\d+) \(([\d.]+)\) \| (\d+) of (\d+) \(([\d.]+)\)",
              (b[0]["correct"], b[0]["n"], f"{b[0]['correct'] / b[0]['n']:.2f}", b[1]["correct"], b[1]["n"], f"{b[1]['correct'] / b[1]['n']:.2f}")),
        Claim("results", "RetrievalMemory reached", r"`RetrievalMemory`, evidence reached \| (\d+) of \d+ \| (\d+) of \d+",
              (r[0]["reached"], r[1]["reached"])),
        Claim("results", "RecentTurnsMemory reached", r"`RecentTurnsMemory`, evidence reached \| (\d+) of \d+ \| (\d+) of \d+",
              (b[0]["reached"], b[1]["reached"])),
        Claim("results", "RetrievalMemory recall / precision", r"`RetrievalMemory`, recall / precision \| ([\d.]+) / ([\d.]+) \| ([\d.]+) / ([\d.]+)",
              (f"{r[0]['recall']:.3f}", f"{r[0]['precision']:.4f}", f"{r[1]['recall']:.3f}", f"{r[1]['precision']:.4f}")),
        Claim("results", "RecentTurnsMemory recall / precision", r"`RecentTurnsMemory`, recall / precision \| ([\d.]+) / ([\d.]+) \| ([\d.]+) / ([\d.]+)",
              (f"{b[0]['recall']:.3f}", f"{b[0]['precision']:.4f}", f"{b[1]['recall']:.3f}", f"{b[1]['precision']:.4f}")),
        Claim("results", "RetrievalMemory messages / tokens", r"`RetrievalMemory`, messages / tokens recalled \| (\d+) / ([\d,]+) \| (\d+) / ([\d,]+)",
              (round(r[0]["messages"]), round(r[0]["tokens_used"]), round(r[1]["messages"]), round(r[1]["tokens_used"]))),
        Claim("results", "RecentTurnsMemory messages / tokens", r"`RecentTurnsMemory`, messages / tokens recalled \| (\d+) / ([\d,]+) \| (\d+) / ([\d,]+)",
              (round(b[0]["messages"]), round(b[0]["tokens_used"]), round(b[1]["messages"]), round(b[1]["tokens_used"]))),
        Claim("results", "RetrievalMemory cost", r"`RetrievalMemory`, cost per question, counted / with framing \| \$([\d.]+) / \$([\d.]+) \| \$([\d.]+) / \$([\d.]+)",
              (money(r[0]["cost_per_q"]), money(r[0]["framed_per_q"]), money(r[1]["cost_per_q"]), money(r[1]["framed_per_q"]))),
        Claim("results", "RecentTurnsMemory cost", r"`RecentTurnsMemory`, cost per question, counted / with framing \| \$([\d.]+) / \$([\d.]+) \| \$([\d.]+) / \$([\d.]+)",
              (money(b[0]["cost_per_q"]), money(b[0]["framed_per_q"]), money(b[1]["cost_per_q"]), money(b[1]["framed_per_q"]))),
        Claim("results", "KU breakdown, RetrievalMemory", r"`RetrievalMemory` \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|",
              (*(v for g in GROUPS for v in r[1]["breakdown"][g]), r[1]["apart"])),
        Claim("results", "KU breakdown, RecentTurnsMemory", r"`RecentTurnsMemory` \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|",
              (*(v for g in GROUPS for v in b[1]["breakdown"][g]), b[1]["apart"])),
        Claim("results", "'I do not know' answers", r"\"I do not know\" in (\d+) of its 122 answers, `RetrievalMemory` in (\d+)",
              (b[0]["idk"] + b[1]["idk"], r[0]["idk"] + r[1]["idk"])),
        Claim("results", "user-turn reach", r"[Ww]ith only the user turns indexed, the evidence reaches the context in (\d+) and (\d+) of 61",
              (r[0]["reached_user_turns"], r[1]["reached_user_turns"])),
        Claim("results", "list-order reach", r"in the list order of 0004 it reaches the evidence in (\d+) `knowledge-update` questions instead of (\d+)",
              (b[1]["reached_list_order"], b[1]["reached"])),
        Claim("results", "both runs cost", r"The harness counts \$([\d.]+) for the two runs", (f"{f['total_cost']:.2f}",)),
        Claim("results", "commit", r"commit `([0-9a-f]{7})`", (next(iter(f["runs"]["retrieval"]["commit"])),)),
    ]


def main() -> int:
    f = compute()
    if "--check" not in sys.argv:
        print_tables(f)
        return 0
    text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
    cs = claims(f)
    for c in cs:
        judge(c, text)
        print(f"{c.status:12s} {c.label:40s} text {fmt(c.groups) if c.groups else '—':52s} computed {fmt(c.computed)}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
