"""The results table: every strategy measured so far, per question type.

Reads the committed rows in evals/results/ and prints the figures the report
quotes: accuracy, recall, precision, how often the evidence reached the
context, what a recall held, and what a question cost, counted by the harness
(ADR 0006) and with the framing the provider adds (ADR 0010). Every figure in
docs/results.md must come from here, and so must the ones README.md restates in
its overview. The fourth strategy's pilot (ADR 0019) is printed apart, in
tables of its own.

    .venv/bin/python evals/results_table.py            # the tables
    .venv/bin/python evals/results_table.py --check    # docs/results.md and README.md against this script
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
from evals.verify_adr_numbers import KU, PILOT_PER_TYPE, ROOT, SSU, TYPES, Claim, fmt, judge  # noqa: E402

RESULTS = ROOT / "evals" / "results"
DOC = ROOT / "docs" / "results.md"
README = ROOT / "README.md"
# The run that stands for each strategy, in the order of the table.
RUNS = {
    "recent-turns": "recent-turns-20261002-193902.jsonl",
    "retrieval": "retrieval-20261002-193417.jsonl",
    # M3: set to the run's file once it is committed. A missing file leaves the row out.
    "consolidating": "consolidating-20261003-233313.jsonl",
}
RUNS = {name: file for name, file in RUNS.items() if (RESULTS / file).exists()}
# ADR 0019: the fourth strategy's run is a pilot on the first ten questions of each type. It is never
# a row of the table: it gets tables of its own, next to the rows the runs above have for those questions.
PILOT = {"fact-graph": "fact-graph-20261005-161632.jsonl"}
PILOT = {name: file for name, file in PILOT.items() if (RESULTS / file).exists()}
# ADR 0019: no figure of the pilot is reported before its answers are read by hand, so docs/results.md
# is held to the pilot's figures once the review of that reading is here.
PILOT_REVIEW = "fact-graph-20261005-161632-review.md"
NAMES = {"recent-turns": "RecentTurnsMemory", "retrieval": "RetrievalMemory", "consolidating": "ConsolidatingMemory",
         "fact-graph": "FactGraphMemory"}
GROUPS = ("neither", "earlier", "later", "both")


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (RESULTS / {**RUNS, **PILOT}[name]).read_text(encoding="utf-8").splitlines()]


def sent(r: dict) -> int:
    """The messages one recall held. A facts message is one message with an id per fact, so the row
    counts them (ADR 0018); a row from before that has no count, and there sources gives it."""
    return r["messages"] if r.get("messages") is not None else len(r["sources"])


def framing(r: dict, label: str) -> int:
    """Input tokens the provider adds to one call: the system prompt and the question count as messages.

    A consolidation call is the system prompt and one user message (ADR 0015), and so is an
    extraction call (ADR 0018)."""
    messages = 2 + sent(r) if label == "answer" else 2
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
        messages=mean(sent(r) for r in rs),
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
        # ADR 0013: what a strategy that reads the sessions with a model reports next to its recall.
        answer = [(r, c) for r, c in paid if c["label"] == "answer"]
        out.update(
            consolidated=mean(r["evidence_consolidated"] for r in rs),
            consolidated_or_reached=sum(r["evidence_consolidated_or_reached"] for r in rs),
            answer_cost_per_q=priced(answer) / len(rs),
        )
        if rs[0]["question_type"] == KU:
            out["breakdown_consolidated"] = {
                g: (sum(r["ku_breakdown_consolidated"] == g for r in rs),
                    sum(r["ku_breakdown_consolidated"] == g and bool(r["correct"]) for r in rs)) for g in GROUPS}
    if rs[0].get("summary_tokens") is not None:
        # ADRs 0015–0017: the consolidating strategy's own figures.
        cons = [(r, c) for r, c in paid if c["label"] == "consolidate"]
        out.update(
            summary_tokens=mean(r["summary_tokens"] for r in rs),
            consolidations=sum(r["consolidations"] for r in rs),
            reasked=sum(r["summary_reasked"] for r in rs),
            cut=sum(r["summary_truncated"] for r in rs),
            skipped=sum(r["consolidations_failed"] for r in rs),
            consolidate_calls=len(cons),
            consolidate_in_per_q=sum(c["input_tokens"] for _, c in cons) / len(rs),
            consolidate_out_per_q=sum(c["output_tokens"] for _, c in cons) / len(rs),
            consolidate_cost_per_q=priced(cons) / len(rs),
        )
    if rs[0].get("facts_stored") is not None:
        # ADR 0018: the fact graph's own figures.
        extract = [(r, c) for r, c in paid if c["label"] == "extract"]
        total = lambda key: sum(r[key] for r in rs)  # noqa: E731
        out.update(
            facts=tuple(mean(r[key] for r in rs) for key in ("facts_stored", "facts_replaced", "facts_held", "facts_shown")),
            facts_message_tokens=mean(r["facts_message_tokens"] for r in rs),
            facts_message_tokens_max=max(r["facts_message_tokens"] for r in rs),
            said_again=total("facts_said_again"), dropped=total("entries_dropped"),
            skipped=total("extractions_failed"), extractions=total("extractions"),
            evidence_turn_facts=(total("evidence_turn_facts_replaced"), total("evidence_turn_facts_shown"),
                                 total("evidence_turn_facts")),
            extract_calls=len(extract),
            extract_in_per_q=sum(c["input_tokens"] for _, c in extract) / len(rs),
            extract_out_per_q=sum(c["output_tokens"] for _, c in extract) / len(rs),
            extract_cost_per_q=priced(extract) / len(rs),
        )
    return out


def pilot() -> dict:
    """ADR 0019: the four strategies on the pilot's questions, the first ten of each type.

    The fourth strategy's rows are its pilot run; the other three are the rows their runs have for
    the same questions."""
    names = (*RUNS, *PILOT)
    order = lambda r: (TYPES.index(r["question_type"]), r["position"])  # noqa: E731
    rs = {name: sorted((r for r in rows(name) if r["position"] < PILOT_PER_TYPE), key=order) for name in names}
    (fourth,) = (rs[name] for name in PILOT)
    whole = [r for name in PILOT for r in rows(name)]
    calls = [c for r in whole for c in r["calls"]]
    by = {name: {r["question_id"]: r for r in rs[name]} for name in names}
    return dict(
        cells={(name, t): cell([r for r in rs[name] if r["question_type"] == t]) for name in names for t in TYPES},
        # The run is the pilot and nothing else, and every strategy has a row for each of its questions.
        same_questions=len(whole) == len(fourth) == len(TYPES) * PILOT_PER_TYPE and all(
            [r["question_id"] for r in rs[name]] == [r["question_id"] for r in fourth] for name in names),
        same_model=len({r["model"] for name in names for r in rs[name]}) == 1,
        questions=[dict(id=r["question_id"], type=r["question_type"],
                        verdicts={name: "yes" if by[name][r["question_id"]]["correct"] else "no" for name in names},
                        reached="yes" if r["evidence_reached"] else "no",
                        evidence_turn_facts=(r["evidence_turn_facts_replaced"], r["evidence_turn_facts_shown"],
                                             r["evidence_turn_facts"])) for r in fourth],
        run=dict(commit={r["commit"] for r in whole}, model={r["model"] for r in whole},
                 extractor={r["extractor"] for r in whole}, calls=len(calls), failed=sum(c["failed"] for c in calls),
                 cost=cost_of(calls),
                 labels={label: (sum(c["label"] == label for c in calls), cost_of([c for c in calls if c["label"] == label]))
                         for label in sorted({c["label"] for c in calls})}),
    )


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
    if PILOT:
        f["pilot"] = pilot()
        f["total_cost"] += f["pilot"]["run"]["cost"]
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
    if "pilot" in f:
        print()
        print_pilot(f["pilot"])
    print()
    for name, v in f["runs"].items():
        print(f"{name}: commit {fmt(sorted(v['commit']))}, model {fmt(sorted(v['model']))}, {v['calls']} calls, {v['failed']} failed, ${v['cost']:.4f} counted")
    if "pilot" in f:
        v = f["pilot"]["run"]
        print(f"{', '.join(PILOT)}, the pilot: commit {fmt(sorted(v['commit']))}, model {fmt(sorted(v['model']))}, extraction by {fmt(sorted(v['extractor']))}, "
              f"{v['calls']} calls, {v['failed']} failed, ${v['cost']:.4f} counted ("
              + ", ".join(f"{label} {n} calls ${cost:.4f}" for label, (n, cost) in v["labels"].items()) + ")")
    print(f"all runs: ${f['total_cost']:.2f} counted, each call at its model's price (the answering model at ${PRICE_IN}/M in and ${PRICE_OUT}/M out)")


def print_pilot(p: dict) -> None:
    c = p["cells"]
    names = (*RUNS, *PILOT)
    (fourth,) = PILOT
    s, k = c[(fourth, SSU)], c[(fourth, KU)]
    both = lambda text: f"{text(s)} | {text(k)}"  # noqa: E731
    print("The pilot (ADR 0019): the fourth strategy on the first ten questions of each type")
    print(f"| on the same {len(p['questions'])} questions | " + " | ".join(f"`{NAMES[n]}`" + (", pilot" if n in PILOT else "") for n in names) + " |")
    print("|---|" + "---:|" * len(names))
    for t in TYPES:
        print(f"| correct, {t} | " + " | ".join(f"{c[(n, t)]['correct']} of {c[(n, t)]['n']}" for n in names) + " |")
    for t in TYPES:
        print(f"| evidence reached, {t} | " + " | ".join(f"{c[(n, t)]['reached']} of {c[(n, t)]['n']}" for n in names) + " |")
    for t in TYPES:
        print(f"| cost per question, {t} | " + " | ".join(f"${c[(n, t)]['cost_per_q']:.4f}" for n in names) + " |")
    print()
    print(f"{NAMES[fourth]}, the pilot's own figures (ADRs 0013, 0018)")
    print(f"| `{NAMES[fourth]}`, pilot | single-session-user | knowledge-update |")
    print("|---|---:|---:|")
    print("| recall / precision | " + both(lambda v: f"{v['recall']:.3f} / {v['precision']:.4f}") + " |")
    print("| messages / tokens recalled | " + both(lambda v: f"{v['messages']:.0f} / {v['tokens_used']:,.0f}") + " |")
    print("| evidence consolidated (0018), mean | " + both(lambda v: f"{v['consolidated']:.3f}") + " |")
    print("| evidence consolidated (0018) or reached | " + both(lambda v: f"{v['consolidated_or_reached']} of {v['n']}") + " |")
    print("| facts stored / replaced / held / shown, mean | " + both(lambda v: " / ".join(f"{x:.1f}" for x in v["facts"])) + " |")
    print("| facts message tokens, mean / max | " + both(lambda v: f"{v['facts_message_tokens']:,.0f} / {v['facts_message_tokens_max']:,}") + " |")
    print("| facts said again / entries dropped | " + both(lambda v: f"{v['said_again']} / {v['dropped']}") + " |")
    print("| sessions skipped / all | " + both(lambda v: f"{v['skipped']} / {v['extractions']}") + " |")
    print("| facts from an evidence turn: replaced / shown / all | " + both(lambda v: " / ".join(map(str, v["evidence_turn_facts"]))) + " |")
    print("| extraction per question: calls, tokens in / out | "
          + both(lambda v: f"{v['extract_calls'] / v['n']:.1f}, {v['extract_in_per_q']:,.0f} / {v['extract_out_per_q']:,.0f}") + " |")
    print("| cost per question: answer + extraction | " + both(lambda v: f"${v['answer_cost_per_q']:.4f} + ${v['extract_cost_per_q']:.4f}") + " |")
    print("| cost per question, counted / with framing | " + both(lambda v: f"${v['cost_per_q']:.4f} / ${v['framed_per_q']:.4f}") + " |")
    print()
    print("knowledge-update breakdown of the pilot (ADRs 0009, 0013): questions, correct")
    print(f"| `{NAMES[fourth]}`, pilot | " + " | ".join(GROUPS) + " | not two sessions |")
    print("|---|" + "---:|" * (len(GROUPS) + 1))
    for label, key in (("window", "breakdown"), ("consolidated (0018) or reached", "breakdown_consolidated")):
        print(f"| {label} | " + " | ".join(f"{k[key][g][0]}, {k[key][g][1]}" for g in GROUPS) + f" | {k['apart']} |")
    print()
    print("The pilot, question by question: the judge's verdict on each strategy's answer, and what the fourth strategy held")
    print("| question | type | " + " | ".join(f"`{NAMES[n]}`" for n in names)
          + " | evidence reached, pilot | facts from an evidence turn: replaced / shown / all |")
    print("|---|---|" + "---|" * len(names) + "---|---:|")
    for q in p["questions"]:
        print(f"| `{q['id']}` | {q['type']} | " + " | ".join(q["verdicts"][n] for n in names)
              + f" | {q['reached']} | " + " / ".join(map(str, q["evidence_turn_facts"])) + " |")
    print()
    print(f"{NAMES[fourth]}, pilot: 'I do not know' answers {s['idk']} + {k['idk']}; list-order reach on KU {k['reached_list_order']} of {k['listed']}"
          f", {k['reached']} in clock order; same questions in every run: {fmt(p['same_questions'])}; same answering model: {fmt(p['same_model'])}")


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
    ] + (claims_consolidating(f) if ("consolidating", SSU) in c else []) + (
        claims_pilot(f) if "pilot" in f and (RESULTS / PILOT_REVIEW).exists() else [])


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
    # Correct `knowledge-update` answers whose notes held the newer value only: those answered from the
    # notes or from both, and the one guess, which asks for the earlier value (the notes' remark on it).
    ku_newer_only = cb[("KU", "anteckningarna")] + cb[("KU", "båda")] + cb[("KU", "gissning")]
    ku_correct = sum(n for (qtype, _), n in cb.items() if qtype == "KU")
    return [
        Claim("results", "reading: notes with the newer value only, among the correct changed-fact answers",
              r"held the newer value only in (\d+) of its (\d+) correct `knowledge-update`\s+answers, and in none both, so the summary does replace the old value. The\s+other (\d+) were answered from the window, with neither value in the notes",
              (ku_newer_only, ku_correct, cb[("KU", "fönstret")])),
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


def claims_pilot(f: dict) -> list[Claim]:
    """ADR 0019: every figure in the pilot's tables, the rows per question included."""
    p = f["pilot"]
    c = p["cells"]
    names = (*RUNS, *PILOT)
    (fourth,) = PILOT
    s, k = c[(fourth, SSU)], c[(fourth, KU)]
    money = lambda v: f"{v:.4f}"  # noqa: E731
    each = lambda cell: r" \| ".join([cell] * len(names)) + r" \|"  # noqa: E731
    group = r"(\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+), (\d+) \| (\d+) \|"
    cs = [
        Claim("results", "pilot: questions", r"\| on the same (\d+) questions \|", (len(p["questions"]),)),
        Claim("results", "pilot: same questions and model in every run", r"\| on the same \d+ questions \|",
              p["same_questions"] and p["same_model"]),
    ]
    for t in TYPES:
        cells = [c[(n, t)] for n in names]
        cs += [
            Claim("results", f"pilot: correct, {t}", rf"\| correct, {t} \| " + each(r"(\d+) of (\d+)"),
                  tuple(v for x in cells for v in (x["correct"], x["n"]))),
            Claim("results", f"pilot: evidence reached, {t}", rf"\| evidence reached, {t} \| " + each(r"(\d+) of (\d+)"),
                  tuple(v for x in cells for v in (x["reached"], x["n"]))),
            Claim("results", f"pilot: cost per question, {t}", rf"\| cost per question, {t} \| " + each(r"\$([\d.]+)"),
                  tuple(money(x["cost_per_q"]) for x in cells)),
        ]
    cs += [
        Claim("results", "pilot: recall / precision", r"\| recall / precision \| ([\d.]+) / ([\d.]+) \| ([\d.]+) / ([\d.]+) \|",
              (f"{s['recall']:.3f}", f"{s['precision']:.4f}", f"{k['recall']:.3f}", f"{k['precision']:.4f}")),
        Claim("results", "pilot: messages / tokens", r"\| messages / tokens recalled \| (\d+) / ([\d,]+) \| (\d+) / ([\d,]+) \|",
              (round(s["messages"]), round(s["tokens_used"]), round(k["messages"]), round(k["tokens_used"]))),
        Claim("results", "pilot: evidence consolidated", r"evidence consolidated \(0018\), mean \| ([\d.]+) \| ([\d.]+) \|",
              (f"{s['consolidated']:.3f}", f"{k['consolidated']:.3f}")),
        Claim("results", "pilot: consolidated or reached", r"evidence consolidated \(0018\) or reached \| (\d+) of (\d+) \| (\d+) of (\d+) \|",
              (s["consolidated_or_reached"], s["n"], k["consolidated_or_reached"], k["n"])),
        Claim("results", "pilot: facts stored / replaced / held / shown",
              r"facts stored / replaced / held / shown, mean \| ([\d.]+) / ([\d.]+) / ([\d.]+) / ([\d.]+) \| ([\d.]+) / ([\d.]+) / ([\d.]+) / ([\d.]+) \|",
              tuple(f"{x:.1f}" for v in (s, k) for x in v["facts"])),
        Claim("results", "pilot: facts message tokens", r"facts message tokens, mean / max \| ([\d,]+) / ([\d,]+) \| ([\d,]+) / ([\d,]+) \|",
              (round(s["facts_message_tokens"]), s["facts_message_tokens_max"], round(k["facts_message_tokens"]), k["facts_message_tokens_max"])),
        Claim("results", "pilot: said again / dropped", r"facts said again / entries dropped \| (\d+) / (\d+) \| (\d+) / (\d+) \|",
              (s["said_again"], s["dropped"], k["said_again"], k["dropped"])),
        Claim("results", "pilot: sessions skipped / all", r"sessions skipped / all \| (\d+) / (\d+) \| (\d+) / (\d+) \|",
              (s["skipped"], s["extractions"], k["skipped"], k["extractions"])),
        Claim("results", "pilot: facts from an evidence turn",
              r"\| facts from an evidence turn: replaced / shown / all \| (\d+) / (\d+) / (\d+) \| (\d+) / (\d+) / (\d+) \|",
              (*s["evidence_turn_facts"], *k["evidence_turn_facts"])),
        Claim("results", "pilot: extraction calls and tokens", r"extraction per question: calls, tokens in / out \| ([\d.]+), ([\d,]+) / ([\d,]+) \| ([\d.]+), ([\d,]+) / ([\d,]+) \|",
              (f"{s['extract_calls'] / s['n']:.1f}", round(s["extract_in_per_q"]), round(s["extract_out_per_q"]),
               f"{k['extract_calls'] / k['n']:.1f}", round(k["extract_in_per_q"]), round(k["extract_out_per_q"]))),
        Claim("results", "pilot: answer + extraction cost", r"cost per question: answer \+ extraction \| \$([\d.]+) \+ \$([\d.]+) \| \$([\d.]+) \+ \$([\d.]+) \|",
              (money(s["answer_cost_per_q"]), money(s["extract_cost_per_q"]), money(k["answer_cost_per_q"]), money(k["extract_cost_per_q"]))),
        Claim("results", "pilot: cost counted / with framing", r"\| cost per question, counted / with framing \| \$([\d.]+) / \$([\d.]+) \| \$([\d.]+) / \$([\d.]+) \|",
              (money(s["cost_per_q"]), money(s["framed_per_q"]), money(k["cost_per_q"]), money(k["framed_per_q"]))),
        Claim("results", "pilot: KU breakdown, window", r"\| window \| " + group,
              (*(v for g in GROUPS for v in k["breakdown"][g]), k["apart"])),
        Claim("results", "pilot: KU breakdown, consolidated or reached", r"\| consolidated \(0018\) or reached \| " + group,
              (*(v for g in GROUPS for v in k["breakdown_consolidated"][g]), k["apart"])),
    ]
    for q in p["questions"]:
        cs.append(Claim("results", f"pilot: {q['id']}",
                        rf"`{q['id']}` \| {q['type']} \| " + each(r"(\w+)") + r" (\w+) \| (\d+) / (\d+) / (\d+) \|",
                        (*(q["verdicts"][n] for n in names), q["reached"], *q["evidence_turn_facts"])))
    return cs + claims_pilot_text(f)


def claims_pilot_text(f: dict) -> list[Claim]:
    """The figures in the text under the pilot's tables: from the rows, the exported facts and the
    reading notes (evals/m4_review_figures.py), without the dataset."""
    from evals.m4_review_figures import compute as review  # noqa: PLC0415 — only when the pilot is reported
    from life_agent.agent.memory import FACT_TOKENS  # noqa: PLC0415
    p, g = f["pilot"], review()
    c, run = p["cells"], p["run"]
    (fourth,) = PILOT
    s, k = c[(fourth, SSU)], c[(fourth, KU)]
    r = (c[("retrieval", SSU)], c[("retrieval", KU)])
    cb = g["correct boxes"]
    replaced, replaced_right = g["earlier replaced by the newer: questions, correct"]
    both, both_right = g["both held and shown: questions, correct"]
    never, never_right = g["one value never a fact: questions, correct"]
    in_fact, in_fact_right = g["value in a shown fact, by the rows: questions, correct"]
    far, far_right, far_third = g["beyond 40,000 tokens: questions, correct here, correct for the consolidating run"]
    far_unanswered = g["beyond 40,000 tokens, judged right and not an answer by the reading"]
    stored, n_replaced = g["facts stored / replaced"]
    from_evidence, from_evidence_replaced, _ = g["facts from evidence sessions: all / replaced / shown"]
    by_evidence, by_others = g["of those replaced: by an evidence session / by a session without evidence"]
    out, fewer = g["b01defab: turns the baseline had and this run did not, their tokens"]
    raw_base, raw_third, raw_here = g["b01defab: raw tokens in the window, baseline / consolidating / here"]
    reading = g["reading of the replacements"]
    wrong_on_content = g["judged right and not an answer by the reading"]
    listed = run["labels"]["extract-list-order"][1]
    return [
        Claim("results", "pilot text: questions, commit, day", r"on the first (\w+) questions of each type, the (\d+) of the M1 pilot, on commit `([0-9a-f]{7})` on (\d+) October",
              (PILOT_PER_TYPE, len(p["questions"]), *sorted(run["commit"]), *sorted({int(file.split("-")[-2][6:8]) for file in PILOT.values()}))),
        Claim("results", "pilot text: the days of the other runs", r"the rows their runs of (\d+) and (\d+) October have for the same questions",
              tuple(sorted({int(file.split("-")[-2][6:8]) for file in RUNS.values()}))),
        Claim("results", "pilot text: extractor", r"with `([\w/.-]+)` extracting the facts", tuple(sorted(run["extractor"]))),
        Claim("results", "pilot text: calls", r"none of its ([\d,]+) calls failed and no session was skipped", (run["calls"],)),
        Claim("results", "pilot text: no call failed, no session skipped, no error", r"No question errored and nothing was over budget; none of its",
              run["failed"] == 0 and s["skipped"] + k["skipped"] == 0 and s["errors"] + k["errors"] == 0 and g["errors / over budget"] == (0, 0)),
        Claim("results", "pilot text: one question moves a share", r"one question moves a share by ([\d.]+), a repeat", (1 / PILOT_PER_TYPE,)),
        Claim("results", "pilot text: the baseline's repeat", r"a repeat of the same (\d+) questions changed (\w+) answer of the baseline",
              (len(p["questions"]), len(g["the baseline's two runs differ on"]))),
        Claim("results", "pilot text: retrieval on the same questions", r"`RetrievalMemory` answered (\d+) and (\d+) of the same questions; the difference from the pilot's (\d+) and (\d+) is (\w+) question",
              (r[0]["correct"], r[1]["correct"], s["correct"], k["correct"], abs(s["correct"] - r[0]["correct"]) + abs(k["correct"] - r[1]["correct"]))),
        Claim("results", "reading: value in a shown fact", r"stood in a fact that was shown in (\d+) of the (\d+) questions, and (\d+) of the (\d+) were answered right",
              (in_fact, len(p["questions"]), in_fact_right, in_fact)),
        Claim("results", "reading: correct from the facts alone", r"the facts alone gave (\d+) of the (\d+) correct answers, (\d+) and (\d+)",
              (cb[("SSU", "korten")] + cb[("KU", "korten")], g["correct"], cb[("SSU", "korten")], cb[("KU", "korten")])),
        Claim("results", "rows: beyond 40,000 tokens", r"(\w+) of the (\d+) questions have more than 40,000 tokens between the evidence and the question, .*? On these (\w+) questions the judge accepted (\w+) answers here, (\w+) counted on content, since `(\w+)` is one of the (\w+)",
              (far, len(p["questions"]), far, far_right, far_right - len(far_unanswered), *far_unanswered, far_right)),
        Claim("results", "rows: beyond 40,000 tokens, the third row, another day", r"in the third row's run, made on other days, it accepted none",
              far_third == 0 and not {file.split("-")[-2] for file in PILOT.values()} & {RUNS["consolidating"].split("-")[-2]}),
        Claim("results", "facts: the changed value replaced", r"replaced the changed value in (\w+) of the (\w+) `knowledge-update` questions, and (\w+) of the (\w+) were answered right",
              (len(replaced), k["n"], replaced_right, len(replaced))),
        Claim("results", "facts: each by the question's newer value", r"In each of the (\w+) the earlier value's fact was replaced by the question's newer value",
              (g["those replaced by the question's newer fact"],)),
        Claim("results", "facts: no evidence-turn fact replaced by anything else", r"no fact that names an evidence turn was replaced by anything else",
              g["those replaced by the question's newer fact"] == g["facts naming an evidence turn: all / replaced / shown"][1] == len(replaced)),
        Claim("results", "facts: two names, and a value never a fact", r"In (\w+) questions the two values got different names, so both held and both were shown, and (\w+) was answered right; in (\w+) more one of the values never became a fact, and (\w+) was judged right",
              (len(both), both_right, len(never), never_right)),
        Claim("results", "facts: every changed value in one of the three", r"in two more one of the values never became a fact", g["every knowledge-update question in one group"]),
        Claim("results", "spike: the changed value kept its name", r"kept its name in (\d+) of the (\d+) histories \(0018\)", kind="external",
              note="ADR 0018's figure, by a hand reading; evals/verify_adr_0018.py finds it there"),
        Claim("results", "reading: the judge's count and on content", r"The judge's (\d+) of (\d+) is (\d+) of (\d+) counted on content",
              (k["correct"], k["n"], k["correct"] - len(wrong_on_content), k["n"])),
        Claim("results", "reading: the verdict counted as wrong on content", r"counted on content.\*\* `(\w+)` asks", tuple(wrong_on_content)),
        Claim("results", "reading: the errors and their boxes", r"The (\w+) errors sit in (\w+) places",
              (s["n"] - s["correct"] + k["n"] - k["correct"], len(g["error boxes"]))),
        Claim("results", "facts: every held evidence-turn fact shown", r"every fact that names an evidence turn and held was shown",
              g["facts naming an evidence turn, held and not shown"] == 0),
        Claim("results", "rows: b01defab, the baseline's window", r"began (\w+) turns earlier and held (\w+) turns of the later evidence session",
              (len(out), len(g["b01defab: of them from an evidence session"]))),
        Claim("results", "rows: b01defab, tokens", r"holds ([\d,]+) tokens of raw turns against the baseline's ([\d,]+), ([\d,]+) fewer, and the facts message holds ([\d,]+)",
              (raw_here, raw_base, fewer, g["b01defab: facts message tokens"])),
        Claim("results", "rows: b01defab, the third row's window and the verdicts", r"The third row's window on the question is the same as the pilot's, and both answered \"I do not know\"",
              g["b01defab: the consolidating run's window is this run's"] and raw_third == raw_here
              and g["b01defab: answers, baseline / consolidating / here"] == ("yes", "no", "no")),
        Claim("results", "rows: 0f05491a, 300 in the assistant's turn, every run", r"300 stands in the assistant's turn just before the user's correction to 120, in the context of all (\w+) runs",
              (len(g["0f05491a: runs with answer_d6d2eba8_2:5 in the context"]),)),
        Claim("results", "rows: 0f05491a, the printout and the answers", r"The two baseline runs answered 300 as well",
              g["0f05491a: answer_d6d2eba8_2:5 in the printout: role, says 300 stars"] == ("assistant", True)
              and len(g["0f05491a: runs with answer_d6d2eba8_2:5 in the context"]) == len(g["0f05491a: answers with 300"])
              and [n for n, v in g["0f05491a: answers with 300"].items() if v] == ["pilot baseline", "baseline", "here"]
              and not g["0f05491a: facts with 300 as a number"]),
        Claim("results", "rows: 0f05491a, the reference answer", r"just before the user's correction to (\d+), in the context", (g["_rows"]["0f05491a"]["gold_answer"],)),
        Claim("results", "facts: replaced of stored", r"The rule replaced (\d+) of the ([\d,]+) facts in the (\d+) histories", (n_replaced, stored, len(p["questions"]))),
        Claim("results", "facts: from evidence sessions, replaced", r"(\d+) of the (\d+) facts from evidence sessions were replaced, each by a fact of the question's other evidence session and none by a session without evidence",
              (from_evidence_replaced, from_evidence)),
        Claim("results", "facts: none replaced by a session without evidence", r"and none by a session without evidence", (by_evidence, by_others) == (from_evidence_replaced, 0)),
        Claim("results", "Claude Code's reading of the replacements", r"A rough reading of the (\d+) pairs of values, .*? sorts them as (\d+) the questions' own values, (\d+) the same thing with more detail, (\d+) where a real change cannot be ruled out, and (\d+) another thing under the same name",
              (n_replaced, reading["question"], reading["detail"], reading["open"], reading["other"])),
        Claim("results", "the reading covers every replacement", r"sorts them as", g["reading covers the replacements"]),
        Claim("results", "pilot text: list-order reach", r"the pilot's window reached the evidence in (\d+) of the (\d+) `knowledge-update` questions, against (\d+) in clock order",
              (k["reached_list_order"], k["listed"], k["reached"])),
        Claim("results", "pilot text: run cost, list-order replay", r"The harness counts \$([\d.]+) for the pilot run, \$([\d.]+) of it the list-order replay",
              (f"{run['cost']:.2f}", f"{listed:.2f}")),
        Claim("results", "M4 limitations: accepted answers", r"One of the (\d+) `knowledge-update` answers the judge accepted is not an answer by the reading \(`(\w+)`\)",
              (k["correct"], *wrong_on_content)),
        Claim("results", "M4 limitations: replacements read", r"The reading of the (\d+) replacements is Claude Code's", (n_replaced,)),
        Claim("results", "M4 limitations: the facts message", r"The facts message takes ([\d,]+) tokens from the window", (FACT_TOKENS,)),
        Claim("results", "M4 limitations: other subjects", r"(\d+) of the ([\d,]+) facts have a subject other than `user`",
              (g["subjects other than user: facts, shown, histories"][0], stored)),
        Claim("results", "M4 limitations: pilot size", r"The fourth strategy is a pilot on (\d+) questions, run once", (len(p["questions"]),)),
    ]


def claims_readme(f: dict) -> list[Claim]:
    """The overview in README.md: each strategy's correct answers per type and its cost per question over
    both types, and the pilot's correct answers."""
    c = f["cells"]

    def row(name: str) -> Claim:
        s, k = c[(name, SSU)], c[(name, KU)]
        cost = (s["cost_per_q"] * s["n"] + k["cost_per_q"] * k["n"]) / (s["n"] + k["n"])
        return Claim("readme", f"README: {NAMES[name]}", rf"`{NAMES[name]}`:[^|]*\| (\d+) of (\d+) \| (\d+) of (\d+) \| \$([\d.]+) \|",
                     (s["correct"], s["n"], k["correct"], k["n"], f"{cost:.3f}"))

    cs = [row(name) for name in RUNS]
    if "pilot" in f and (RESULTS / PILOT_REVIEW).exists():
        p = f["pilot"]
        (fourth,) = PILOT
        s, k = p["cells"][(fourth, SSU)], p["cells"][(fourth, KU)]
        cs.append(Claim("readme", "README: pilot", r"a pilot on (\d+) of the questions, of which it answered (\d+) of (\d+) and (\d+) of (\d+)",
                        (len(p["questions"]), s["correct"], s["n"], k["correct"], k["n"])))
    return cs


def main() -> int:
    f = compute()
    if "--check" not in sys.argv:
        print_tables(f)
        return 0
    text, readme = (re.sub(r"\s+", " ", path.read_text(encoding="utf-8")) for path in (DOC, README))
    cs = claims(f) + claims_readme(f)
    for c in cs:
        judge(c, readme if c.adr == "readme" else text)
        print(f"{c.status:12s} {c.label:40s} text {fmt(c.groups) if c.groups else '—':52s} computed {fmt(c.computed)}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
