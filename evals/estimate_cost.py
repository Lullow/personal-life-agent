"""Estimate what the whole comparison costs at N questions per type (ADR 0010).

docs/vg-project.md fixes N from the estimated total cost of the comparison,
consolidation included. The answer and grading cost per question comes from
the M1 pilot's rows, with the per-message framing measured by
scripts/check_token_count.py, and is reconciled here against what OpenRouter
billed. The rest is a model, because two of the three strategies are not built:

* ConsolidatingMemory is modelled as a rolling summary rewritten after every
  session. Each call reads the session's turns, the previous summary of S
  tokens and PROMPT tokens of instruction, and writes S tokens. ADR 0009's
  list-order replay adds one more consolidation of the first ten
  knowledge-update questions. M3 checks its actual design against this model.
* RetrievalMemory embeds every turn once per question.
* Every strategy's answer call costs what the pilot's did: each fills the same
  budget (ADR 0007).

Prices and the exchange rate are external facts, read on the dates given.

    .venv/bin/python evals/estimate_cost.py            # the table
    .venv/bin/python evals/estimate_cost.py --check    # ADR 0010's figures against this script
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.longmemeval import load_questions  # noqa: E402
from evals.verify_adr_numbers import (  # noqa: E402
    ADR_DIR, KU, ROOT, TYPES, Claim, TiktokenCounter, build_records, fmt, judge, load_pinned,
    replay_order,
)

PILOT_ROWS = ROOT / "evals" / "results" / "recent-turns-20260927-132525.jsonl"
PILOT_QUESTIONS = 20
# Measured with scripts/check_token_count.py on 2026-09-27: the provider's input
# count was 4 tokens per message plus 3 per call above the harness's.
FRAMING_PER_MESSAGE, FRAMING_PER_CALL = 4, 3
# OpenRouter's activity page for 2026-09-27, and the check call's usage.cost.
BILLED_DAY, CHECK_CALL = 0.433, 0.0195525
# USD per million tokens, input and output, OpenRouter on 2026-09-27.
PRICES = {"gpt-4o-2024-08-06": (2.50, 10.00), "gpt-4o-mini-2024-07-18": (0.15, 0.60)}
EMBED_PRICE = 0.02  # text-embedding-3-small, OpenRouter on 2026-09-27
SEK_PER_USD = 9.9009  # ECB reference rate, 2026-09-25
CAP_SEK = 1000
PROMPT = 300  # the consolidation model's instruction tokens per call
SUMMARIES = (500, 1000, 2000)
STRATEGIES = 3
ORDER_REPLAYS = 10  # ADR 0009: the knowledge-update pilot questions, replayed in list order
CHOSEN_N, CONSOLIDATOR = 61, "gpt-4o-mini-2024-07-18"
CHECK_HISTORIES = 5  # the gpt-4o comparison ADR 0010 names: the first five knowledge-update questions
CAP_USD = CAP_SEK / SEK_PER_USD


def usd(tokens_in: float, tokens_out: float, model: str) -> float:
    price_in, price_out = PRICES[model]
    return (tokens_in * price_in + tokens_out * price_out) / 1e6


def pilot() -> dict:
    """What the pilot cost, as counted, with the measured framing, and per question."""
    rows = [json.loads(line) for line in PILOT_ROWS.read_text(encoding="utf-8").splitlines()]
    model = rows[0]["model"].split("/")[1]
    out: dict = {}
    for label in ("answer", "grade"):
        calls = [(r, c) for r in rows for c in r["calls"] if c["label"] == label]
        # An answer call carries the system prompt, the recalled messages and the
        # question; a grading call, the system prompt and one message.
        framing = sum(FRAMING_PER_MESSAGE * (2 + len(r["sources"]) if label == "answer" else 2)
                      + FRAMING_PER_CALL for r, _ in calls)
        tin, tout = sum(c["input_tokens"] for _, c in calls), sum(c["output_tokens"] for _, c in calls)
        out[label] = dict(counted=usd(tin, tout, model), framed=usd(tin + framing, tout, model))
    out["counted"] = sum(out[k]["counted"] for k in ("answer", "grade"))
    out["framed"] = sum(out[k]["framed"] for k in ("answer", "grade"))
    out["billed"] = BILLED_DAY - CHECK_CALL
    out["per_question"] = out["framed"] / PILOT_QUESTIONS
    for k in ("answer", "grade"):
        out[f"per_question_{k}"] = out[k]["framed"] / PILOT_QUESTIONS
    return out


def histories(data: dict, lists: dict) -> dict[str, dict]:
    """History tokens and sessions written, for every question in the lists."""
    counter = TiktokenCounter()
    out = {}
    for t in TYPES:
        for qid in lists[t][:CHOSEN_N]:
            x = data[qid]
            records = build_records(x, "clock")[0]
            out[qid] = dict(tokens=sum(counter.count(r.content) for r in records),
                            sessions=len(replay_order(x, "clock")))
    return out


def consolidation(h: dict, model: str, summary: int) -> float:
    s = h["sessions"]
    return usd(h["tokens"] + s * (summary + PROMPT), s * summary, model)


def estimate(n: int, model: str, summary: int, per_q: float, hist: dict, lists: dict) -> dict:
    ids = [q for t in TYPES for q in lists[t][:n]]
    answer_grade = per_q * (STRATEGIES * len(ids) - PILOT_QUESTIONS)  # the pilot rows are paid
    consolidate = sum(consolidation(hist[q], model, summary) for q in ids)
    consolidate += sum(consolidation(hist[q], model, summary) for q in lists[KU][:ORDER_REPLAYS])
    embed = sum(hist[q]["tokens"] for q in ids) * EMBED_PRICE / 1e6
    total = BILLED_DAY + answer_grade + consolidate + embed
    return dict(answer_grade=answer_grade, consolidate=consolidate, embed=embed, total=total,
                sek=total * SEK_PER_USD, share=total / CAP_USD)


def gpt4o_check(summary: int, per_q: float, hist: dict, lists: dict) -> float:
    """Consolidate the first five knowledge-update histories with gpt-4o, answer and grade them."""
    ids = lists[KU][:CHECK_HISTORIES]
    return sum(consolidation(hist[q], "gpt-4o-2024-08-06", summary) for q in ids) + per_q * len(ids)


def compute() -> dict:
    data = {x["question_id"]: x for x in load_pinned()}
    lists = load_questions(CHOSEN_N)
    p = pilot()
    hist = histories(data, lists)
    f = dict(pilot=p, cap_usd=CAP_USD, lists=lists, hist=hist)
    chosen = [hist[q] for t in TYPES for q in lists[t][:CHOSEN_N]]
    f["history mean"] = statistics.fmean(h["tokens"] for h in chosen)
    f["sessions mean"] = statistics.fmean(h["sessions"] for h in chosen)
    f["grid"] = {(n, m, s): estimate(n, m, s, p["per_question"], hist, lists)
                 for n in (30, 45, 61) for m in PRICES for s in SUMMARIES}
    f["check"] = {s: gpt4o_check(s, p["per_question"], hist, lists) for s in SUMMARIES}
    f["ku unused"] = len(lists[KU]) - CHOSEN_N
    return f


def print_table(f: dict) -> None:
    p = f["pilot"]
    print("pilot, 20 questions")
    print(f"  counted by the harness          ${p['counted']:.4f}")
    print(f"  with the measured framing       ${p['framed']:.4f}")
    print(f"  billed by OpenRouter            ${p['billed']:.4f}")
    print(f"  per question and strategy       ${p['per_question']:.4f} "
          f"(answer ${p['per_question_answer']:.4f}, grade ${p['per_question_grade']:.4f})")
    print(f"\nhistories at N={CHOSEN_N}: {f['history mean']:,.0f} tokens and {f['sessions mean']:.1f} sessions on average")
    print(f"cap: {CAP_SEK} SEK = ${f['cap_usd']:.2f} at {SEK_PER_USD} SEK/USD\n")
    print(f"{'N':>3} {'consolidator':23s} {'summary':>7} | {'answer+grade':>12} {'consolidation':>13} "
          f"{'embeddings':>10} | {'total $':>8} {'SEK':>6} {'of cap':>6}")
    for (n, m, s), e in f["grid"].items():
        print(f"{n:>3} {m:23s} {s:>7} | {e['answer_grade']:>12.2f} {e['consolidate']:>13.2f} {e['embed']:>10.2f} | "
              f"{e['total']:>8.2f} {e['sek']:>6.0f} {e['share']:>6.0%}")
    print(f"\ngpt-4o comparison on the first {CHECK_HISTORIES} knowledge-update histories: "
          + ", ".join(f"${f['check'][s]:.2f} at summary {s}" for s in SUMMARIES))
    print(f"knowledge-update questions in the list that N={CHOSEN_N} leaves unmeasured: {f['ku unused']}")


def claims(f: dict) -> list[Claim]:
    p, g = f["pilot"], f["grid"]
    lo, hi = g[(61, CONSOLIDATOR, 500)], g[(61, CONSOLIDATOR, 2000)]
    o500, o1000 = g[(61, "gpt-4o-2024-08-06", 500)], g[(61, "gpt-4o-2024-08-06", 1000)]
    n45, n30 = g[(45, "gpt-4o-2024-08-06", 1000)], g[(30, "gpt-4o-2024-08-06", 1000)]
    n30_2000 = g[(30, "gpt-4o-2024-08-06", 2000)]
    pct = lambda e: round(100 * e["share"])  # noqa: E731
    money = lambda v: f"{v:.2f}"  # noqa: E731
    return [
        Claim("0010", "pilot counted / framed / billed",
              r"counted \$(\d+\.\d+) for the pilot's 20 questions; with the measured framing, \$(\d+\.\d+); OpenRouter billed \$(\d+\.\d+)",
              (f"{p['counted']:.4f}", f"{p['framed']:.4f}", f"{p['billed']:.4f}")),
        Claim("0010", "per question: all / answer / grade",
              r"\$([\d.]+) per question and strategy: \$([\d.]+) to answer and \$([\d.]+) to grade",
              (f"{p['per_question']:.4f}", f"{p['per_question_answer']:.4f}", f"{p['per_question_grade']:.4f}")),
        Claim("0010", "framing per message / per call", r"(\d+) tokens per message and (\d+) per call",
              (FRAMING_PER_MESSAGE, FRAMING_PER_CALL)),
        Claim("0010", "history tokens / sessions", r"hold ([\d,]+) tokens in ([\d.]+) sessions on average",
              (round(f["history mean"]), f"{f['sessions mean']:.1f}")),
        Claim("0010", "prices", r"`gpt-4o-2024-08-06` at \$([\d.]+) and \$([\d.]+), `gpt-4o-mini-2024-07-18` at \$([\d.]+) and \$([\d.]+), `text-embedding-3-small` at \$([\d.]+)",
              (*(f"{v:.2f}" for v in PRICES["gpt-4o-2024-08-06"]), *(f"{v:.2f}" for v in PRICES[CONSOLIDATOR]), f"{EMBED_PRICE:.2f}"),
              kind="external", note="OpenRouter models API, 2026-09-27"),
        Claim("0010", "rate / cap", r"(\d+\.\d+) SEK per dollar.*?a cap of \$(\d+\.\d+)", (SEK_PER_USD, money(f["cap_usd"]))),
        Claim("0010", "PROMPT and summary range", r"(\d+) tokens of instruction, and writes S tokens, with S from (\d+) to (\d+)",
              (PROMPT, SUMMARIES[0], SUMMARIES[-1])),
        Claim("0010", "chosen: total range $ / SEK / share",
              r"\*\*\$([\d.]+) to \$([\d.]+)\*\*, (\d+) to (\d+) SEK, (\d+) to (\d+)% of the cap",
              (money(lo["total"]), money(hi["total"]), round(lo["sek"]), round(hi["sek"]), pct(lo), pct(hi))),
        Claim("0010", "gpt-4o at N=61: 500 / 1000", r"fits only with S = 500, at (\d+)% of the cap; at S = 1000 it is (\d+)%",
              (pct(o500), pct(o1000))),
        Claim("0010", "gpt-4o, S=1000: N=45 / N=30 / N=30 at S=2000",
              r"at N = 45 and S = 1000 it takes (\d+)%, at N = 30 (\d+)%, and at N = 30 with S = 2000 (\d+)%",
              (pct(n45), pct(n30), pct(n30_2000))),
        Claim("0010", "gpt-4o check on five histories: 500 / 2000",
              r"costs \$([\d.]+) to \$([\d.]+) with the answers and their grading",
              (money(f["check"][500]), money(f["check"][2000]))),
        Claim("0010", "embeddings at N=61", r"embedding every history costs \$([\d.]+)",
              (money(g[(61, CONSOLIDATOR, 500)]["embed"]),)),
        Claim("0010", "one question at N=61", r"one question moves a share by ([\d.]+)", (f"{1 / CHOSEN_N:.3f}",)),
        Claim("0010", "KU questions unmeasured", r"leaves the last (\d+) of the 69", (f["ku unused"],)),
    ]


def main() -> int:
    f = compute()
    if "--check" not in sys.argv:
        print_table(f)
        return 0
    paths = sorted(ADR_DIR.glob("0010-*.md"))
    if not paths:
        raise SystemExit("no ADR 0010 to check")
    text = re.sub(r"\s+", " ", paths[0].read_text(encoding="utf-8"))
    cs = claims(f)
    for c in cs:
        judge(c, text)
        print(f"{c.status:12s} {c.label:48s} text {fmt(c.groups) if c.groups else '—':40s} "
              f"computed {fmt(c.computed)}{'  ' + c.note if c.note else ''}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
