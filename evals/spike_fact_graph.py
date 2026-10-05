"""A probe, not a measurement: the facts of one history, drawn as a graph in Neo4j.

Before an ADR fixes how a fact graph is built, this looks at what an extraction
gives. Each session of a history goes to the consolidator's model once, as
quoted transcript, and comes back as (subject, relation, value) triples; each
triple is drawn as an edge that carries its session, its turn and the session's
time. No question is answered, nothing is graded, and no figure printed here is
a result. Nothing is replaced either: whether the model names one relation the
same way in two sessions is what a replacement rule would rest on, and that is
what this is here to show.

It only takes the histories no run measures: the questions ADR 0005 admits
beyond the first 61 of a type (ADR 0010). The prompt below is shaped on what
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
"""

from __future__ import annotations

import argparse
import hashlib
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
PROMPT_SHA256 = hashlib.sha256(FACT_SYSTEM_PROMPT.encode("utf-8")).hexdigest()


# -- extraction --------------------------------------------------------------

def sessions_of(x: dict) -> tuple[list[list[MemoryRecord]], set[str]]:
    """The history's sessions in replay order (ADR 0004), and its evidence turns' ids."""
    records, _, evidence = build_records(x, "clock")
    sessions: dict[str, list[MemoryRecord]] = {}
    for record in records:
        sessions.setdefault(record.session_id, []).append(record)
    return list(sessions.values()), evidence


def extraction_message(turns: list[MemoryRecord]) -> str:
    """The session as quoted transcript, as the consolidator gets it (ADR 0015), each turn numbered."""
    return "Conversation:\n" + "\n\n".join(f"[{n}] {r.role}: {r.content}" for n, r in enumerate(turns))


def facts_of(reply: dict | None, turns: int) -> tuple[list[dict], int]:
    """The well-formed facts of a reply, and how many entries were dropped as malformed."""
    kept, dropped = [], 0
    for entry in (reply or {}).get("facts", []):
        fact = entry if isinstance(entry, dict) else {}
        value = fact.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)  # a count sent as a number is still a value
        texts = (fact.get("subject"), fact.get("relation"), value)
        turn = fact.get("turn")
        if (all(isinstance(t, str) and t.strip() for t in texts)
                and isinstance(turn, int) and not isinstance(turn, bool) and 0 <= turn < turns):
            subject, relation, value = (t.strip() for t in texts)
            kept.append({"subject": subject, "relation": relation, "value": value, "turn": turn})
        else:
            dropped += 1
    return kept, dropped


def session_row(x: dict, turns: list[MemoryRecord], evidence: set[str], inner: object,
                counter: TokenCounter) -> dict:
    """One session's call, with its own call log, so sessions can be asked side by side."""
    log: list[LLMCall] = []
    client = RecordingLLMClient(inner, label="extract", counter=counter, log=log, model=CONSOLIDATOR_MODEL)
    messages = [{"role": "user", "content": extraction_message(turns)}]
    reply = None
    for _ in range(ATTEMPTS):
        answer = client.chat_json(FACT_SYSTEM_PROMPT, messages)
        if answer is not None and isinstance(answer.get("facts"), list):
            reply = answer
            break
    facts, dropped = facts_of(reply, len(turns))
    return {
        "question_id": x["question_id"],
        "session_id": turns[0].session_id,
        "at": turns[0].at.isoformat(),
        "turns": len(turns),
        "evidence_turns": [n for n, r in enumerate(turns) if r.id in evidence],
        "model": CONSOLIDATOR_MODEL,
        "prompt_sha256": PROMPT_SHA256,
        "failed": reply is None,
        "facts": facts,
        "dropped": dropped,
        "calls": [asdict(c) for c in log],
    }


def saved_rows(path: Path, sessions: list[list[MemoryRecord]]) -> list[dict] | None:
    """The rows of an earlier run, if the file holds exactly this history's sessions."""
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return rows if [r["session_id"] for r in rows] == [s[0].session_id for s in sessions] else None


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


def draw(driver, history: str, rows: list[dict]) -> int:
    """Replace *history*'s graph with the facts in *rows*, in one transaction; the edges drawn."""

    def rebuild(tx) -> int:
        tx.run("MATCH (n:Entity {history: $history}) DETACH DELETE n", history=history)
        edges = 0
        for row in rows:
            for fact in row["facts"]:
                tx.run(
                    "MERGE (s:Entity {history: $history, key: $subject_key}) ON CREATE SET s.name = $subject "
                    "MERGE (o:Entity {history: $history, key: $value_key}) ON CREATE SET o.name = $value "
                    # Cypher takes no parameter for a type; edge_type leaves nothing that could end the backticks.
                    f"CREATE (s)-[:`{edge_type(fact['relation'])}` {{history: $history, relation: $relation, "
                    "value: $value, session_id: $session_id, turn: $turn, record_id: $record_id, at: $at, "
                    "evidence_session: $evidence_session, evidence_turn: $evidence_turn}]->(o)",
                    history=history, subject=fact["subject"], subject_key=norm(fact["subject"]),
                    value=fact["value"], value_key=norm(fact["value"]), relation=fact["relation"],
                    session_id=row["session_id"], turn=fact["turn"],
                    record_id=f"{row['session_id']}:{fact['turn']}", at=datetime.fromisoformat(row["at"]),
                    evidence_session=bool(row["evidence_turns"]), evidence_turn=fact["turn"] in row["evidence_turns"],
                )
                edges += 1
        return edges

    with driver.session() as session:
        return session.execute_write(rebuild)


# -- what to read ------------------------------------------------------------

def fact_line(row: dict, fact: dict) -> str:
    mark = "*" if fact["turn"] in row["evidence_turns"] else " "
    return (f"    {mark} {row['at'][:10]}  {row['session_id']}:{fact['turn']:<3} "
            f"{fact['subject']} / {fact['relation']} = {fact['value']}")


def report(rows: list[dict], every_fact: bool) -> None:
    facts = [(row, fact) for row in rows for fact in row["facts"]]
    counts = [len(row["facts"]) for row in rows]
    calls = [c for row in rows for c in row["calls"]]
    by_key: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
    for row, fact in facts:
        by_key.setdefault((norm(fact["subject"]), norm(fact["relation"])), []).append((row, fact))
    repeated = {k: v for k, v in by_key.items() if len({row["session_id"] for row, _ in v}) > 1}
    changed = sum(len({norm(fact["value"]) for _, fact in v}) > 1 for v in repeated.values())

    lines = [
        ("sessions", f"{len(rows)}, {sum(bool(r['evidence_turns']) for r in rows)} with evidence"),
        ("sessions without a facts list after every attempt", f"{sum(r['failed'] for r in rows)}"),
        ("facts", f"{len(facts)}; per session mean {statistics.fmean(counts):.1f}, median "
                  f"{statistics.median(counts):g}, most {max(counts)}; sessions with none {counts.count(0)}"),
        ("entries dropped as malformed", f"{sum(r['dropped'] for r in rows)}"),
        ("(subject, relation) pairs", f"{len(by_key)} distinct; {len(repeated)} in more than one session, "
                                      f"{changed} of them with more than one value"),
        ("calls", f"{len(calls)}, {sum(c['failed'] for c in calls)} failed; "
                  f"{sum(c['input_tokens'] for c in calls):,} tokens in, "
                  f"{sum(c['output_tokens'] for c in calls):,} out; ${cost_of(calls):.4f}"),
    ]
    for label, value in lines:
        print(f"  {label:52s} {value}")

    print("\n  pairs in more than one session, oldest first (* = from an evidence turn)")
    for (subject, relation), found in repeated.items():
        print(f"  {subject} / {relation}")
        for row, fact in found:
            print(fact_line(row, fact))
    print("\n  every fact of the evidence sessions" if not every_fact else "\n  every fact")
    for row in rows:
        if every_fact or row["evidence_turns"]:
            print(f"  {row['at'][:10]}  {row['session_id']}, {row['turns']} turns"
                  + (", evidence in turn " + ", ".join(map(str, row["evidence_turns"])) if row["evidence_turns"] else "")
                  + (", no facts list" if row["failed"] else ""))
            for fact in row["facts"]:
                print(fact_line(row, fact))


# -- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("histories", nargs="+", help="question ids, among those no run measures")
    ap.add_argument("--dry-run", action="store_true", help="no model call, no database: the sessions and what they cost to send")
    ap.add_argument("--no-graph", action="store_true", help="extract and report; Neo4j is not touched")
    ap.add_argument("--again", action="store_true", help="ask the model again where replies are saved")
    ap.add_argument("--facts", action="store_true", help="print every fact, not only the evidence sessions'")
    ap.add_argument("--workers", type=int, default=4, help="sessions asked at once; the rows stay in replay order")
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
    # Before any model call: a database that is not there should not cost a history.
    driver = None if args.dry_run or args.no_graph else connect()
    inner = None

    for qid in args.histories:
        x = by_id[qid]
        sessions, evidence = sessions_of(x)
        print(f"\n{qid}: {x['question']} (gold: {x['answer']}; asked {x['question_date']})")
        if args.dry_run:
            tokens = sum(counter.count(FACT_SYSTEM_PROMPT) + counter.count(extraction_message(s)) for s in sessions)
            print(f"  {len(sessions)} sessions, {sum(any(r.id in evidence for r in s) for s in sessions)} with evidence; "
                  f"{tokens:,} tokens in, ${usd(tokens, 0, CONSOLIDATOR_MODEL):.4f} before any output (dry run)")
            continue

        path = SPIKE / f"{qid}-{PROMPT_SHA256[:8]}.jsonl"
        rows = None if args.again else saved_rows(path, sessions)
        if rows is None:
            inner = inner or real_client(CONSOLIDATOR_MODEL)
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = []
            with path.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as pool:
                for row in pool.map(lambda s: session_row(x, s, evidence, inner, counter), sessions):
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    rows.append(row)
                    print(f"  {len(rows):>2}/{len(sessions)} {row['session_id']:<24} "
                          + ("no facts list" if row["failed"] else f"{len(row['facts'])} facts"))
        print(f"  replies: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}, "
              f"prompt {PROMPT_SHA256[:8]}, {CONSOLIDATOR_MODEL}\n")
        report(rows, args.facts)

        if driver is not None:
            edges = draw(driver, qid, rows)
            print(f"\n  drawn: {edges} edges. In http://localhost:7474:\n"
                  f"    MATCH (a:Entity {{history: '{qid}'}})-[r]->(b) RETURN a, r, b\n"
                  f"    MATCH (a:Entity {{history: '{qid}'}})-[r {{evidence_session: true}}]->(b) RETURN a, r, b")
    if driver is not None:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
