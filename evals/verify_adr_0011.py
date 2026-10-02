"""Recompute the figures in ADR 0011 from the pinned dataset.

The figures describe the histories ADR 0010 measures: how the tokens and the
evidence divide between user and assistant turns, and which records are too
large for the budget. Nothing here ranks or recalls anything.

    .venv/bin/python evals/verify_adr_0011.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import CHOSEN_N, FRAMING_PER_MESSAGE  # noqa: E402
from evals.longmemeval import load_questions  # noqa: E402
from evals.verify_adr_numbers import (  # noqa: E402
    ADR_DIR, TYPES, Claim, TiktokenCounter, build_records, fmt, judge, load_pinned,
)
from life_agent.agent.memory import DEFAULT_BUDGET_TOKENS  # noqa: E402


def compute() -> dict:
    data = {x["question_id"]: x for x in load_pinned()}
    lists = load_questions(CHOSEN_N)
    counter = TiktokenCounter()
    tokens: Counter[str] = Counter()
    evidence_roles: Counter[str] = Counter()
    evidence_sizes: list[int] = []
    histories = too_large = too_large_evidence = 0
    for t in TYPES:
        for qid in lists[t][:CHOSEN_N]:
            records, _, evidence = build_records(data[qid], "clock")
            histories += 1
            for r in records:
                size = counter.count(r.content)
                tokens[r.role] += size
                too_large += size > DEFAULT_BUDGET_TOKENS
                if r.id in evidence:
                    evidence_roles[r.role] += 1
                    evidence_sizes.append(size)
                    too_large_evidence += size > DEFAULT_BUDGET_TOKENS
    return dict(histories=histories, assistant_share=tokens["assistant"] / sum(tokens.values()),
                evidence=len(evidence_sizes), evidence_user=evidence_roles["user"],
                too_large=too_large, too_large_evidence=too_large_evidence,
                largest_evidence=max(evidence_sizes))


def claims(f: dict) -> list[Claim]:
    return [
        Claim("0011", "histories measured", r"In the (\d+) histories that 0010 measures", (f["histories"],)),
        Claim("0011", "share of tokens in assistant turns", r"assistant turns hold (\d+)% of the tokens",
              (round(100 * f["assistant_share"]),)),
        Claim("0011", "evidence turns: user / all", r"(\d+) of the (\d+) evidence turns are user turns",
              (f["evidence_user"], f["evidence"])),
        Claim("0011", "records larger than the budget", r"(\w+) records are larger than the budget",
              (f["too_large"],)),
        Claim("0011", "…none of them evidence", r"None of them is evidence", f["too_large_evidence"] == 0),
        Claim("0011", "largest evidence turn", r"the largest evidence turn is (\d+) tokens",
              (f["largest_evidence"],)),
        Claim("0011", "framing per message", r"Every message adds (\d+) input tokens", (FRAMING_PER_MESSAGE,)),
        Claim("0011", "embeddings at N=61", r"The \$([\d.]+) that 0010 set aside for embeddings",
              kind="external", note="ADR 0010; evals/estimate_cost.py --check"),
        Claim("0011", "k1 / b", r"`k1 = ([\d.]+)` and `b = ([\d.]+)`, the defaults of Lucene",
              kind="external", note="Lucene's BM25Similarity"),
        Claim("0011", "LongMemEval commit", r"commit `(d0c699fa[0-9a-f]{32})`",
              kind="external", note="src/retrieval/run_retrieval.py, lines 35 and 213–215"),
    ]


def main() -> int:
    paths = sorted(ADR_DIR.glob("0011-*.md"))
    if not paths:
        raise SystemExit("no ADR 0011 to check")
    text = re.sub(r"\s+", " ", paths[0].read_text(encoding="utf-8"))
    cs = claims(compute())
    for c in cs:
        judge(c, text)
        print(f"{c.status:12s} {c.label:40s} text {fmt(c.groups) if c.groups else '—':44s} "
              f"computed {fmt(c.computed)}{'  ' + c.note if c.note else ''}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
