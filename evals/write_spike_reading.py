"""Write the spike's saved replies out for reading by hand.

The hand readings ADR 0018 quotes were made from the spike's printed report.
This puts what they rest on in one file: the eight replacements round two's
model named, with the turns they point at, and for each of the eight histories
the facts every round extracted from its two evidence sessions, with what
round three replaced. It reads the saved replies and the pinned dataset, calls
no model and judges nothing; the last column of every table is left empty for
the reader. Nothing is truncated.

    .venv/bin/python evals/write_spike_reading.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import CHOSEN_N  # noqa: E402
from evals.longmemeval import QUESTIONS  # noqa: E402
from evals.spike_fact_graph import PROMPTS, prompt_id, replacements  # noqa: E402
from evals.verify_adr_0018 import SPIKE, line_of, saved  # noqa: E402
from evals.verify_adr_numbers import ROOT, TYPES, load_pinned  # noqa: E402

OUT = SPIKE / "reading.md"
ROUNDS = {
    1: "each session on its own, nothing replaced",
    2: "the facts so far given under numbers; the model names the numbers a new fact replaces",
    3: "the facts so far given; the code replaces on the same subject and relation",
}


def quote(text: str) -> list[str]:
    return [f"> {line}" for line in text.splitlines()] + [""]


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("$", "\\$").replace("\n", "<br>")


def table(header: tuple[str, ...], rows: list[tuple]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|---" * len(header) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return lines + [""]


class History:
    """One spike history: its dataset entry and what names its sessions and turns."""

    def __init__(self, x: dict) -> None:
        self.x = x
        self.qid = x["question_id"]
        self.date_of = dict(zip(x["haystack_session_ids"], x["haystack_dates"]))
        self.turns = dict(zip(x["haystack_session_ids"], x["haystack_sessions"]))
        # The evidence sessions in replay order, as the saved rows have them.
        self.evidence = [r["session_id"] for r in saved(1, self.qid) if r["evidence_turns"]]
        self.which = dict(zip(self.evidence, ("earlier", "later"))) if len(self.evidence) == 2 else {}

    def session(self, session_id: str) -> str:
        kind = f"{self.which[session_id]} evidence session" if session_id in self.which else \
            ("evidence session" if session_id in self.evidence else "no evidence")
        return f"{session_id}, {self.date_of[session_id]}, {kind}"

    def turn(self, row: dict, fact: dict) -> str:
        mark = ", evidence" if fact["turn"] in row["evidence_turns"] else ""
        return f"{fact['turn']}{mark}"

    def fact(self, row: dict, fact: dict) -> str:
        number = f"#{fact['number']} " if "number" in fact else ""
        role = self.turns[row["session_id"]][fact["turn"]]["role"]
        return f"{number}{line_of(fact)}\n{self.session(row['session_id'])}, turn {self.turn(row, fact)}, {role}"

    def text(self, row: dict, fact: dict) -> str:
        return self.turns[row["session_id"]][fact["turn"]]["content"]


def round_two(histories: list[History]) -> list[str]:
    rows = []
    for h in histories:
        replies = saved(2, h.qid)
        numbered = {fact["number"]: (r, fact) for r in replies for fact in r["facts"]}
        for old, (by_row, by) in sorted(replacements(replies).items()):
            old_row, old_fact = numbered[old]
            rows.append((len(rows) + 1, h.qid, h.fact(old_row, old_fact), h.text(old_row, old_fact),
                         h.fact(by_row, by), h.text(by_row, by), ""))
    lines = [f"## A. Round two: the {len(rows)} replacements", "",
             f"Prompt `{prompt_id(PROMPTS[2])}`: {ROUNDS[2]}. One row per fact the model named as replaced, "
             "in the order of the histories and then of the replaced fact's number.", ""]
    return lines + table(("", "history", "the old fact", "the turn it points at", "the new fact",
                          "the turn it points at", "my judgement"), rows)


def history_section(h: History) -> list[str]:
    x = h.x
    lines = [f"### {h.qid}", "",
             f"- question: {x['question']}",
             f"- gold answer: {x['answer']}",
             f"- question date: {x['question_date']}", ""]
    first = {r["session_id"]: r for r in saved(1, h.qid)}
    for session_id in h.evidence:
        row = first[session_id]
        lines += [f"**{h.session(session_id)}**, {row['turns']} turns, evidence in turn "
                  + ", ".join(map(str, row["evidence_turns"])), ""]
        for n in row["evidence_turns"]:
            t = h.turns[session_id][n]
            lines += [f"Turn {n}, {t['role']}:", ""] + quote(t["content"])

    rows = []
    for round_ in PROMPTS:
        replies = saved(round_, h.qid)
        by_session = {r["session_id"]: r for r in replies}
        replaced = replacements(replies) if round_ == 3 else {}
        for session_id in h.evidence:
            row = by_session[session_id]
            where = h.which.get(session_id, session_id)
            if not row["facts"]:
                rows.append((round_, where, "", "(no facts)" if not row["failed"] else "(no reply)", "", ""))
            for fact in row["facts"]:
                by = ""
                if fact.get("number") in replaced:
                    by_row, by_fact = replaced[fact["number"]]
                    by = h.fact(by_row, by_fact)
                number = f"#{fact['number']} " if "number" in fact else ""
                rows.append((round_, where, h.turn(row, fact), number + line_of(fact), by, ""))
    return lines + table(("round", "session", "turn", "fact", "replaced by, in round three", "my judgement"), rows)


def main() -> int:
    doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    by_id = {x["question_id"]: x for x in load_pinned()}
    histories = [History(by_id[q]) for t in TYPES for q in doc[t][CHOSEN_N:]]

    lines = [
        "# The spike's replies, for reading by hand", "",
        "Written by `evals/write_spike_reading.py` from the saved replies in this directory and the pinned dataset. "
        "No model was called and nothing here is a judgement: the last column of every table is empty, for the "
        "reader. A fact is written `subject / relation = value`. A turn is counted from 0 within its session, and "
        "\"evidence\" after a turn's number means the dataset marks that turn `has_answer`. Nothing is truncated.", "",
        "The three rounds, all over the same eight histories that no run measures:", "",
    ]
    lines += [f"- round {n}, prompt `{prompt_id(PROMPTS[n])}`: {text}" for n, text in ROUNDS.items()] + [""]
    lines += round_two(histories)
    lines += ["## B. The eight histories", "",
              "For each history: the question, the gold answer, its two evidence sessions with the marked turns, and "
              "every fact each round extracted from those two sessions, in the order of the reply. The numbers of "
              "rounds two and three are the ones the facts had in their round. The column \"replaced by\" is filled "
              "only for round three's facts that a later fact replaced, as round three ran.", ""]
    for h in histories:
        lines += history_section(h)

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(histories)} histories: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
