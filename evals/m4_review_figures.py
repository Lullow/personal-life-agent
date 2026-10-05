"""The figures in the review of the M4 pilot, from the run's rows, its facts and the author's reading notes.

The reading notes (`evals/results/lasning-m4-anteckningar.md`) sort every
question into a box and say, fact by fact, what the model was shown. This
script checks them against the rows, against the facts the run left in its
graphs (`fact-graph-20261005-161632-facts.jsonl`, written by
`evals/export_fact_graphs.py`) and against the dataset, counts what those
alone can say, and prints every figure the review quotes.

    .venv/bin/python evals/m4_review_figures.py            # the figures
    .venv/bin/python evals/m4_review_figures.py --check    # the notes, statement by statement, against them
    .venv/bin/python evals/m4_review_figures.py --facts    # per question, the facts of its evidence sessions
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import COUNTER, KU, ROOT, SSU, TYPES, Claim, build_records, fmt, judge, load_pinned  # noqa: E402

RESULTS = ROOT / "evals" / "results"
RUN = RESULTS / "fact-graph-20261005-161632.jsonl"
FACTS = RESULTS / "fact-graph-20261005-161632-facts.jsonl"
NOTES = RESULTS / "lasning-m4-anteckningar.md"
# The other runs' rows for the same questions: the M1 pilot, and the three runs of the comparison.
OTHERS = {
    "pilot baseline": "recent-turns-20260927-132525.jsonl",
    "baseline": "recent-turns-20261002-193902.jsonl",
    "retrieval": "retrieval-20261002-193417.jsonl",
    "consolidating": "consolidating-20261003-233313.jsonl",
}
CORRECT_BOXES = ("korten", "fönstret", "båda", "gissning")
ERROR_BOXES = ("utdraget", "regeln", "urvalet", "genereringen", "nästan rätt")
SHORT = {SSU: "SSU", KU: "KU"}
SV = {0: "noll", 1: "en", 2: "två", 3: "tre", 4: "fyra", 5: "fem", 6: "sex"}
# For each knowledge-update question: the fact the notes name for the newer value, the earlier value as the
# notes give it (a fact, or the bare value), and what the notes say became of the earlier one. Transcribed
# from the notes' rows; the check holds every string here to the row it was taken from.
CHANGED = {
    "07741c45": ("old_sneakers_storage_plan = storing old sneakers in a shoe rack", "sneaker_storage = under bed", "held"),
    "b6019101": ("watched_mcu_films_count = 5", "4", "replaced"),
    "6071bd76": ("french_press_ratio = 1 tablespoon of coffee for every 5 ounces of water", "6 ounces", "never a fact"),
    "a2f3aa27": ("instagram_followers = 1300", "1250", "replaced"),
    "c6853660": ("coffee_intake = two cups in the morning", "coffee_intake = one cup in the morning", "replaced"),
    "b01defab": (None, "current_reading = The Nightingale", "held"),
    "0f05491a": ("starbucks_gold_level_stars_needed = 120", "125", "replaced"),
    "6aeb4375": ("korean_restaurant_visits = four different ones", "three different ones recently", "replaced"),
    "06db6396": ("completed_projects = 5", "4", "replaced"),
    "89941a94": ("trip_bike_count = four bikes", "number_of_bikes = 3", "held"),
}
# The words of the reference answer to look for in a fact's value, where the answer is not one string.
ANSWER_WORDS = {"6b168ec8": "3", "66f24dbb": "yellow dress", "6071bd76": "5 ounces", "6aeb4375": "four",
                "89941a94": "road bike"}
# The instructions the notes found in a window, by question.
INSTRUCTIONS = (
    ("a2f3aa27", "For all my future prompts , always answer in short blocks, after each one stop and ask me if to continue. please confirm"),
    ("36580ce8", "ME3.2, and as usual, please give it a nice heading."),
    ("8ebdbe50", "Act as the CTO"),
    ("8ebdbe50", "Continue"),
    ("86f00804", "continue"),
)
NUMBER_300 = re.compile(r"(?<![\d,.])300(?![\d,])")


# -- what is read --------------------------------------------------------------

def run_rows(path: Path) -> dict[str, dict]:
    rs = sorted(map(json.loads, path.read_text(encoding="utf-8").splitlines()),
                key=lambda r: (TYPES.index(r["question_type"]), r["position"]))
    return {r["question_id"]: r for r in rs}


def rows() -> dict[str, dict]:
    """The pilot's rows by question id, in the order of the question lists."""
    return run_rows(RUN)


def facts() -> dict[str, list[dict]]:
    """question id -> the facts of its clock-order replay, the one the question was asked against, as stored."""
    out: dict[str, list[dict]] = {}
    for f in map(json.loads, FACTS.read_text(encoding="utf-8").splitlines()):
        if f["order"] == "clock":
            out.setdefault(f["question_id"], []).append(f)
    return out


def notes_rows() -> dict[str, tuple[str, str, str]]:
    """question id -> (type, box, the whole row) from the notes' `id TYP: box — comment` lines."""
    text = NOTES.read_text(encoding="utf-8")
    return {qid: (t, rest.split(" — ")[0].strip(), rest)
            for qid, t, rest in re.findall(r"^([0-9a-f]{8}) (KU|SSU): (.*)$", text, re.M)}


def histories(ids: set[str]) -> dict[str, dict]:
    """question id -> its turns by record id, from the pinned dataset (ADR 0004)."""
    out = {}
    for x in load_pinned():
        if x["question_id"] in ids:
            records, _, _ = build_records(x)
            out[x["question_id"]] = {r.id: r for r in records}
    return out


# -- helpers -------------------------------------------------------------------

def line(f: dict) -> str:
    return f"{f['subject']} / {f['relation']} = {f['value']}"


def short(f: dict) -> str:
    return f"{f['relation']} = {f['value']}"


def session_of(turn_id: str) -> str:
    return turn_id.rsplit(":", 1)[0]


def idk(r: dict) -> bool:
    return "not know" in (r["answer"] or "").lower()


def states(r: dict, fs: list[dict]) -> list[dict]:
    """Each fact of a question with what the row says about it: shown, replaced and by what, from the evidence."""
    by_id = {f["id"]: f for f in fs}
    shown, evidence = set(r["sources"]), set(r["evidence"])
    sessions = {session_of(e) for e in evidence}
    return [dict(f, shown=f["id"] in shown, replaced=f["replaced_by"] is not None,
                 replacer=by_id.get(f["replaced_by"]),
                 evidence_turn=f["turn_id"] in evidence, evidence_session=f["session_id"] in sessions)
            for f in fs]


def facts_agree(r: dict, fs: list[dict]) -> bool:
    """The exported facts are the ones the row counted: every count, and every fact shown one that holds."""
    st = states(r, fs)
    shown = [s for s in r["sources"] if s.startswith("fact:")]
    return (len(fs) == r["facts_stored"]
            and sum(f["replaced"] for f in st) == r["facts_replaced"]
            and sum(not f["replaced"] for f in st) == r["facts_held"]
            and len(shown) == r["facts_shown"] == sum(f["shown"] for f in st)
            and not any(f["shown"] and f["replaced"] for f in st)
            and all(f["replacer"] is not None for f in st if f["replaced"])
            and sum(f["evidence_turn"] for f in st) == r["evidence_turn_facts"]
            and sum(f["evidence_turn"] and f["replaced"] for f in st) == r["evidence_turn_facts_replaced"]
            and sum(f["evidence_turn"] and f["shown"] for f in st) == r["evidence_turn_facts_shown"]
            and r["facts_message"] == "\n".join(line(f) for f in st if f["shown"]))


def find(st: list[dict], text: str) -> list[dict]:
    """The facts a `relation = value` of the notes names."""
    return [f for f in st if short(f).casefold() == text.casefold()]


def window(r: dict, turns: dict) -> list[str]:
    """The raw turns of a row's context, in order: its sources without the ids that are no turn."""
    return [s for s in r["sources"] if s in turns]


def changed(q: str, st: list[dict]) -> dict:
    """What the facts say of a knowledge-update question's two values, next to what the notes say (CHANGED)."""
    newer_text, earlier_text, said = CHANGED[q]
    newer = find(st, newer_text) if newer_text else []
    if " = " in earlier_text:
        earlier = find(st, earlier_text)
    else:  # a bare value: the fact of that value under the newer fact's relation, if there is one
        earlier = [f for f in st if newer and f["relation"] == newer[0]["relation"] and f["value"].casefold() == earlier_text.casefold()]
    if not earlier:
        found = "never a fact" if not any(earlier_text.casefold() in f["value"].casefold() for f in st) else "another fact"
    elif all(f["replaced"] for f in earlier):
        by_newer = newer and all(f["replaced_by"] == newer[0]["id"] for f in earlier)
        found = "replaced" if by_newer else "replaced by another fact"
    else:
        found = "held" if all(f["shown"] for f in earlier) else "held, not shown"
    return dict(newer=newer, earlier=earlier, said=said, found=found,
                newer_shown=bool(newer) and all(f["shown"] for f in newer),
                newer_names_evidence=bool(newer) and all(f["evidence_turn"] for f in newer))


# -- the figures ---------------------------------------------------------------

def compute() -> dict:
    rs, fs, nr = rows(), facts(), notes_rows()
    others = {name: run_rows(RESULTS / file) for name, file in OTHERS.items()}
    turns = histories(set(rs))
    tokens = COUNTER.count
    st = {q: states(rs[q], fs[q]) for q in rs}
    every = [(q, x) for q in rs for x in st[q]]
    wrong = [q for q in rs if not rs[q]["correct"]]
    of_type = lambda t: [q for q in rs if rs[q]["question_type"] == t]  # noqa: E731
    f: dict = {"_rows": rs, "_states": st, "_notes": nr, "_turns": turns, "_others": others}

    f["questions"] = Counter(SHORT[r["question_type"]] for r in rs.values())
    f["commit"] = sorted({r["commit"] for r in rs.values()})
    f["facts file covers the rows"] = set(fs) == set(rs)
    f["facts agree with the rows"] = all(facts_agree(rs[q], fs[q]) for q in rs)
    f["wrong"] = {SHORT[t]: [q for q in of_type(t) if q in wrong] for t in TYPES}
    f["correct"] = len(rs) - len(wrong)
    f["idk"] = [q for q in rs if idk(rs[q])]
    f["verdicts"] = Counter(r["verdict"] for r in rs.values())
    reached = [q for q in rs if rs[q]["evidence_reached"]]
    f["evidence in the window: questions, correct"] = (reached, sum(bool(rs[q]["correct"]) for q in reached))
    f["correct without evidence in the window"] = sum(bool(rs[q]["correct"]) for q in rs if q not in reached)
    f["raw turns of an evidence session in the window"] = {
        q: sorted({session_of(s) for s in window(rs[q], turns[q])} & {session_of(e) for e in rs[q]["evidence"]})
        for q in rs if {session_of(s) for s in window(rs[q], turns[q])} & {session_of(e) for e in rs[q]["evidence"]}}

    # The two values of each knowledge-update question (the notes' table "vad hände med det ändrade värdet").
    ch = {q: changed(q, st[q]) for q in of_type(KU)}
    f["_changed"] = ch
    f["changed value: notes / facts"] = {q: (c["said"], c["found"]) for q, c in ch.items()}
    f["newer fact shown"] = {q: c["newer_shown"] for q, c in ch.items()}
    f["earlier replaced by the newer: questions, correct"] = (
        [q for q, c in ch.items() if c["found"] == "replaced"],
        sum(bool(rs[q]["correct"]) for q, c in ch.items() if c["found"] == "replaced"))
    f["both held and shown: questions, correct"] = (
        [q for q, c in ch.items() if c["found"] == "held" and c["newer_shown"]],
        sum(bool(rs[q]["correct"]) for q, c in ch.items() if c["found"] == "held" and c["newer_shown"]))
    f["one value never a fact: questions, correct"] = (
        [q for q, c in ch.items() if c["found"] == "never a fact" or not c["newer"]],
        sum(bool(rs[q]["correct"]) for q, c in ch.items() if c["found"] == "never a fact" or not c["newer"]))
    f["newer fact names a turn that is no evidence turn"] = [q for q, c in ch.items() if c["newer"] and not c["newer_names_evidence"]]
    f["evidence turns no fact names"] = {
        q: sorted(e for e in rs[q]["evidence"] if not any(x["turn_id"] == e for x in st[q]))
        for q in rs if any(not any(x["turn_id"] == e for x in st[q]) for e in rs[q]["evidence"])}

    # What the rule replaced (ADR 0018 counts the harm next to the gain).
    replaced = [(q, x) for q, x in every if x["replaced"]]
    f["facts stored / replaced"] = (len(every), len(replaced))
    f["replaced by type"] = {SHORT[t]: sum(x["replaced"] for q in of_type(t) for x in st[q]) for t in TYPES}
    f["replaced, by question"] = {q: sum(x["replaced"] for x in st[q]) for q in rs}
    f["replaced, most common relations"] = Counter(x["relation"] for _, x in replaced).most_common(6)
    from_evidence = [(q, x) for q, x in every if x["evidence_session"]]
    ev_sessions = lambda q: {session_of(e) for e in rs[q]["evidence"]}  # noqa: E731
    f["facts from evidence sessions: all / replaced / shown"] = (
        len(from_evidence), sum(x["replaced"] for _, x in from_evidence), sum(x["shown"] for _, x in from_evidence))
    f["of those replaced: by an evidence session / by a session without evidence"] = (
        sum(x["replacer"]["session_id"] in ev_sessions(q) for q, x in from_evidence if x["replaced"]),
        sum(x["replacer"]["session_id"] not in ev_sessions(q) for q, x in from_evidence if x["replaced"]))
    f["facts naming an evidence turn: all / replaced / shown"] = (
        sum(x["evidence_turn"] for _, x in every), sum(x["evidence_turn"] and x["replaced"] for _, x in every),
        sum(x["evidence_turn"] and x["shown"] for _, x in every))
    f["facts naming an evidence turn, held and not shown"] = sum(
        x["evidence_turn"] and not x["replaced"] and not x["shown"] for _, x in every)
    f["facts naming an evidence turn, replaced"] = [
        (q, short(x), f"-> {x['replacer']['value']}", x["replacer"]["session_id"]) for q, x in every if x["evidence_turn"] and x["replaced"]]
    f["those replaced by the question's newer fact"] = sum(
        bool(ch[q]["newer"]) and x["replaced_by"] == ch[q]["newer"][0]["id"] for q, x in every if x["evidence_turn"] and x["replaced"])
    f["replaced where the new value contains the old"] = sum(
        x["value"].casefold() in x["replacer"]["value"].casefold() for _, x in replaced)
    borrowed = lambda sid: sid.startswith(("sharegpt", "ultrachat"))  # noqa: E731
    f["replaced with a ShareGPT or UltraChat session on either side"] = sum(
        borrowed(x["session_id"]) or borrowed(x["replacer"]["session_id"]) for _, x in replaced)
    f["replaced neither from nor by an evidence session"] = sum(
        not x["evidence_session"] and x["replacer"]["session_id"] not in ev_sessions(q) for q, x in replaced)
    chain = [x for x in st["95bcc1c8"] if x["relation"] == "trip_destination"]
    f["95bcc1c8 trip_destination: replaced, days from the first to the last"] = (
        sum(x["replaced"] for x in chain),
        (date.fromisoformat(max(x["at"] for x in chain)[:10]) - date.fromisoformat(min(x["at"] for x in chain)[:10])).days + 1)
    f["b01defab yoga_classes_frequency"] = [x["value"] for x in st["b01defab"] if x["relation"] == "yoga_classes_frequency"]
    f["6071bd76 cooking_class_participant"] = [x["value"] for x in st["6071bd76"] if x["relation"] == "cooking_class_participant"]
    f["8ebdbe50 contact_persons"] = [(x["value"], x["replacer"]["value"] if x["replaced"] else None)
                                    for x in st["8ebdbe50"] if x["relation"] == "contact_persons"]
    f["07741c45 closet_organization_plan"] = [x["value"] for x in st["07741c45"] if x["relation"] == "closet_organization_plan"]

    # Subjects, repeated names, and where the facts shown come from.
    other = [(q, x) for q, x in every if x["subject"].casefold() != "user"]
    f["subjects other than user: facts, shown, histories"] = (len(other), sum(x["shown"] for _, x in other), len({q for q, _ in other}))
    f["subjects other than user"] = Counter((q, x["subject"]) for q, x in other)
    f["subjects other than user, shown"] = [(q, line(x)) for q, x in other if x["shown"]]
    held_names: dict = {}
    for q, x in every:
        if not x["replaced"]:
            held_names.setdefault((q, x["subject"].casefold(), x["relation"].casefold()), []).append(x)
    again = {k: v for k, v in held_names.items() if len(v) > 1}
    f["names held more than once: all / across sessions"] = (len(again), sum(len({x["session_id"] for x in v}) > 1 for v in again.values()))
    f["names shown more than once"] = {(k[0], k[2]): sum(x["shown"] for x in v) for k, v in again.items() if sum(x["shown"] for x in v) > 1}
    shown = [(q, x) for q, x in every if x["shown"]]
    origin = lambda q, x: ("evidence session" if x["evidence_session"] else  # noqa: E731
                           "ShareGPT or UltraChat" if borrowed(x["session_id"]) else "other session of the benchmark")
    f["facts shown by origin: facts"] = dict(Counter(origin(q, x) for q, x in shown))
    by_origin: Counter = Counter()
    per_question: dict = {q: Counter() for q in rs}
    for q, x in shown:
        by_origin[origin(q, x)] += tokens(line(x))
        per_question[q][origin(q, x)] += tokens(line(x))
    f["facts shown by origin: tokens of their lines"] = dict(by_origin)
    f["share of the shown lines' tokens from ShareGPT or UltraChat"] = round(by_origin["ShareGPT or UltraChat"] / sum(by_origin.values()), 3)
    f["the same, per question, largest"] = sorted(
        ((round(c["ShareGPT or UltraChat"] / sum(c.values()), 2), q) for q, c in per_question.items()), reverse=True)[:4]
    f["facts naming an assistant turn: stored / shown"] = (
        sum(turns[q][x["turn_id"]].role == "assistant" for q, x in every),
        sum(turns[q][x["turn_id"]].role == "assistant" for q, x in shown))

    # b01defab: what the facts message's tokens cost the window.
    q = "b01defab"
    ours, base = window(rs[q], turns[q]), window(others["baseline"][q], turns[q])
    out = [s for s in base if s not in ours]
    f["b01defab: first raw turn, baseline / consolidating / here"] = (
        base[0], window(others["consolidating"][q], turns[q])[0], ours[0])
    f["b01defab: raw tokens in the window, baseline / here"] = (
        sum(tokens(turns[q][s].content) for s in base), sum(tokens(turns[q][s].content) for s in ours))
    f["b01defab: turns the baseline had and this run did not, their tokens"] = (out, sum(tokens(turns[q][s].content) for s in out))
    f["b01defab: of them from an evidence session, their tokens"] = (
        [s for s in out if session_of(s) in ev_sessions(q)],
        sum(tokens(turns[q][s].content) for s in out if session_of(s) in ev_sessions(q)))
    f["b01defab: facts message tokens"] = rs[q]["facts_message_tokens"]
    f["b01defab: turns naming The Nightingale, baseline / consolidating / here"] = tuple(
        [s for s in window(r[q], turns[q]) if "Nightingale" in turns[q][s].content] for r in (others["baseline"], others["consolidating"], rs))
    f["b01defab: answers, baseline / consolidating / here"] = (
        others["baseline"][q]["verdict"], others["consolidating"][q]["verdict"], rs[q]["verdict"])
    f["b01defab: facts naming The Nightingale"] = [short(x) for x in st[q] if "nightingale" in short(x).casefold()]

    # 0f05491a: where the 300 of the answer stands.
    q = "0f05491a"
    f["0f05491a: turns in the window with 300 as a number"] = [
        (s, turns[q][s].role) for s in window(rs[q], turns[q]) if NUMBER_300.search(turns[q][s].content)]
    f["0f05491a: the same for the pilot baseline / baseline / consolidating"] = tuple(
        [(s, turns[q][s].role) for s in window(others[name][q], turns[q]) if NUMBER_300.search(turns[q][s].content)]
        for name in ("pilot baseline", "baseline", "consolidating"))
    f["0f05491a: facts with 300 as a number"] = [short(x) for x in st[q] if NUMBER_300.search(x["value"])]
    f["0f05491a: answers with 300"] = {name: bool(NUMBER_300.search(r[q]["answer"])) for name, r in (*others.items(), ("here", rs))}
    f["0f05491a: turns of the later evidence session in the window / in the session"] = (
        sum(session_of(s) == "answer_d6d2eba8_2" for s in window(rs[q], turns[q])),
        sum(session_of(s) == "answer_d6d2eba8_2" for s in turns[q]))

    # c8c3f81d and c6853660: the turn a fact names, and the evidence turn.
    f["c8c3f81d: facts of the evidence session, the turn each names"] = [
        (short(x), x["turn"]) for x in st["c8c3f81d"] if x["evidence_session"]]
    f["c8c3f81d: evidence consolidated"] = rs["c8c3f81d"]["evidence_consolidated"]
    f["c6853660: the newer fact's turn, the evidence turn of its session"] = (
        ch["c6853660"]["newer"][0]["turn"],
        [int(e.rsplit(":", 1)[1]) for e in rs["c6853660"]["evidence"] if session_of(e) == ch["c6853660"]["newer"][0]["session_id"]])
    f["c6853660: 'increased' in the turn the newer fact names"] = "increased" in turns["c6853660"][ch["c6853660"]["newer"][0]["turn_id"]].content

    # The boxes of the reading.
    f["labelled"] = len(nr)
    f["labels cover the rows"] = set(nr) == set(rs)
    f["label types agree"] = all(SHORT[rs[q]["question_type"]] == t for q, (t, _, _) in nr.items())
    f["box agrees with correct"] = all(box.startswith(CORRECT_BOXES) == bool(rs[q]["correct"]) for q, (_, box, _) in nr.items())
    f["error boxes"] = Counter(nr[q][1].split(",")[0] for q in wrong)
    f["correct boxes"] = Counter((nr[q][0], nr[q][1].split(",")[0]) for q in rs if q not in wrong)
    return f


# -- the notes, statement by statement -----------------------------------------

def claims(f: dict) -> list[Claim]:
    rs, st, nr, turns, others, ch = f["_rows"], f["_states"], f["_notes"], f["_turns"], f["_others"], f["_changed"]
    wrong = [q for q in rs if not rs[q]["correct"]]
    right = [q for q in rs if rs[q]["correct"]]
    boxed = lambda box, qs: [q for q in qs if nr[q][1].split(",")[0] == box]  # noqa: E731
    tagged = lambda tag: [q for q in rs if tag in nr[q][1]]  # noqa: E731
    in_notes = lambda q, text: text in nr[q][2]  # noqa: E731
    ids = lambda qs: r", ".join([r"`(\w+)`"] * len(qs))  # noqa: E731
    cs = [
        Claim("notes", "run, commit", r"Körning: fact-graph-20261005-161632, commit `(\w+)`", tuple(f["commit"])),
        Claim("notes", "wrong and correct answers read", r"\((\d+) fel\) och `lasning-m4-2-ratt.md` \((\d+) rätta\)", (len(wrong), len(right))),
        Claim("notes", "wrong, all knowledge-update", r"# Fel \((\d+), alla KU\)", (len(wrong),)),
        Claim("notes", "wrong, all knowledge-update (types)", r"# Fel \(\d+, alla KU\)", all(rs[q]["question_type"] == KU for q in wrong)),
        Claim("notes", "correct", r"# Rätta svar \((\d+)\)", (len(right),)),
        Claim("notes", "every row labelled, types as in the rows", r"# Fel \(", f["labels cover the rows"] and f["label types agree"]),
        Claim("notes", "box agrees with the judge's verdict", r"# Rätta svar \(", f["box agrees with correct"]),
        Claim("notes", "'urvalet' empty: questions", r"i alla (\d+) frågor visades varje kort som pekar på en evidenstur", (len(rs),)),
        Claim("notes", "'urvalet' empty: every such fact shown", r"visades varje kort som pekar på en evidenstur och gällde",
              f["facts naming an evidence turn, held and not shown"] == 0),
    ]
    # The cards a row quotes: each is a fact of that question, shown, or replaced where the row says so.
    for q, (_, _, row) in nr.items():
        for text in re.findall(r'"([A-Za-z_0-9]+ = [^"]+)"', row):
            found = find(st[q], text)
            expect_replaced = q in CHANGED and CHANGED[q][1] == text and CHANGED[q][2] == "replaced"
            ok = bool(found) and all((x["replaced"] and not x["shown"]) if expect_replaced else x["shown"] for x in found)
            cs.append(Claim("notes", f"{q}: {'replaced' if expect_replaced else 'shown'}: {text[:44]}", re.escape(text), ok))
    # A correct answer in "korten" has no evidence in the window; in "båda" it has; the later turn where the row says so.
    for q in right:
        box = nr[q][1].split(",")[0]
        cs.append(Claim("notes", f"{q}: box and window", rf"{q} (?:KU|SSU): {box}",
                        rs[q]["evidence_reached"] == (box in ("fönstret", "båda"))))
        if "senare evidensturen i fönstret" in nr[q][2]:
            cs.append(Claim("notes", f"{q}: the later evidence turn in the window", rf"{q} KU: [^`]*?senare evidensturen i fönstret",
                            rs[q]["ku_breakdown"] in ("later", "both")))
        if "slutsats" not in nr[q][1]:
            words = ANSWER_WORDS.get(q, rs[q]["gold_answer"]).casefold()
            quoted = [x for text in re.findall(r'"([A-Za-z_0-9]+ = [^"]+)"', nr[q][2]) for x in find(st[q], text)]
            cs.append(Claim("notes", f"{q}: the answer is a quoted fact's value", rf"{q} (?:KU|SSU): {box}",
                            any(words in x["value"].casefold() for x in quoted)))
    # The two values of each knowledge-update question.
    for q, (newer, earlier, said) in CHANGED.items():
        cs.append(Claim("notes", f"{q}: transcribed from its row", rf"{q} KU:",
                        (newer is None or in_notes(q, newer)) and in_notes(q, earlier)))
        cs.append(Claim("notes", f"{q}: earlier value {said}", rf"{q} KU:", ch[q]["found"] == said))
        if newer:
            cs.append(Claim("notes", f"{q}: newer value shown", rf"{q} KU:", ch[q]["newer_shown"]))
    replaced, replaced_right = f["earlier replaced by the newer: questions, correct"]
    both, both_right = f["both held and shown: questions, correct"]
    never, never_right = f["one value never a fact: questions, correct"]
    only_new = [q for q in right if q in ch and ch[q]["newer_shown"] and not (ch[q]["found"] == "held")]
    both_shown = [q for q in right if q in ch and ch[q]["newer_shown"] and ch[q]["found"] == "held"]
    with_value = [q for q in rs if nr[q][1].split(",")[0] != "utdraget" and "slutsats" not in nr[q][1]]
    reached, reached_right = f["evidence in the window: questions, correct"]
    cs += [
        # The four wrong answers.
        Claim("notes", "07741c45: no 'closet' in the newer fact", r"`07741c45` \| delvis \(\"shoe rack\", inte \"closet\"\) \| ja \| inte ersatt, gäller och visas \|",
              "shoe rack" in ch["07741c45"]["newer"][0]["value"] and "closet" not in ch["07741c45"]["newer"][0]["value"]),
        Claim("notes", "07741c45: judged as in M3", r"underkänt som i M3", others["consolidating"]["07741c45"]["verdict"] == rs["07741c45"]["verdict"] == "no"),
        Claim("notes", "c6853660: table row", r"`c6853660` \| ja \| ja \| ersatt \(rätt\) \|", ch["c6853660"]["newer_shown"] and ch["c6853660"]["found"] == "replaced"),
        Claim("notes", "b01defab: table row", r"`b01defab` \| nej \| – \| inte ersatt, gäller och visas \|",
              f["b01defab: facts naming The Nightingale"] == ["current_reading = The Nightingale"] and ch["b01defab"]["found"] == "held"),
        Claim("notes", "0f05491a: table row", r"`0f05491a` \| ja \| ja \| ersatt \(rätt\) \|", ch["0f05491a"]["newer_shown"] and ch["0f05491a"]["found"] == "replaced"),
        Claim("notes", "0f05491a: the later evidence turn in the window", r"den senare evidensturen ligger dessutom i fönstret", rs["0f05491a"]["ku_breakdown"] == "later"),
        Claim("notes", "0f05491a: the evidence turn's words", r"\(\"I need 120 stars … not 300\"\)",
              any(e in window(rs["0f05491a"], turns["0f05491a"]) and "I need 120 stars" in turns["0f05491a"][e].content
                  and "not 300" in turns["0f05491a"][e].content for e in rs["0f05491a"]["evidence"])),
        Claim("notes", "0f05491a: 300 as in the pilot and in M2", r"svaret blev 300, samma tal som baslinjen i piloten och i M2",
              all(f["0f05491a: answers with 300"][k] for k in ("here", "pilot baseline", "baseline"))),
        Claim("notes", "0f05491a: 300 in no fact", r"`0f05491a` ett tal som inte står i något kort", not f["0f05491a: facts with 300 as a number"]),
        *(Claim("notes", f"error boxes: {box}", rf"\| {box} \| (\d+) \|", (len(boxed(box, wrong)),)) for box in ERROR_BOXES),
        Claim("notes", "error boxes: sum", r"\| summa \| (\d+) \|", (len(wrong),)),
        Claim("notes", "'I do not know' among the wrong", rf"(\w+) av de (\w+) svaren är \"I do not know\" \({ids(f['idk'])}\)",
              [{SV[len(f["idk"])].capitalize()}, {SV[len(wrong)]}, set(f["idk"])], kind="sets"),
        Claim("notes", "'I do not know' only among the wrong", r"svaren är \"I do not know\"", set(f["idk"]) <= set(wrong)),
        # The sixteen correct answers.
        *(Claim("notes", f"correct boxes: {box}", rf"\| {box} \| (\d+) \| (\d+) \| (\d+) \|",
                (len([q for q in boxed(box, right) if nr[q][0] == "SSU"]), len([q for q in boxed(box, right) if nr[q][0] == "KU"]), len(boxed(box, right))))
          for box in CORRECT_BOXES),
        Claim("notes", "correct boxes: sum", r"\| summa \| (\d+) \| (\d+) \| (\d+) \|",
              (sum(nr[q][0] == "SSU" for q in right), sum(nr[q][0] == "KU" for q in right), len(right))),
        Claim("notes", "correct KU: only the newer value shown / both", rf"bara det nya värdet visades i (\d+) \({ids(only_new)}\), båda värdena i (\d+) \({ids(both_shown)}\)",
              [{str(len(only_new))}, set(only_new), {str(len(both_shown))}, set(both_shown)], kind="sets"),
        Claim("notes", "51a45a95: Target not in the evidence turn", r"\"Target\" står inte i evidensmeningen",
              not any("Target" in turns["51a45a95"][e].content for e in rs["51a45a95"]["evidence"])),
        Claim("notes", "a2f3aa27: the evidence turn's words", r"datat säger \"I think I'm close to 1300\"",
              any("I think I'm close to 1300" in turns["a2f3aa27"][e].content for e in rs["a2f3aa27"]["evidence"])),
        Claim("notes", "07741c45: the evidence turn's words", r"\"looking forward to get rid of some of my old sneakers in a shoe rack\"",
              any("looking forward to get rid of some of my old sneakers in a shoe rack" in turns["07741c45"][e].content for e in rs["07741c45"]["evidence"])),
        # What became of the changed value.
        Claim("notes", "KU: earlier replaced by the newer", rf"\| gamla ersatt av nya, bara nya visas \| (\d+) \| {ids(replaced)} \| (\d+) \|",
              [{str(len(replaced))}, set(replaced), {str(replaced_right)}], kind="sets"),
        Claim("notes", "KU: both held and shown", rf"\| båda gäller och visas \(namnet byttes\) \| (\d+) \| {ids(both)} \| (\d+) \|",
              [{str(len(both))}, set(both), {str(both_right)}], kind="sets"),
        Claim("notes", "KU: one value never a fact", r"\| ett av värdena blev aldrig kort \| (\d+) \| `(\w+)` \(gamla saknas\), `(\w+)` \(nya saknas\) \| (\d+) \|",
              (len(never), *[q for q in never if ch[q]["newer"]], *[q for q in never if not ch[q]["newer"]], never_right)),
        Claim("notes", "KU: both held under two names", r"båda gäller och visas \(namnet byttes\)",
              all(ch[q]["newer"][0]["relation"] != ch[q]["earlier"][0]["relation"] for q in both)),
        Claim("notes", "replaced facts naming an evidence turn", r"I alla (\w+) fall där regeln ersatte ett kort som pekar på en evidenstur",
              (SV[f["facts naming an evidence turn: all / replaced / shown"][1]],)),
        Claim("notes", "each replaced by the question's newer value", r"var det frågans nya värde som ersatte det gamla",
              f["those replaced by the question's newer fact"] == f["facts naming an evidence turn: all / replaced / shown"][1]),
        Claim("notes", "value in a shown fact", rf"stod i ett visat kort i (\d+) av (\d+) frågor. Undantagen är `(\w+)` \(blev aldrig kort\) och `(\w+)` \(bara som slutsats\). (\d+) av de (\d+) blev rätt",
              (len(with_value), len(rs), *boxed("utdraget", wrong), *tagged("slutsats"), sum(bool(rs[q]["correct"]) for q in with_value), len(with_value))),
        Claim("notes", "value in a shown fact, wrong", r"de tre andra är `(\w+)`, `(\w+)` och `(\w+)`", [{q for q in with_value if q in wrong}], kind="sets"),
        Claim("notes", "evidence in the window", rf"Evidensen låg i fönstret i (\d+) frågor \({ids(reached)}\), (\d+) av dem rätt",
              [{str(len(reached))}, set(reached), {str(reached_right)}], kind="sets"),
        Claim("notes", "correct from the facts alone", r"Korten ensamma gav (\d+) rätta svar \((\d+) SSU, (\d+) KU\)",
              (len(boxed("korten", right)), len([q for q in boxed("korten", right) if nr[q][0] == "SSU"]), len([q for q in boxed("korten", right) if nr[q][0] == "KU"]))),
        Claim("notes", "questions tagged as asking for the change", r"På de (\w+) frågor som gäller ändringen eller det tidigare läget", (SV[len(tagged("frågar efter"))],)),
        Claim("notes", "verdicts not named", r"De övriga (\d+) utslagen är rimliga", (len(rs) - 3,)),
        # The questions the notes leave for the rows.
        Claim("notes", "b01defab: first raw turn of the window", r"Här börjar fönstret i nästa samtal \(`([\w:]+)`\)", (f["b01defab: first raw turn, baseline / consolidating / here"][2],)),
        Claim("notes", "c8c3f81d: facts naming the evidence turn", r"\"facts naming an evidence turn\" är (\d+)", (rs["c8c3f81d"]["evidence_turn_facts"],)),
        Claim("notes", "c8c3f81d: evidence consolidated", r"\"Evidence consolidated\" är ändå ([\d.]+)", (f"{f['c8c3f81d: evidence consolidated']:.2f}",)),
        Claim("notes", "c8c3f81d: no fact holds 'favourite'", r"meningen \"Nike has been my favourite brand\" finns inte i något kort",
              "Nike has been my favourite brand" in turns["c8c3f81d"]["answer_761acef8:6"].content
              and not any("favo" in short(x).casefold() and "nike" in short(x).casefold() for x in st["c8c3f81d"])),
        Claim("notes", "c6853660: the newer fact's turn and the evidence turn", r"det nya värdets kort pekar på tur :(\d+), inte evidensturen :(\d+)",
              (f["c6853660: the newer fact's turn, the evidence turn of its session"][0], *f["c6853660: the newer fact's turn, the evidence turn of its session"][1])),
        Claim("notes", "rule in KU: replaced, of questions", r"Regeln i KU: (\d+) av (\d+) här", (len(replaced), len(ch))),
        Claim("notes", "facts from an evidence turn: replaced, all (KU)", r"\"facts from an evidence turn: replaced\" \((\d+) av (\d+)\)",
              (sum(rs[q]["evidence_turn_facts_replaced"] for q in ch), sum(rs[q]["evidence_turn_facts"] for q in ch))),
        Claim("notes", "replaced, by type", r"(\d+) kort är ersatta i SSU-frågorna och (\d+) i KU-frågorna", (f["replaced by type"]["SSU"], f["replaced by type"]["KU"])),
        Claim("notes", "95bcc1c8: trip_destination", r"`trip_destination` byts (\w+) gånger på (\w+) dagar i `95bcc1c8`",
              tuple(SV[n] for n in f["95bcc1c8 trip_destination: replaced, days from the first to the last"])),
        Claim("notes", "b01defab: yoga_classes_frequency", r"`yoga_classes_frequency` går \"twice a week\" → \"Vinyasa flow classes\" → \"twice a week\" i `b01defab`",
              f["b01defab yoga_classes_frequency"] == ["twice a week", "Vinyasa flow classes", "twice a week"]),
        Claim("notes", "6071bd76: cooking_class_participant", r"`cooking_class_participant` går från \"mom\" till \"three months ago\" i `6071bd76`",
              f["6071bd76 cooking_class_participant"] == ["mom", "three months ago"]),
        Claim("notes", "8ebdbe50: contact_persons", r"(\w+) `contact_persons` ersätts av en \"Emily\" i `8ebdbe50`",
              (SV[sum(new == "Emily" for _, new in f["8ebdbe50 contact_persons"])],)),
        Claim("notes", "07741c45: closet_organization_plan", r"`closet_organization_plan` går från \"organizing closet by type\" till \"this weekend\" i `07741c45`",
              f["07741c45 closet_organization_plan"] == ["organizing closet by type", "this weekend"]),
        Claim("notes", "c8c3f81d: Ruth in the facts message", r"`Ruth / attracted_to = women` står i kortmeddelandet i `c8c3f81d`",
              "Ruth / attracted_to = women" in rs["c8c3f81d"]["facts_message"].splitlines()),
        Claim("notes", "names shown more than once", r"(\w+) `network_event` i `8ebdbe50` och (\w+) `trip_activity` i `95bcc1c8`",
              (SV[f["names shown more than once"].get(("8ebdbe50", "network_event"), 0)].capitalize(),
               SV[f["names shown more than once"].get(("95bcc1c8", "trip_activity"), 0)])),
    ]
    # The instructions the notes found in a window, and that no answer followed.
    for q, text in INSTRUCTIONS:
        w = window(rs[q], turns[q])
        cs.append(Claim("notes", f"{q}: instruction in the window: {text[:24]}", re.escape(text),
                        any(turns[q][s].role == "user" and text in turns[q][s].content for s in w)))
    last_user = [s for s in window(rs["36580ce8"], turns["36580ce8"]) if turns["36580ce8"][s].role == "user"][-1]
    cs.append(Claim("notes", "36580ce8: the last user message before the question", r"som sista användarmeddelande före frågan i `36580ce8`",
                    turns["36580ce8"][last_user].content == INSTRUCTIONS[1][1]))
    return cs


def print_facts(f: dict) -> None:
    for q, r in f["_rows"].items():
        print(f"\n{q} {SHORT[r['question_type']]} correct={r['correct']} evidence in the window={r['evidence_reached']}")
        print(f"  question: {r['question']}\n  gold: {r['gold_answer']}\n  answer: {r['answer']}")
        for x in f["_states"][q]:
            if x["evidence_session"]:
                state = f"replaced by {x['replacer']['id']} ({line(x['replacer'])})" if x["replaced"] else "holds"
                print(f"  {'*' if x['evidence_turn'] else ' '} {x['id']} turn {x['turn']}: {line(x)} | "
                      f"{'shown' if x['shown'] else 'not shown'}, {state}")


def main() -> int:
    f = compute()
    if "--check" in sys.argv:
        text = re.sub(r"\s+", " ", NOTES.read_text(encoding="utf-8"))
        cs = claims(f)
        for c in cs:
            judge(c, text)
            print(f"{c.status:12s} {c.label:62s} notes {fmt(c.groups) if c.groups else '—':40s} computed {fmt(c.computed)}")
        tally = Counter(c.status for c in cs)
        print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
        return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0
    for k, v in f.items():
        if not k.startswith("_"):
            print(f"{k:76s} {v}")
    if "--facts" in sys.argv:
        print_facts(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
