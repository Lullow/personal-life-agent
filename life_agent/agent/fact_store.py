"""Where :class:`~life_agent.agent.memory.FactGraphMemory` keeps its facts.

A fact is a timestamped triple: a subject, a relation and a value, with the
session and the turn it came from.  The strategy decides what is stored and
what a new fact replaces; the store only keeps what it is handed, and answers
what held at a point in time.  It is memory's own store and has no path to the
domain tables: nothing here goes through ``db/repositories.py``.

Two implementations stand behind one Protocol
(``docs/adr/0018-fact-graph-memory-replaces-on-the-name.md``):

* :class:`InProcessFactStore` keeps the facts in a list.  The tests and the
  evaluation's dry run use it, and need neither Docker nor a network.
* :class:`Neo4jFactStore` keeps each fact as an edge in a graph database.  A
  measured run uses it.  The driver is the optional extra ``graph``, and it is
  imported only when a driver is asked for, so the app and the tests never
  load it.

A replaced fact is never deleted in either: it is marked with the fact that
replaced it and with that fact's time, so what held at an earlier time can
still be asked for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence


class FactStoreError(RuntimeError):
    """A read from the store or a write to it failed: the machine's failure, not the model's."""


def normalise(name: str) -> str:
    """How two names are compared (ADR 0018): case and runs of whitespace aside, nothing else."""
    return " ".join(name.casefold().split())


@dataclass(frozen=True)
class Fact:
    """One fact, as it is stored.

    ``at`` is the strategy's clock when the extraction ran, never the time of
    the turn.  ``turn`` is the number the model named among the turns its call
    read, and ``turn_id`` that turn's record id; they are kept for ranking and
    for display.  ``replaced_by`` is the id of the fact that replaced this one
    and ``replaced_at`` that fact's ``at``; both are None while the fact holds.
    """

    id: str
    subject: str
    relation: str
    value: str
    session_id: str
    turn: int
    turn_id: str
    at: datetime
    replaced_by: str | None = None
    replaced_at: datetime | None = None

    @property
    def line(self) -> str:
        """The fact as it is shown, to the extraction call and to the answering model."""
        return f"{self.subject} / {self.relation} = {self.value}"

    def holds(self, at: datetime) -> bool:
        """Whether the fact holds at *at*: stored by then, and not replaced by then."""
        return self.at <= at and (self.replaced_at is None or self.replaced_at > at)


class FactStore(Protocol):
    """What :class:`~life_agent.agent.memory.FactGraphMemory` needs from its store."""

    def clear(self) -> None:
        """Drop every fact this store holds."""
        ...

    def add(self, facts: Sequence[Fact], replaced: Mapping[str, str]) -> None:
        """Store one session's *facts*, in order, and mark what they replace.

        *replaced* maps the id of a fact already stored to the id of the fact
        in *facts* that replaces it.  All of it happens or none of it does.
        """
        ...

    def held(self, at: datetime) -> list[Fact]:
        """The facts that hold at *at*, in the order they were stored."""
        ...

    def facts(self) -> list[Fact]:
        """Every fact, replaced ones included, in the order they were stored."""
        ...


class InProcessFactStore:
    """The facts in a list in the process.  Nothing outlives it."""

    def __init__(self) -> None:
        self._facts: list[Fact] = []

    def clear(self) -> None:
        self._facts = []

    def add(self, facts: Sequence[Fact], replaced: Mapping[str, str]) -> None:
        by = {fact.id: fact for fact in facts}
        marked = [
            replace(old, replaced_by=replaced[old.id], replaced_at=by[replaced[old.id]].at)
            if old.id in replaced
            else old
            for old in self._facts
        ]
        self._facts = marked + list(facts)

    def held(self, at: datetime) -> list[Fact]:
        return [fact for fact in self._facts if fact.holds(at)]

    def facts(self) -> list[Fact]:
        return list(self._facts)


def edge_type(relation: str) -> str:
    """A relationship type from a name the model chose: only A-Z, 0-9 and _ survive."""
    name = re.sub(r"[^A-Z0-9]+", "_", relation.upper()).strip("_")
    return name if name and not name[0].isdigit() else f"R_{name}"


def neo4j_driver(uri: str, user: str, password: str) -> Any:
    """A driver for the Neo4j at *uri*, checked to answer, or FactStoreError saying what is missing."""
    try:
        from neo4j import GraphDatabase  # the optional extra "graph"; nothing else imports it
    except ImportError as e:
        raise FactStoreError("the Neo4j driver is not installed: pip install -e '.[graph]'") from e
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        # Every read and write names a tag; without the index each would scan
        # the nodes of every other tag as well.
        driver.execute_query("CREATE INDEX entity_tag IF NOT EXISTS FOR (n:Entity) ON (n.tag)")
    except Exception as e:  # noqa: BLE001 — whatever it is, the store cannot be used
        driver.close()
        raise FactStoreError(f"Neo4j does not answer at {uri} ({type(e).__name__}: {e})") from e
    return driver


class Neo4jFactStore:
    """The facts as edges in Neo4j, under one *tag*.

    A fact is an edge from a node for its subject to a node for its value,
    typed by the relation and carrying the rest of the fact.  A node is named
    by its text, case and spacing aside, so a subject and a value of one name
    share a node.  Everything this store writes carries its tag and everything
    it reads is matched on it, so two stores with different tags never see
    each other's facts.

    A replaced fact's edge stays, with ``replaced_by`` and ``replaced_at``.
    The ``REPLACED_BY`` edge from its value to the newer one says nothing the
    two fact edges do not, and is there to be seen; it carries no ``id``,
    which is what tells it from a fact.
    """

    def __init__(self, driver: Any, tag: str) -> None:
        self._driver = driver
        self.tag = tag

    def clear(self) -> None:
        self._write(lambda tx: tx.run("MATCH (n:Entity {tag: $tag}) DETACH DELETE n", tag=self.tag).consume())

    def add(self, facts: Sequence[Fact], replaced: Mapping[str, str]) -> None:
        if not facts:
            return
        by = {fact.id: fact for fact in facts}

        def work(tx: Any) -> None:
            stored = tx.run(
                "MATCH (:Entity {tag: $tag})-[r]->(:Entity) WHERE r.id IS NOT NULL RETURN count(r) AS n",
                tag=self.tag,
            ).single()["n"]
            for seq, fact in enumerate(facts, start=stored):
                tx.run(
                    "MERGE (s:Entity {tag: $tag, key: $subject_key}) ON CREATE SET s.name = $subject "
                    "MERGE (o:Entity {tag: $tag, key: $value_key}) ON CREATE SET o.name = $value "
                    # Cypher takes no parameter for a type; edge_type leaves nothing that could end the backticks.
                    f"CREATE (s)-[:`{edge_type(fact.relation)}` {{tag: $tag, id: $id, seq: $seq, "
                    "subject: $subject, relation: $relation, value: $value, session_id: $session_id, "
                    "turn: $turn, turn_id: $turn_id, at: $at}]->(o)",
                    tag=self.tag, id=fact.id, seq=seq, subject=fact.subject, subject_key=normalise(fact.subject),
                    relation=fact.relation, value=fact.value, value_key=normalise(fact.value),
                    session_id=fact.session_id, turn=fact.turn, turn_id=fact.turn_id, at=fact.at,
                ).consume()
            for old, new in replaced.items():
                marked = tx.run(
                    "MATCH (:Entity {tag: $tag})-[r {id: $old}]->(a:Entity) "
                    "SET r.replaced_by = $new, r.replaced_at = $at "
                    "WITH a MATCH (b:Entity {tag: $tag, key: $new_key}) "
                    "CREATE (a)-[:REPLACED_BY {tag: $tag, at: $at, old: $old, new: $new}]->(b) "
                    "RETURN count(*) AS n",
                    tag=self.tag, old=old, new=new, at=by[new].at, new_key=normalise(by[new].value),
                ).single()["n"]
                if marked != 1:
                    raise FactStoreError(f"{old!r} is stored {marked} times under {self.tag!r}; it should be once")

        self._write(work)

    def held(self, at: datetime) -> list[Fact]:
        return self._read("AND r.at <= $at AND (r.replaced_at IS NULL OR r.replaced_at > $at)", at=at)

    def facts(self) -> list[Fact]:
        return self._read("")

    def _read(self, condition: str, **parameters: Any) -> list[Fact]:
        query = (
            "MATCH (:Entity {tag: $tag})-[r]->(:Entity) WHERE r.id IS NOT NULL "
            f"{condition} RETURN properties(r) AS fact ORDER BY r.seq"
        )
        try:
            with self._driver.session() as session:
                rows = session.execute_read(
                    lambda tx: [record["fact"] for record in tx.run(query, tag=self.tag, **parameters)]
                )
        except Exception as e:  # noqa: BLE001 — ADR 0018: any failure of the store is raised as one kind
            raise FactStoreError(f"reading {self.tag!r} from Neo4j failed ({type(e).__name__}: {e})") from e
        return [
            Fact(
                id=row["id"], subject=row["subject"], relation=row["relation"], value=row["value"],
                session_id=row["session_id"], turn=row["turn"], turn_id=row["turn_id"],
                at=row["at"].to_native(), replaced_by=row.get("replaced_by"),
                replaced_at=row["replaced_at"].to_native() if row.get("replaced_at") is not None else None,
            )
            for row in rows
        ]

    def _write(self, work: Any) -> None:
        try:
            with self._driver.session() as session:
                session.execute_write(work)
        except FactStoreError:
            raise
        except Exception as e:  # noqa: BLE001 — ADR 0018: any failure of the store is raised as one kind
            raise FactStoreError(f"writing {self.tag!r} to Neo4j failed ({type(e).__name__}: {e})") from e
