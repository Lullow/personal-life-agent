"""The figures in the M3 review, from the run's rows and the author's reading notes.

The reading notes (`evals/results/lasning-m3-anteckningar.md`) sort every
question into a box. This script checks the boxes against the rows, counts
what the rows alone can say, and prints every figure the review quotes.

    .venv/bin/python evals/m3_review_figures.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import KU, ROOT, SSU  # noqa: E402
from life_agent.agent.memory import SUMMARY_TARGET_TOKENS  # noqa: E402

RESULTS = ROOT / "evals" / "results"
RUN = RESULTS / "consolidating-20261003-233313.jsonl"
NOTES = RESULTS / "lasning-m3-anteckningar.md"
CORRECT_BOXES = ("anteckningarna", "fönstret", "båda", "gissning")
DISTANCE_BINS = ((0, 8000), (8000, 20000), (20000, 40000), (40000, 70000), (70000, None))
SENTENCE_ENDS = ".!?\"”’)»。！？"


def rows() -> dict[str, dict]:
    return {r["question_id"]: r for r in map(json.loads, RUN.read_text(encoding="utf-8").splitlines())}


def boxes() -> dict[str, tuple[str, str]]:
    """question id -> (type, box) from the notes' `id TYP: box — comment` lines."""
    text = NOTES.read_text(encoding="utf-8")
    out = {}
    for qid, t, rest in re.findall(r"^([0-9a-f]{8}) (KU|SSU): (.*)$", text, re.M):
        out[qid] = (t, rest.split(" — ")[0].strip())
    return out


def idk(r: dict) -> bool:
    return "not know" in (r["answer"] or "").lower()


def outputs(r: dict) -> list[int]:
    return [c["output_tokens"] for c in r["calls"] if c["label"] == "consolidate" and not c["failed"]]


def compute() -> dict:
    rs, bx = rows(), boxes()
    f: dict = {}
    f["labelled"] = len(bx)
    f["labels cover the rows"] = set(bx) == set(rs)
    f["box agrees with correct"] = all(
        (box.startswith(CORRECT_BOXES)) == bool(rs[q]["correct"]) for q, (_, box) in bx.items())
    ku_err = [q for q, (t, box) in bx.items() if t == "KU" and not rs[q]["correct"]]
    ssu_err = [q for q, (t, box) in bx.items() if t == "SSU" and not rs[q]["correct"]]
    right = [q for q in bx if rs[q]["correct"]]
    f["errors"] = (len(ku_err), len(ssu_err))
    f["correct"] = len(right)
    f["KU boxes"] = Counter(bx[q][1] for q in ku_err)
    f["SSU boxes"] = Counter(bx[q][1] for q in ssu_err)
    f["correct boxes"] = Counter((bx[q][0], bx[q][1].split(",")[0]) for q in right)
    f["KU idk"] = (sum(idk(rs[q]) for q in ku_err), [q for q in ku_err if not idk(rs[q])])
    f["SSU idk"] = (sum(idk(rs[q]) for q in ssu_err), [q for q in ssu_err if not idk(rs[q])])
    noll = lambda qs: [q for q in qs if bx[q][1].startswith("nollställda")]  # noqa: E731
    f["KU nollställda"] = (len(noll(ku_err)), sorted(rs[q]["summary_tokens"] for q in noll(ku_err)),
                           min(rs[q]["summary_tokens"] for q in ku_err if q not in noll(ku_err)))
    f["SSU nollställda"] = (len(noll(ssu_err)), sorted(rs[q]["summary_tokens"] for q in noll(ssu_err)),
                            min(rs[q]["summary_tokens"] for q in ssu_err if q not in noll(ssu_err)))
    # The ask-again collapsing the notes: a reply over S followed by one under 30% of it.
    collapses = {}
    for q, r in rs.items():
        o = outputs(r)
        n = sum(1 for a, b in zip(o, o[1:]) if a > SUMMARY_TARGET_TOKENS and b < 0.3 * a)
        if n:
            collapses[q] = n
    f["collapses"] = (sum(collapses.values()), len(collapses))
    f["nollställda with a collapse"] = sum(q in collapses for q in noll(ku_err) + noll(ssu_err))
    f["nollställda without"] = [q for q in noll(ku_err) + noll(ssu_err) if q not in collapses]
    # Final notes ending without sentence punctuation, and whether the reply held more than the summary.
    mid = [q for q, r in rs.items() if r["summary"].rstrip()[-1:] not in SENTENCE_ENDS]
    f["mid-sentence endings"] = {q: dict(last_output=outputs(rs[q])[-1], summary_tokens=rs[q]["summary_tokens"],
                                         failed_calls=sum(c["failed"] for c in rs[q]["calls"])) for q in mid}
    # Language of the final notes.
    cjk = [q for q, r in rs.items() if len(re.findall(r"[一-鿿]", r["summary"])) > 50]
    stop = {"the", "and", "user", "is", "to", "of", "a", "for", "in", "they"}

    def english(s: str) -> float:
        w = re.findall(r"[A-Za-z]+", s.lower())
        return sum(x in stop for x in w) / max(1, len(w))
    f["non-English finals"] = sorted(set(cjk) | {q for q, r in rs.items() if english(r["summary"]) < 0.12})
    f["36580ce8"] = dict(tokens=rs["36580ce8"]["summary_tokens"], spaces=rs["36580ce8"]["summary"].count(" "),
                         ascii_full_stops=rs["36580ce8"]["summary"].count("."),
                         cjk_full_stops=rs["36580ce8"]["summary"].count("。"),
                         last_outputs=outputs(rs["36580ce8"])[-3:])
    # Size and distance against correctness.
    st = [r["summary_tokens"] for r in rs.values()]
    f["summary tokens under 300 / 600 / 800, at least 900"] = (
        sum(x < 300 for x in st), sum(x < 600 for x in st), sum(x < 800 for x in st), sum(x >= 900 for x in st))
    f["correct under 600 / at least 600"] = (
        (sum(r["correct"] for r in rs.values() if r["summary_tokens"] < 600), sum(r["summary_tokens"] < 600 for r in rs.values())),
        (sum(r["correct"] for r in rs.values() if r["summary_tokens"] >= 600), sum(r["summary_tokens"] >= 600 for r in rs.values())))
    f["correct by distance"] = []
    for lo, hi in DISTANCE_BINS:
        g = [r for r in rs.values() if lo <= r["distance_tokens"] and (hi is None or r["distance_tokens"] < hi)]
        f["correct by distance"].append((lo, hi, sum(r["correct"] for r in g), len(g)))
    f["evidence consolidated everywhere"] = all(r["evidence_consolidated"] == 1.0 for r in rs.values())
    f["skipped: questions, sessions"] = (sum(1 for r in rs.values() if r["consolidations_failed"]),
                                         sum(r["consolidations_failed"] for r in rs.values()))
    f["603deb26 restating turn in window"] = "answer_8afdebac_2:10" in rs["603deb26"]["sources"]
    f["07741c45"] = (rs["07741c45"]["verdict"], rs["07741c45"]["answer"])
    f["4100d0a0"] = (rs["4100d0a0"]["evidence_reached"], rs["4100d0a0"]["answer"])
    f["reached in window: questions, correct"] = (sum(r["evidence_reached"] for r in rs.values()),
                                                   sum(r["correct"] for r in rs.values() if r["evidence_reached"]))
    return f


def main() -> int:
    f = compute()
    for k, v in f.items():
        print(f"{k:50s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
