"""Tests for the store behind FactGraphMemory.

:class:`TestFactStoreContract` runs against every implementation of the store,
so that the one the tests use and the one a measured run uses are held to the
same rules.  The store in the process always runs.  The one in Neo4j runs only
when ``LIFE_AGENT_NEO4J_PASSWORD`` is set in the real environment, since the
local ``.env`` is neutralised for tests and the suite must pass offline:

    LIFE_AGENT_NEO4J_PASSWORD=... pytest tests/test_fact_store.py

It writes under the tag ``pytest`` and clears it before and after.
"""

import os
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from life_agent.agent.fact_store import (
    Fact,
    InProcessFactStore,
    Neo4jFactStore,
    edge_type,
    neo4j_driver,
    normalise,
)

MAY = datetime(2026, 5, 1, 9, 0, 0)
JUNE = datetime(2026, 6, 1, 9, 0, 0)
DAY = timedelta(days=1)


def fact(session_id: str, n: int, relation: str, value: str, at: datetime, subject="user") -> Fact:
    return Fact(
        id=f"fact:{session_id}:{n}",
        subject=subject,
        relation=relation,
        value=value,
        session_id=session_id,
        turn=0,
        turn_id=f"{session_id}:0",
        at=at,
    )


@pytest.fixture(params=["process", "neo4j"])
def store(request):
    if request.param == "process":
        yield InProcessFactStore()
        return
    password = os.environ.get("LIFE_AGENT_NEO4J_PASSWORD")
    if not password:
        pytest.skip("LIFE_AGENT_NEO4J_PASSWORD is not set in the environment; the suite runs offline")
    driver = neo4j_driver(
        os.environ.get("LIFE_AGENT_NEO4J_URI", "bolt://localhost:7687"),
        os.environ.get("LIFE_AGENT_NEO4J_USER", "neo4j"),
        password,
    )
    store = Neo4jFactStore(driver, "pytest")
    store.clear()
    yield store
    store.clear()
    driver.close()


class TestFact:
    def test_the_line_is_what_is_shown(self):
        assert fact("s1", 0, "car", "Honda", MAY).line == "user / car = Honda"

    def test_a_fact_holds_from_the_instant_it_was_stored(self):
        honda = fact("s1", 0, "car", "Honda", MAY)

        assert not honda.holds(MAY - DAY)
        assert honda.holds(MAY)
        assert honda.holds(JUNE)

    def test_a_replaced_fact_holds_until_the_instant_it_was_replaced(self):
        honda = replace(fact("s1", 0, "car", "Honda", MAY), replaced_by="fact:s2:0", replaced_at=JUNE)

        assert honda.holds(JUNE - DAY)
        assert not honda.holds(JUNE)


class TestNames:
    def test_case_and_runs_of_whitespace_are_set_aside(self):
        assert normalise("  Wake_Up   Time ") == normalise("wake_up time")

    def test_nothing_else_is_normalised(self):
        assert normalise("wake_up_time") != normalise("wake up time")
        assert normalise("cars") != normalise("car")

    def test_an_edge_type_keeps_only_letters_digits_and_underscores(self):
        assert edge_type("blood_type") == "BLOOD_TYPE"
        assert edge_type("favourite café") == "FAVOURITE_CAF"
        assert edge_type("x`]->() DETACH DELETE n //") == "X_DETACH_DELETE_N"

    def test_an_edge_type_never_starts_with_a_digit_and_is_never_empty(self):
        assert edge_type("5k_time") == "R_5K_TIME"
        assert edge_type("!!!") == "R_"


class TestFactStoreContract:
    def test_an_empty_store_holds_nothing(self, store):
        assert store.facts() == []
        assert store.held(JUNE) == []

    def test_facts_come_back_as_they_were_stored_in_the_order_stored(self, store):
        first = [fact("s1", 0, "car", "Honda", MAY), fact("s1", 1, "dog_name", "Miso", MAY)]
        second = [fact("s2", 0, "city", "Lund", JUNE)]

        store.add(first, {})
        store.add(second, {})

        assert store.facts() == first + second

    def test_the_text_of_a_fact_survives_unchanged(self, store):
        # The nodes are named case aside, so these two share theirs; each
        # fact still reads as it was written.
        facts = [
            fact("s1", 0, "Home Town", "Malmö", MAY, subject="User"),
            fact("s1", 1, "birth_place", "MALMÖ", MAY, subject="user"),
        ]

        store.add(facts, {})

        assert [f.line for f in store.facts()] == ["User / Home Town = Malmö", "user / birth_place = MALMÖ"]

    def test_a_replaced_fact_is_marked_and_kept(self, store):
        honda = fact("s1", 0, "car", "Honda", MAY)
        tesla = fact("s2", 0, "car", "Tesla", JUNE)
        store.add([honda], {})

        store.add([tesla], {honda.id: tesla.id})

        old, new = store.facts()
        assert (old.id, old.value) == (honda.id, "Honda")
        assert (old.replaced_by, old.replaced_at) == (tesla.id, JUNE)
        assert (new.replaced_by, new.replaced_at) == (None, None)

    def test_what_held_before_a_replacement_can_still_be_asked_for(self, store):
        honda = fact("s1", 0, "car", "Honda", MAY)
        tesla = fact("s2", 0, "car", "Tesla", JUNE)
        store.add([honda], {})
        store.add([tesla], {honda.id: tesla.id})

        assert [f.value for f in store.held(MAY - DAY)] == []
        assert [f.value for f in store.held(MAY)] == ["Honda"]
        assert [f.value for f in store.held(JUNE - DAY)] == ["Honda"]
        assert [f.value for f in store.held(JUNE)] == ["Tesla"]

    def test_a_fact_that_was_not_replaced_stays_among_those_that_hold(self, store):
        store.add([fact("s1", 0, "car", "Honda", MAY), fact("s1", 1, "dog_name", "Miso", MAY)], {})
        store.add([fact("s2", 0, "car", "Tesla", JUNE)], {"fact:s1:0": "fact:s2:0"})

        assert [f.line for f in store.held(JUNE)] == ["user / dog_name = Miso", "user / car = Tesla"]

    def test_clear_drops_everything(self, store):
        store.add([fact("s1", 0, "car", "Honda", MAY)], {})

        store.clear()

        assert store.facts() == []
        assert store.held(JUNE) == []
