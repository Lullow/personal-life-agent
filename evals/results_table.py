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
from evals.longmemeval import MODEL, PRICE_IN, PRICE_OUT, STRATEGY_LABELS, cost_of, usd  # noqa: E402
from evals.verify_adr_numbers import KU, ROOT, SSU, TYPES, Claim, fmt, judge  # noqa: E402

RESULTS = ROOT / "evals" / "results"
DOC = ROOT / "docs" / "results.md"
# The run that stands for each strategy, in the order of the table.
RUNS = {
    "recent-turns": "recent-turns-20261002-193902.jsonl",
    "retrieval": "retrieval-20261002-193417.jsonl",
    # M3: set to the run's file once it is committed. A missing file leaves the row out.
    "consolidating": "consolidating-20261003-233313.jsonl",
}
RUNS = {name: file for name, file in RUNS.items() if (RESULTS / file).exists()}
NAMES = {"recent-turns": "RecentTurnsMemory", "retrieval": "RetrievalMemory", "consolidating": "ConsolidatingMemory"}
GROUPS = ("neither", "earlier", "later", "both")


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (RESULTS / RUNS[name]).read_text(encoding="utf-8").splitlines()]


def framing(r: dict, label: str) -> int:
    """Input tokens the provider adds to one call: the system prompt and the question count as messages.

    A consolidation call is the system prompt and one user message (ADR 0015)."""
    messages = 2 + len(r["sources"]) if label == "answer" else 2
    return FRAMING_PER_MESSAGE * messages + FRAMING_PER_CALL


def priced(calls: list[tuple[dict, dict]], with_framing: bool = False) -> float:
    """The calls' cost, each at its own model's price (ADR 0015); a call without a model is the answering model's."""
    return sum(usd(c["input_tokens"] + (framing(r, c["label"]) if with_framing else 0), c["output_tokens"],
                   c.get("model") or MODEL) for r, c in calls)


def cell(rs: list[dict]) -> dict:
    mean = statistics.fmean
    ok = [r for r in rs if r["status"] == "ok"]
    paid = [(r, c) for r in rs for c in r["calls"] if c["label"] in STRATEGY_LABELS and not c["failed"]]
    tin = sum(c["input_tokens"] for _, c in paid)
    tout = sum(c["output_tokens"] for _, c in paid)
    out = dict(
        n=len(rs), errors=len(rs) - len(ok),
        correct=sum(r["correct"] for r in ok),
        reached=sum(r["evidence_reached"] for r in rs),
        recall=mean(r["recall"] for r in rs),
        precision=mean(r["precision"] for r in rs),
        messages=mean(len(r["sources"]) for r in rs),
        tokens_used=mean(r["tokens_used"] for r in rs),
        input_per_q=tin / len(rs), output_per_q=tout / len(rs),
        cost_per_q=priced(paid) / len(rs), framed_per_q=priced(paid, with_framing=True) / len(rs),
        idk=sum("not know" in (r["answer"] or "").lower() for r in ok),
    )
    if rs[0]["question_type"] == KU:
        out["breakdown"] = {g: (sum(r["ku_breakdown"] == g for r in rs),
                               sum(r["ku_breakdown"] == g and bool(r["correct"]) for r in rs)) for g in GROUPS}
        out["apart"] = sum(r["ku_breakdown"] is None for r in rs)
        # ADR 0009: a strategy with model calls is replayed in list order on the pilot questions only.
        listed = [r for r in rs if r["evidence_reached_list_order"] is not None]
        out["reached_list_order"] = sum(r["evidence_reached_list_order"] for r in listed)
        out["listed"] = len(listed)
    if rs[0]["recall_user_turns"] is not None:
        out["reached_user_turns"] = sum(r["evidence_reached_user_turns"] for r in rs)
        out["recall_user_turns"] = mean(r["recall_user_turns"] for r in rs)
    if rs[0].get("evidence_consolidated") is not None:
        # ADRs 0013, 0015–0017: the consolidating strategy's own figures.
        cons = [(r, c) for r, c in paid if c["label"] == "consolidate"]
        answer = [(r, c) for r, c in paid if c["label"] == "answer"]
        out.update(
            consolidated=mean(r["evidence_consolidated"] for r in rs),
            consolidated_or_reached=sum(r["evidence_consolidated_or_reached"] for r in rs),
            summary_tokens=mean(r["summary_tokens"] for r in rs),
            consolidations=sum(r["consolidations"] for r in rs),
            reasked=sum(r["summary_reasked"] for r in rs),
            cut=sum(r["summary_truncated"] for r in rs),
            skipped=sum(r["consolidations_failed"] for r in rs),
            consolidate_calls=len(cons),
            consolidate_in_per_q=sum(c["input_tokens"] for _, c in cons) / len(rs),
            consolidate_out_per_q=sum(c["output_tokens"] for _, c in cons) / len(rs),
            consolidate_cost_per_q=priced(cons) / len(rs),
            answer_cost_per_q=priced(answer) / len(rs),
        )
        if rs[0]["question_type"] == KU:
            out["breakdown_consolidated"] = {
                g: (sum(r["ku_breakdown_consolidated"] == g for r in rs),
                    sum(r["ku_breakdown_consolidated"] == g and bool(r["correct"]) for r in rs)) for g in GROUPS}
    return out


def compute() -> dict:
    f: dict = {"cells": {}, "runs": {}}
    for name in RUNS:
        rs = rows(name)
        f["runs"][name] = dict(commit={r["commit"] for r in rs}, model={r["model"] for r in rs},
                               calls=sum(len(r["calls"]) for r in rs),
                               failed=sum(c["failed"] for r in rs for c in r["calls"]),
                               cost=cost_of([c for r in rs for c in r["calls"]]))
        for t in TYPES:
            f["cells"][(name, t)] = cell([r for r in rs if r["question_type"] == t])
    f["total_cost"] = sum(v["cost"] for v in f["runs"].values())
    f["two_runs_cost"] = sum(f["runs"][n]["cost"] for n in ("recent-turns", "retrieval") if n in f["runs"])
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
        print(f"{NAMES[name]}: 'I do not know' answers {s['idk']} + {k['idk']}; list-order reach on KU {k['reached_list_order']} of {k['listed']}"
              + (f"; user-turn reach {s['reached_user_turns']} of {s['n']} and {k['reached_user_turns']} of {k['n']}" if "reached_user_turns" in s else ""))
    if ("consolidating", SSU) in c:
        s, k = c[("consolidating", SSU)], c[("consolidating", KU)]
        print()
        print("ConsolidatingMemory (ADRs 0013, 0015–0017)")
        print("| | single-session-user | knowledge-update |")
        print("|---|---:|---:|")
        print(f"| evidence consolidated, mean | {s['consolidated']:.3f} | {k['consolidated']:.3f} |")
        print(f"| evidence consolidated or reached | {s['consolidated_or_reached']} of {s['n']} | {k['consolidated_or_reached']} of {k['n']} |")
        print(f"| summary tokens, mean | {s['summary_tokens']:,.0f} | {k['summary_tokens']:,.0f} |")
        print(f"| consolidations: asked again / cut / skipped / all | {s['reasked']} / {s['cut']} / {s['skipped']} / {s['consolidations']} | {k['reasked']} / {k['cut']} / {k['skipped']} / {k['consolidations']} |")
        print(f"| consolidation per question: calls, tokens in / out | {s['consolidate_calls'] / s['n']:.1f}, {s['consolidate_in_per_q']:,.0f} / {s['consolidate_out_per_q']:,.0f} | {k['consolidate_calls'] / k['n']:.1f}, {k['consolidate_in_per_q']:,.0f} / {k['consolidate_out_per_q']:,.0f} |")
        print(f"| cost per question: answer + consolidation | ${s['answer_cost_per_q']:.4f} + ${s['consolidate_cost_per_q']:.4f} | ${k['answer_cost_per_q']:.4f} + ${k['consolidate_cost_per_q']:.4f} |")
        print()
        print("knowledge-update breakdown, consolidated or reached (ADR 0013): questions, correct")
        print("| | " + " | ".join(GROUPS) + " | not two sessions |")
        print("|---|" + "---:|" * (len(GROUPS) + 1))
        print("| `ConsolidatingMemory` | " + " | ".join(f"{k['breakdown_consolidated'][g][0]}, {k['breakdown_consolidated'][g][1]}" for g in GROUPS) + f" | {k['apart']} |")
    print()
    for name, v in f["runs"].items():
        print(f"{name}: commit {fmt(sorted(v['commit']))}, model {fmt(sorted(v['model']))}, {v['calls']} calls, {v['failed']} failed, ${v['cost']:.4f} counted")
    print(f"all runs: ${f['total_cost']:.2f} counted, each call at its model's price (the answering model at ${PRICE_IN}/M in and ${PRICE_OUT}/M out)")


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
        Claim("results", "both runs cost", r"The harness counts \$([\d.]+) for the two runs", (f"{f['two_runs_cost']:.2f}",)),
        Claim("results", "commit", r"commit `([0-9a-f]{7})`", (next(iter(f["runs"]["retrieval"]["commit"])),)),
    ] + (claims_consolidating(f) if ("consolidating", SSU) in c else [])


def claims_consolidating(f: dict) -> list[Claim]:
    c = f["cells"]
    s, k = c[("consolidating", SSU)], c[("consolidating", KU)]
    run = f["runs"]["consolidating"]
    money = lambda v: f"{v:.4f}"  # noqa: E731
    return [
        Claim("results", "ConsolidatingMemory correct", r"`ConsolidatingMemory`, correct \| (\d+) of (\d+) \(([\d.]+)\) \| (\d+) of (\d+) \(([\d.]+)\)",
              (s["correct"], s["n"], f"{s['correct'] / s['n']:.2f}", k["correct"], k["n"], f"{k['correct'] / k['n']:.2f}")),
        Claim("results", "ConsolidatingMemory reached", r"`ConsolidatingMemory`, evidence reached \| (\d+) of \d+ \| (\d+) of \d+",
              (s["reached"], k["reached"])),
        Claim("results", "ConsolidatingMemory recall / precision", r"`ConsolidatingMemory`, recall / precision \| ([\d.]+) / ([\d.]+) \| ([\d.]+) / ([\d.]+)",
              (f"{s['recall']:.3f}", f"{s['precision']:.4f}", f"{k['recall']:.3f}", f"{k['precision']:.4f}")),
        Claim("results", "ConsolidatingMemory messages / tokens", r"`ConsolidatingMemory`, messages / tokens recalled \| (\d+) / ([\d,]+) \| (\d+) / ([\d,]+)",
              (round(s["messages"]), round(s["tokens_used"]), round(k["messages"]), round(k["tokens_used"]))),
        Claim("results", "ConsolidatingMemory cost", r"`ConsolidatingMemory`, cost per question, counted / with framing \| \$([\d.]+) / \$([\d.]+) \| \$([\d.]+) / \$([\d.]+)",
              (money(s["cost_per_q"]), money(s["framed_per_q"]), money(k["cost_per_q"]), money(k["framed_per_q"]))),
        Claim("results", "KU breakdown, ConsolidatingMemory", r"`ConsolidatingMemory` \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|",
              (*(v for g in GROUPS for v in k["breakdown"][g]), k["apart"])),
        Claim("results", "KU breakdown, consolidated or reached", r"`ConsolidatingMemory` \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|.*?`ConsolidatingMemory` \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|",
              (*(v for g in GROUPS for v in k["breakdown"][g]), k["apart"], *(v for g in GROUPS for v in k["breakdown_consolidated"][g]), k["apart"])),
        Claim("results", "evidence consolidated", r"evidence consolidated, mean \| ([\d.]+) \| ([\d.]+) \|",
              (f"{s['consolidated']:.3f}", f"{k['consolidated']:.3f}")),
        Claim("results", "consolidated or reached", r"evidence consolidated or reached \| (\d+) of \d+ \| (\d+) of \d+ \|",
              (s["consolidated_or_reached"], k["consolidated_or_reached"])),
        Claim("results", "summary tokens", r"summary tokens, mean \| ([\d,]+) \| ([\d,]+) \|",
              (round(s["summary_tokens"]), round(k["summary_tokens"]))),
        Claim("results", "asked again / cut / skipped / all", r"consolidations: asked again / cut / skipped / all \| (\d+) / (\d+) / (\d+) / (\d+) \| (\d+) / (\d+) / (\d+) / (\d+) \|",
              (s["reasked"], s["cut"], s["skipped"], s["consolidations"], k["reasked"], k["cut"], k["skipped"], k["consolidations"])),
        Claim("results", "consolidation calls and tokens per question", r"consolidation per question: calls, tokens in / out \| ([\d.]+), ([\d,]+) / ([\d,]+) \| ([\d.]+), ([\d,]+) / ([\d,]+) \|",
              (f"{s['consolidate_calls'] / s['n']:.1f}", round(s["consolidate_in_per_q"]), round(s["consolidate_out_per_q"]),
               f"{k['consolidate_calls'] / k['n']:.1f}", round(k["consolidate_in_per_q"]), round(k["consolidate_out_per_q"]))),
        Claim("results", "answer + consolidation cost", r"cost per question: answer \+ consolidation \| \$([\d.]+) \+ \$([\d.]+) \| \$([\d.]+) \+ \$([\d.]+) \|",
              (money(s["answer_cost_per_q"]), money(s["consolidate_cost_per_q"]), money(k["answer_cost_per_q"]), money(k["consolidate_cost_per_q"]))),
        Claim("results", "third row: I do not know in the errors", r"\"I do not\s+know\" is the answer in (\d+) of (\d+) errors",
              (s["idk"] + k["idk"], s["n"] - s["correct"] + k["n"] - k["correct"])),
        Claim("results", "third row: cut of all consolidations", r"the cut fell in ([\d,]+) of ([\d,]+)",
              (s["cut"] + k["cut"], s["consolidations"] + k["consolidations"])),
        Claim("results", "third row: skipped sessions", r"(\d+) sessions were skipped\s+after", (s["skipped"] + k["skipped"],)),
        Claim("results", "third row: list-order reach", r"window reached\s+the evidence in (\d+) of (\d+), against (\d+) of 61 in clock order",
              (k["reached_list_order"], k["listed"], k["reached"])),
        Claim("results", "third row: run cost counted", r"The harness counts \$([\d.]+) for\s+the run", (f"{run['cost']:.2f}",)),
        Claim("results", "third row: failed calls", r"(\d+) consolidation calls failed, every one", (run["failed"],)),
    ] + claims_reading()


def claims_reading() -> list[Claim]:
    """Figures the review derives from the rows and the reading notes (evals/m3_review_figures.py)."""
    from evals.m3_review_figures import compute as review  # noqa: PLC0415 — only when the third row exists
    g = review()
    dist = g["correct by distance"]
    under, over = g["correct under 600 / at least 600"]
    cb = g["correct boxes"]
    notes_only = cb[("SSU", "anteckningarna")] + cb[("KU", "anteckningarna")]
    window_only = cb[("SSU", "fönstret")] + cb[("KU", "fönstret")]
    both = cb[("SSU", "båda")] + cb[("KU", "båda")]
    return [
        Claim("results", "reading: correct by distance",
              r"(\d+) of (\d+) under\s+8,000, (\d+) of (\d+) from 8,000 to 20,000, (\d+) of (\d+) from 20,000 to 40,000, (\d+) of (\d+)\s+from 40,000 to 70,000 and (\d+) of (\d+) beyond",
              tuple(v for _, _, c, n in dist for v in (c, n))),
        Claim("results", "reading: answered from notes / window / both / guess",
              r"The notes alone\s+account for (\d+) of the (\d+) correct answers, the window for (\d+), both for (\d+), and\s+one is a guess",
              (notes_only, g["correct"], window_only, both)),
        Claim("results", "reading: one guess", r"and\s+one is a guess", cb[("KU", "gissning")] + cb[("SSU", "gissning")] == 1),
        Claim("results", "rows: ask-again collapses", r"in (\d+) consolidations in (\d+)\s+questions a reply over 1,000 tokens was followed by one under 30%",
              g["collapses"]),
        Claim("results", "rows: short final notes and correctness", r"(\d+) questions ended with notes under 600 tokens, where (\d+) of (\d+)\s+answers were right against (\d+) of (\d+) above",
              (under[1], under[0], under[1], over[0], over[1])),
        Claim("results", "rows: final notes ending mid-sentence", r"(\w+) final notes end mid-sentence", (len(g["mid-sentence endings"]),)),
        Claim("results", "rows: non-English final notes", r"(\w+) of the 122\s+final notes are not in English", (len(g["non-English finals"]),)),
        Claim("results", "rows: the Chinese notes", r"collapsed to\s+(\d+) tokens because the cut rule knows no Chinese full stop", (g["36580ce8"]["tokens"],)),
        Claim("results", "rows: skipped sessions held no evidence", r"none of them holding evidence", g["evidence consolidated everywhere"]),
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
