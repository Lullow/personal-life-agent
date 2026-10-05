"""Write the special-case dump and the KU labelling worksheet under data/.

Both are for reading by hand and live in a git-ignored directory. Turn text is
written in full, never truncated. The worksheet holds the knowledge-update
questions that ADR 0005 admits, in file order rather than the sha256 order of
0005, so it does not reveal which questions a run draws. Its label column is
left empty. The file committed later holds only question_id and label.

    .venv/bin/python evals/write_reading_files.py
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import (  # noqa: E402
    DATASET, KU, ROOT, evidence_sessions, exclusion_reasons, when,
)

OUT = ROOT / "data" / "longmemeval"


def evidence_turns(x):
    """Every has_answer turn, ordered by session date, then list position."""
    out = []
    for i in sorted(evidence_sessions(x), key=lambda i: (when(x["haystack_dates"][i]), i)):
        for j, t in enumerate(x["haystack_sessions"][i]):
            if t.get("has_answer"):
                out.append(dict(session_id=x["haystack_session_ids"][i], date=x["haystack_dates"][i],
                                list_position=i, turn_index=j, role=t["role"], content=t["content"]))
    return out


def fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def main() -> int:
    """Write both files, over what is there. Only when run: an import writes nothing."""
    data = json.loads(DATASET.read_bytes())
    by_id = {x["question_id"]: x for x in data}

    # -- 3. special cases --------------------------------------------------------
    lines = ["# Special cases: 618f13b2, 2133c1b5, e66b632c", "",
             "Full text from longmemeval_s_cleaned.json. Evidence turns are the turns marked",
             "`has_answer: true`, ordered by session date. Nothing is truncated.", ""]
    for qid in ("618f13b2", "2133c1b5", "e66b632c"):
        x = by_id[qid]
        lines += [f"## {qid}", "",
                  f"- question_type: {x['question_type']}",
                  f"- question_date: {x['question_date']}",
                  f"- answer_session_ids: {', '.join(x['answer_session_ids'])}",
                  f"- question: {x['question']}",
                  f"- answer: {x['answer']}", ""]
        for n, e in enumerate(evidence_turns(x), start=1):
            f = fence(e["content"])
            lines += [f"### Evidence turn {n}: {e['session_id']}:{e['turn_index']}, {e['role']}", "",
                      f"Session date {e['date']}; position {e['list_position']} in the list.", "",
                      f + "text", e["content"], f, ""]
    (OUT / "special_cases.md").write_text("\n".join(lines), encoding="utf-8")

    # -- 4. KU worksheet ---------------------------------------------------------
    pool_ku = [x for x in data if x["question_type"] == KU and not exclusion_reasons(x)]
    max_ev = max(len(evidence_turns(x)) for x in pool_ku)
    header = ["question_id", "question", "answer", "question_date"]
    for n in range(1, max_ev + 1):
        header += [f"evidence_{n}_session_id", f"evidence_{n}_date", f"evidence_{n}_role", f"evidence_{n}_text"]
    header.append("label")
    with (OUT / "ku_labeling_worksheet.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for x in pool_ku:
            row = [x["question_id"], x["question"], str(x["answer"]), x["question_date"]]
            ev = evidence_turns(x)
            for n in range(max_ev):
                row += [ev[n]["session_id"], ev[n]["date"], ev[n]["role"], ev[n]["content"]] if n < len(ev) else ["", "", "", ""]
            row.append("")
            w.writerow(row)

    print("special cases:", OUT / "special_cases.md")
    print("worksheet:", OUT / "ku_labeling_worksheet.csv", "rows:", len(pool_ku), "max evidence turns:", max_ev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
