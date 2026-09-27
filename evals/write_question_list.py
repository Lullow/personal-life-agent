"""Write evals/longmemeval_questions.json, the question order ADR 0005 fixes.

Eligibility is the rule in verify_adr_numbers.py; this script only orders it.
Within each type, questions are sorted by sha256(question_id), ascending, and a
run of N per type takes the first N of each list. The file is written once and
committed. If it already exists, the script never overwrites it: it recomputes
the order and says whether the committed file still matches, exiting 1 if not.

    .venv/bin/python evals/write_question_list.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import (  # noqa: E402
    DATASET, DATASET_SHA256, ROOT, TYPES, load_pinned, pool_of,
)

OUT = ROOT / "evals" / "longmemeval_questions.json"


def order_key(question_id: str) -> str:
    return hashlib.sha256(question_id.encode()).hexdigest()


def question_list(data: list[dict]) -> dict:
    pool = pool_of(data)
    doc: dict = {
        "rule": "docs/adr/0005-which-questions-are-measured.md",
        "dataset": DATASET.name,
        "dataset_sha256": DATASET_SHA256,
        "order": "sha256(question_id), ascending",
    }
    for t in TYPES:
        doc[t] = sorted((x["question_id"] for x in pool if x["question_type"] == t), key=order_key)
    return doc


def main() -> int:
    doc = question_list(load_pinned())
    text = json.dumps(doc, indent=2) + "\n"
    counts = ", ".join(f"{len(doc[t])} {t}" for t in TYPES)
    if OUT.exists():
        if OUT.read_text(encoding="utf-8") == text:
            print(f"{OUT.relative_to(ROOT)} matches the rule: {counts}")
            return 0
        print(f"{OUT.relative_to(ROOT)} does NOT match the rule; it was not overwritten")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
