"""A probe, not a measurement: the facts of one history, drawn as a graph in Neo4j.

Before an ADR fixes how a fact graph is built, this looks at what an extraction
gives. Each session of a history goes to the consolidator's model once, as
quoted transcript, and comes back as (subject, relation, value) triples; each
triple is drawn as an edge that carries its session, its turn and the session's
time. No question is answered, nothing is graded, and no figure printed here is
a result.

It has three rounds, each with its own prompt. The first replaces nothing:
whether the model names one relation the same way in two sessions is what a
rule that replaces on the name would rest on, and on the eight histories it
did not (one changed value in eight kept its name). The other two ask the
sessions in order and give each call the facts no later fact has replaced. In
the second the facts are numbered and the model names the numbers a new fact
makes out of date; it rarely did, and never for a changed value the question
is about, but seeing the earlier facts it reused their names. In the third the
model is told that a fact with the subject and relation of an earlier one
replaces it, and the code replaces on exactly that; it replaced an old value
where the name was kept, and more often an unrelated fact that shared a
general name. A replaced fact is kept, with the time it was replaced.

It only takes the histories no run measures: the questions ADR 0005 admits
beyond the first 61 of a type (ADR 0010). The prompts below are shaped on what
they show, so a measured history must never pass through here.

The replies are saved under data/longmemeval/spike/, one file per history and
prompt, so the graph can be drawn again without a model call. Drawing needs a
running Neo4j and its password in .env as LIFE_AGENT_NEO4J_PASSWORD
(LIFE_AGENT_NEO4J_URI and _USER default to bolt://localhost:7687 and neo4j):

    docker run -d --name life-agent-neo4j -p 127.0.0.1:7474:7474 \\
        -p 127.0.0.1:7687:7687 -e NEO4J_AUTH=neo4j/<password> neo4j:5.26.31

    .venv/bin/python evals/spike_fact_graph.py 5c40ec5b --dry-run    # no model, no database
    .venv/bin/python evals/spike_fact_graph.py 5c40ec5b --no-graph   # calls the model; no database
    .venv/bin/python evals/spike_fact_graph.py 5c40ec5b              # saved replies if any, then Neo4j
    .venv/bin/python evals/spike_fact_graph.py 5c40ec5b --facts      # every fact, session by session
    .venv/bin/python evals/spike_fact_graph.py 5c40ec5b --round 3    # the facts so far shown; replaced on the name

A history has one graph in Neo4j: drawing a round replaces the other round's.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.longmemeval import ATTEMPTS, CONSOLIDATOR_MODEL, QUESTIONS, cost_of, real_client, usd  # noqa: E402
from evals.verify_adr_numbers import ROOT, TYPES, TiktokenCounter, build_records, load_pinned  # noqa: E402
from life_agent.agent.memory import MemoryRecord, TokenCounter  # noqa: E402
from life_agent.agent.recording import LLMCall, RecordingLLMClient  # noqa: E402
from life_agent.config import env_value  # noqa: E402

SPIKE = ROOT / "data" / "longmemeval" / "spike"
MEASURED_PER_TYPE = 61  # ADR 0010: the first 61 of each type are measured

# Not written for LongMemEval, and its three example names are in no question
# of the list. One JSON object comes back and nothing dispatches on it.
FACT_SYSTEM_PROMPT = (
    "You keep the assistant's memory of facts about the user. You are given the\n"
    "transcript of one conversation between the user and the assistant, every turn\n"
    "numbered in brackets. List what the user says about themselves and about the\n"
    "people, places and things in their life: what they have, like, do, plan and\n"
    "have done, with the names, numbers, dates and places. Leave out general\n"
    "knowledge, the assistant's advice, and what the user only asks about.\n"
    'Each fact is one triple with the turn it comes from. subject: "user", or the\n'
    "name of the person or thing the fact is about. relation: what is said about\n"
    "the subject, as a short general name in English, lower_snake_case, the name\n"
    "you would choose again if the same fact came up with another value\n"
    "(blood_type, dentist_name, number_of_siblings). value: the value, as short as\n"
    "the conversation allows, in the language of the conversation. turn: the\n"
    "number of the turn. When the conversation gives two values for the same\n"
    "thing, give only the current one. Reply with a JSON object:\n"
    '{"facts": [{"subject": "...", "relation": "...", "value": "...", "turn": 0}]}.\n'
    'With nothing to list, reply {"facts": []}.'
)

# Round two. The first round's prompt with the facts so far added, and a
# replaces list per fact; its one new example is in no question either.
REPLACING_SYSTEM_PROMPT = (
    "You keep the assistant's memory of facts about the user. You are given the\n"
    "facts so far, numbered, and the transcript of one more conversation between\n"
    "the user and the assistant, every turn numbered in brackets. List what the\n"
    "user says in this conversation about themselves and about the people, places\n"
    "and things in their life: what they have, like, do, plan and have done, with\n"
    "the names, numbers, dates and places. Leave out general knowledge, the\n"
    "assistant's advice, and what the user only asks about.\n"
    'Each fact is one triple with the turn it comes from. subject: "user", or the\n'
    "name of the person or thing the fact is about. relation: what is said about\n"
    "the subject, as a short general name in English, lower_snake_case, the name\n"
    "you would choose again if the same fact came up with another value\n"
    "(blood_type, dentist_name, number_of_siblings). value: the value, as short as\n"
    "the conversation allows, in the language of the conversation. turn: the\n"
    "number of the turn. replaces: the numbers of the facts so far that this fact\n"
    "makes out of date, because it is a newer value for the same thing, whatever\n"
    "name the old fact's relation has. A fact about another person, thing or\n"
    "occasion than the old fact's replaces nothing: a second allergy does not\n"
    "replace the first. Most facts replace nothing, and the list is empty. When\n"
    "the conversation gives two values for the same thing, give only the current\n"
    "one. Reply with a JSON object:\n"
    '{"facts": [{"subject": "...", "relation": "...", "value": "...", "turn": 0,\n'
    '"replaces": []}]}. With nothing to list, reply {"facts": []}.'
)

# Round three. No replaces list: the code replaces on the subject and relation,
# and the prompt says so.
KEYED_SYSTEM_PROMPT = (
    "You keep the assistant's memory of facts about the user. You are given the\n"
    "facts so far and the transcript of one more conversation between the user\n"
    "and the assistant, every turn numbered in brackets. List what the user says\n"
    "in this conversation about themselves and about the people, places and\n"
    "things in their life: what they have, like, do, plan and have done, with the\n"
    "names, numbers, dates and places. Leave out general knowledge, the\n"
    "assistant's advice, and what the user only asks about.\n"
    'Each fact is one triple with the turn it comes from. subject: "user", or the\n'
    "name of the person or thing the fact is about. relation: what is said about\n"
    "the subject, as a short name in English, lower_snake_case (blood_type,\n"
    "dentist_name, number_of_siblings). value: the value, as short as the\n"
    "conversation allows, in the language of the conversation. turn: the number\n"
    "of the turn.\n"
    "A fact with the subject and relation of a fact so far replaces it. So when\n"
    "the user gives a newer value for one of the facts so far, use exactly its\n"
    "subject and relation; and give a fact about another person, thing or\n"
    "occasion a relation of its own, one that says which: a second allergy is not\n"
    "a newer value for the first. When the conversation gives two values for the\n"
    "same thing, give only the current one. Reply with a JSON object:\n"
    '{"facts": [{"subject": "...", "relation": "...", "value": "...", "turn": 0}]}.\n'
    'With nothing to list, reply {"facts": []}.'
)
PROMPTS = {1: FACT_SYSTEM_PROMPT, 2: REPLACING_SYSTEM_PROMPT, 3: KEYED_SYSTEM_PROMPT}


def prompt_id(prompt: str) -> str:
    """What names a prompt in a reply file: a changed prompt never reads another's replies."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]


# -- extraction --------------------------------------------------------------

def sessions_of(x: dict) -> tuple[list[list[MemoryRecord]], set[str]]:
    """The history's sessions in replay order (ADR 0004), and its evidence turns' ids."""
    records, _, evidence = build_records(x, "clock")
    sessions: dict[str, list[MemoryRecord]] = {}
    for record in records:
        sessions.setdefault(record.session_id, []).append(record)
    return list(sessions.values()), evidence


def extraction_message(turns: list[MemoryRecord], shown: dict[int, dict] | None = None,
                       numbered: bool = False) -> str:
    """The session as quoted transcript, as the consolidator gets it (ADR 0015), each turn numbered.

    After round one the facts no later fact has replaced come first; in round
    two each under its number, for the model to name.
    """
    transcript = "Conversation:\n" + "\n\n".join(f"[{n}] {r.role}: {r.content}" for n, r in enumerate(turns))
    if shown is None:
        return transcript
    facts = "\n".join((f"{n}. " if numbered else "") + f"{f['subject']} / {f['relation']} = {f['value']}"
                      for n, f in shown.items())
    return f"Facts so far:\n{facts or '(none)'}\n\n{transcript}"


def key_of(fact: dict) -> tuple[str, str]:
    """What round three replaces on: the subject and the relation, case and spacing aside."""
    return norm(fact["subject"]), norm(fact["relation"])


def facts_of(reply: dict | None, turns: int, shown: dict[int, dict] | None = None) -> tuple[list[dict], int, int]:
    """The well-formed facts of a reply; the entries dropped as malformed; and, in round
    two, the replaces-numbers dropped because no fact was shown under them."""
    kept, dropped, strays = [], 0, 0
    for entry in (reply or {}).get("facts", []):
        fact = entry if isinstance(entry, dict) else {}
        value = fact.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)  # a count sent as a number is still a value
        texts = (fact.get("subject"), fact.get("relation"), value)
        turn = fact.get("turn")
        if not (all(isinstance(t, str) and t.strip() for t in texts)
                and isinstance(turn, int) and not isinstance(turn, bool) and 0 <= turn < turns):
            dropped += 1
            continue
        subject, relation, value = (t.strip() for t in texts)
        kept.append({"subject": subject, "relation": relation, "value": value, "turn": turn})
        if shown is not None:
            named = fact.get("replaces") or []
            named = named if isinstance(named, list) else [named]
            good = sorted({n for n in named if isinstance(n, int) and not isinstance(n, bool) and n in shown})
            strays += len(named) - len(good)
            kept[-1]["replaces"] = good
    return kept, dropped, strays


def session_row(x: dict, turns: list[MemoryRecord], evidence: set[str], inner: object,
                counter: TokenCounter, round_: int = 1, shown: dict[int, dict] | None = None) -> dict:
    """One session's call, with its own call log. After round one *shown* is the facts so far."""
    prompt = PROMPTS[round_]
    log: list[LLMCall] = []
    client = RecordingLLMClient(inner, label="extract", counter=counter, log=log, model=CONSOLIDATOR_MODEL)
    messages = [{"role": "user", "content": extraction_message(turns, shown, numbered=round_ == 2)}]
    reply = None
    for _ in range(ATTEMPTS):
        answer = client.chat_json(prompt, messages)
        if answer is not None and isinstance(answer.get("facts"), list):
            reply = answer
            break
    # Only round two's reply names what it replaces; round three's facts get theirs from the code.
    facts, dropped, strays = facts_of(reply, len(turns), shown if round_ == 2 else None)
    if round_ == 3:
        for fact in facts:
            fact["replaces"] = sorted(n for n, old in shown.items() if key_of(old) == key_of(fact))
    row = {
        "question_id": x["question_id"],
        "session_id": turns[0].session_id,
        "at": turns[0].at.isoformat(),
        "turns": len(turns),
        "evidence_turns": [n for n, r in enumerate(turns) if r.id in evidence],
        "model": CONSOLIDATOR_MODEL,
        "prompt": prompt_id(prompt),
        "failed": reply is None,
        "facts": facts,
        "dropped": dropped,
        "calls": [asdict(c) for c in log],
    }
    if shown is not None:
        row.update(round=round_, facts_shown=len(shown), stray_numbers=strays)
    return row


def history_rows(x: dict, sessions: list[list[MemoryRecord]], evidence: set[str], inner: object,
                 counter: TokenCounter, path: Path, round_: int, workers: int) -> list[dict]:
    """A model call per session, each row saved as it comes.

    Round one asks *workers* sessions at once. The other two ask them in
    order: a call is given the facts the earlier sessions left, a fact gets the
    next number, and the facts it replaces leave the list. Two facts of one
    session never replace each other.
    """
    current: dict[int, dict] = {}
    numbers = itertools.count(1)

    def in_order():
        for turns in sessions:
            row = session_row(x, turns, evidence, inner, counter, round_, dict(current))
            for fact in row["facts"]:
                fact["number"] = next(numbers)
                for old in fact["replaces"]:
                    current.pop(old, None)
                current[fact["number"]] = fact
            yield row

    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with path.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        made = in_order() if round_ > 1 else pool.map(lambda s: session_row(x, s, evidence, inner, counter), sessions)
        for row in made:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            print(f"  {x['question_id']} {len(rows):>2}/{len(sessions)} {row['session_id']:<24} "
                  + ("no facts list" if row["failed"] else f"{len(row['facts'])} facts"), flush=True)
    return rows


def saved_rows(path: Path, sessions: list[list[MemoryRecord]]) -> list[dict] | None:
    """The rows of an earlier run, if the file holds exactly this history's sessions."""
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return rows if [r["session_id"] for r in rows] == [s[0].session_id for s in sessions] else None


def replacements(rows: list[dict]) -> dict[int, tuple[dict, dict]]:
    """After round one: each replaced fact's number, with the row and the fact that replaced it."""
    found: dict[int, tuple[dict, dict]] = {}
    for row in rows:
        for fact in row["facts"]:
            for old in fact.get("replaces", []):
                found.setdefault(old, (row, fact))
    return found


# -- the graph ---------------------------------------------------------------

def norm(name: str) -> str:
    """How two names are compared here: case and spacing aside, nothing else."""
    return " ".join(name.casefold().split())


def edge_type(relation: str) -> str:
    """A relationship type from a name the model chose: only A-Z, 0-9 and _ survive."""
    name = re.sub(r"[^A-Z0-9]+", "_", relation.upper()).strip("_")
    return name if name and not name[0].isdigit() else f"R_{name}"


def connect():
    """The Neo4j the graph is drawn in, or SystemExit saying what is missing."""
    try:
        from neo4j import GraphDatabase  # only drawing needs the driver; it is no dependency before the ADR
    except ImportError:
        raise SystemExit("the Neo4j driver is not installed: .venv/bin/pip install neo4j, or use --no-graph")
    password = env_value("LIFE_AGENT_NEO4J_PASSWORD")
    if not password:
        raise SystemExit("set LIFE_AGENT_NEO4J_PASSWORD in .env, or use --no-graph")
    driver = GraphDatabase.driver(env_value("LIFE_AGENT_NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(env_value("LIFE_AGENT_NEO4J_USER", "neo4j"), password))
    try:
        driver.verify_connectivity()
    except Exception as e:  # noqa: BLE001 — whatever it is, nothing can be drawn
        raise SystemExit(f"Neo4j does not answer ({type(e).__name__}: {e}). "
                         "Is the container running? --no-graph goes without it.")
    return driver


def draw(driver, history: str, rows: list[dict]) -> tuple[int, int]:
    """Replace *history*'s graph with the facts in *rows*, in one transaction.

    Returns the fact edges drawn and the REPLACED_BY edges. A replaced fact's
    edge stays, with replaced_at and replaced_by; the REPLACED_BY edge from its
    value to the newer one says nothing the two fact edges do not, and is there
    to be seen.
    """
    replaced = replacements(rows)

    def rebuild(tx) -> tuple[int, int]:
        tx.run("MATCH (n:Entity {history: $history}) DETACH DELETE n", history=history)
        edges = arrows = 0
        value_of: dict[int, str] = {}
        for row in rows:
            for fact in row["facts"]:
                number = fact.get("number")
                by_row, by = replaced.get(number, (None, None))
                tx.run(
                    "MERGE (s:Entity {history: $history, key: $subject_key}) ON CREATE SET s.name = $subject "
                    "MERGE (o:Entity {history: $history, key: $value_key}) ON CREATE SET o.name = $value "
                    # Cypher takes no parameter for a type; edge_type leaves nothing that could end the backticks.
                    f"CREATE (s)-[:`{edge_type(fact['relation'])}` {{history: $history, prompt: $prompt, "
                    "relation: $relation, value: $value, session_id: $session_id, turn: $turn, "
                    "record_id: $record_id, at: $at, evidence_session: $evidence_session, "
                    "evidence_turn: $evidence_turn, number: $number, replaced_at: $replaced_at, "
                    "replaced_by: $replaced_by}]->(o)",
                    history=history, prompt=row.get("prompt"), subject=fact["subject"],
                    subject_key=norm(fact["subject"]), value=fact["value"], value_key=norm(fact["value"]),
                    relation=fact["relation"], session_id=row["session_id"], turn=fact["turn"],
                    record_id=f"{row['session_id']}:{fact['turn']}", at=datetime.fromisoformat(row["at"]),
                    evidence_session=bool(row["evidence_turns"]), evidence_turn=fact["turn"] in row["evidence_turns"],
                    # None leaves the property unset: a round-one fact has no number, a current fact no replaced_at.
                    number=number, replaced_at=datetime.fromisoformat(by_row["at"]) if by_row else None,
                    replaced_by=by["number"] if by else None,
                )
                edges += 1
                if number is not None:
                    value_of[number] = norm(fact["value"])
        for old, (by_row, by) in replaced.items():
            if value_of[old] != value_of[by["number"]]:
                tx.run(
                    "MATCH (a:Entity {history: $history, key: $old_key}), (b:Entity {history: $history, key: $new_key}) "
                    "CREATE (a)-[:REPLACED_BY {history: $history, at: $at, old: $old, new: $new}]->(b)",
                    history=history, old_key=value_of[old], new_key=value_of[by["number"]],
                    at=datetime.fromisoformat(by_row["at"]), old=old, new=by["number"],
                )
                arrows += 1
        return edges, arrows

    with driver.session() as session:
        return session.execute_write(rebuild)


# -- what to read ------------------------------------------------------------

def fact_line(row: dict, fact: dict, replaced: dict[int, tuple[dict, dict]] | None = None) -> str:
    mark = "*" if fact["turn"] in row["evidence_turns"] else " "
    number = f"#{fact['number']:<4}" if "number" in fact else ""
    line = (f"    {mark} {number}{row['at'][:10]}  {row['session_id']}:{fact['turn']:<3} "
            f"{fact['subject']} / {fact['relation']} = {fact['value']}")
    if fact.get("replaces"):
        line += "  [replaces " + ", ".join(f"#{n}" for n in fact["replaces"]) + "]"
    if replaced and fact.get("number") in replaced:
        by_row, by = replaced[fact["number"]]
        line += f"  [replaced {by_row['at'][:10]} by #{by['number']}]"
    return line


def report(rows: list[dict], every_fact: bool) -> None:
    facts = [(row, fact) for row in rows for fact in row["facts"]]
    counts = [len(row["facts"]) for row in rows]
    calls = [c for row in rows for c in row["calls"]]
    by_key: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
    for row, fact in facts:
        by_key.setdefault(key_of(fact), []).append((row, fact))
    repeated = {k: v for k, v in by_key.items() if len({row["session_id"] for row, _ in v}) > 1}
    changed = sum(len({norm(fact["value"]) for _, fact in v}) > 1 for v in repeated.values())
    replacing = "facts_shown" in rows[0]
    replaced = replacements(rows)
    numbered = {fact["number"]: (row, fact) for row, fact in facts} if replacing else {}

    lines = [
        ("sessions", f"{len(rows)}, {sum(bool(r['evidence_turns']) for r in rows)} with evidence"),
        ("sessions without a facts list after every attempt", f"{sum(r['failed'] for r in rows)}"),
        ("facts", f"{len(facts)}; per session mean {statistics.fmean(counts):.1f}, median "
                  f"{statistics.median(counts):g}, most {max(counts)}; sessions with none {counts.count(0)}"),
        ("entries dropped as malformed", f"{sum(r['dropped'] for r in rows)}"),
        ("(subject, relation) pairs", f"{len(by_key)} distinct; {len(repeated)} in more than one session, "
                                      f"{changed} of them with more than one value"),
    ]
    if replacing:
        same = sum(norm(numbered[old][1]["value"]) == norm(by["value"]) for old, (_, by) in replaced.items())
        shown = [r["facts_shown"] for r in rows]
        lines += [
            ("facts replaced", f"{len(replaced)}, {same} of them by the same value; "
                               f"{len(facts) - len(replaced)} current at the end"),
            ("replaces-numbers naming no fact shown (round two)", f"{sum(r['stray_numbers'] for r in rows)}"),
            ("facts shown to a call, mean / most", f"{statistics.fmean(shown):.0f} / {max(shown)}"),
        ]
    lines.append(("calls", f"{len(calls)}, {sum(c['failed'] for c in calls)} failed; "
                           f"{sum(c['input_tokens'] for c in calls):,} tokens in, "
                           f"{sum(c['output_tokens'] for c in calls):,} out; ${cost_of(calls):.4f}"))
    for label, value in lines:
        print(f"  {label:52s} {value}")

    if replacing:
        print("\n  replaced facts, in the order they were written (* = from an evidence turn)")
        for old in sorted(replaced):
            by_row, by = replaced[old]
            print(fact_line(*numbered[old]))
            print("   ->" + fact_line(by_row, by)[3:])
    print("\n  pairs in more than one session, oldest first (* = from an evidence turn)")
    for (subject, relation), found in repeated.items():
        print(f"  {subject} / {relation}")
        for row, fact in found:
            print(fact_line(row, fact, replaced))
    print("\n  every fact of the evidence sessions" if not every_fact else "\n  every fact")
    for row in rows:
        if every_fact or row["evidence_turns"]:
            print(f"  {row['at'][:10]}  {row['session_id']}, {row['turns']} turns"
                  + (", evidence in turn " + ", ".join(map(str, row["evidence_turns"])) if row["evidence_turns"] else "")
                  + (", no facts list" if row["failed"] else ""))
            for fact in row["facts"]:
                print(fact_line(row, fact, replaced))


# -- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("histories", nargs="+", help="question ids, among those no run measures")
    ap.add_argument("--round", type=int, choices=sorted(PROMPTS), default=1, dest="round_",
                    help="1: nothing replaced; 2: the model names what a fact replaces; 3: replaced on the same subject and relation")
    ap.add_argument("--dry-run", action="store_true", help="no model call, no database: the sessions and what they cost to send")
    ap.add_argument("--no-graph", action="store_true", help="extract and report; Neo4j is not touched")
    ap.add_argument("--again", action="store_true", help="ask the model again where replies are saved")
    ap.add_argument("--facts", action="store_true", help="print every fact, not only the evidence sessions'")
    ap.add_argument("--workers", type=int, default=4, help="calls at once: sessions in round one, histories after it")
    args = ap.parse_args(argv)
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    unmeasured = [q for t in TYPES for q in doc[t][MEASURED_PER_TYPE:]]
    wrong = [q for q in args.histories if q not in unmeasured]
    if wrong:
        raise SystemExit(f"{', '.join(wrong)}: not among the histories no run measures ({', '.join(unmeasured)})")
    by_id = {x["question_id"]: x for x in load_pinned()}
    counter = TiktokenCounter()
    prompt = PROMPTS[args.round_]

    if args.dry_run:
        for qid in args.histories:
            sessions, evidence = sessions_of(by_id[qid])
            tokens = sum(counter.count(prompt) + counter.count(extraction_message(s)) for s in sessions)
            print(f"{qid}: {len(sessions)} sessions, {sum(any(r.id in evidence for r in s) for s in sessions)} "
                  f"with evidence; {tokens:,} tokens in, ${usd(tokens, 0, CONSOLIDATOR_MODEL):.4f} before any output"
                  + (" and before the facts so far" if args.round_ > 1 else "") + " (dry run)")
        return 0

    # Before any model call: a database that is not there should not cost a history.
    driver = None if args.no_graph else connect()
    histories = []
    for qid in args.histories:
        sessions, evidence = sessions_of(by_id[qid])
        path = SPIKE / f"{qid}-{prompt_id(prompt)}.jsonl"
        histories.append((by_id[qid], sessions, evidence, path, None if args.again else saved_rows(path, sessions)))
    inner = real_client(CONSOLIDATOR_MODEL) if any(saved is None for *_, saved in histories) else None

    def rows_of(history: tuple) -> list[dict]:
        x, sessions, evidence, path, saved = history
        if saved is not None:
            return saved
        return history_rows(x, sessions, evidence, inner, counter, path, args.round_,
                            1 if args.round_ > 1 else args.workers)

    # After round one the calls come in order within a history, so there the histories run side by side.
    with ThreadPoolExecutor(max_workers=args.workers if args.round_ > 1 else 1) as pool:
        made = list(pool.map(rows_of, histories))

    for (x, _, _, path, _), rows in zip(histories, made):
        qid = x["question_id"]
        print(f"\n{qid}: {x['question']} (gold: {x['answer']}; asked {x['question_date']})")
        print(f"  replies: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}, "
              f"prompt {prompt_id(prompt)}, {CONSOLIDATOR_MODEL}\n")
        report(rows, args.facts)
        if driver is not None:
            edges, arrows = draw(driver, qid, rows)
            print(f"\n  drawn: {edges} facts" + (f", {arrows} REPLACED_BY" if args.round_ > 1 else "")
                  + ". In http://localhost:7474:\n"
                  f"    MATCH (a:Entity {{history: '{qid}'}})-[r]->(b) RETURN a, r, b\n"
                  f"    MATCH (a:Entity {{history: '{qid}'}})-[r {{evidence_session: true}}]->(b) RETURN a, r, b")
            if args.round_ > 1:
                print(f"    MATCH (s:Entity {{history: '{qid}'}})-[old]->(o)-[by:REPLACED_BY]->(n)<-[new]-(s2) "
                      "WHERE old.replaced_by = new.number RETURN s, old, o, by, n, new, s2")
    if driver is not None:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
