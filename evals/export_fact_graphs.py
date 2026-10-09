"""Copy the facts a run of the fact graph left in Neo4j into a file next to its rows.

A run keeps its facts in Neo4j (ADR 0018), and a row keeps only the facts
message the answering model saw. The graphs live in a container on one
machine and the extraction cannot be repeated, since the model names its
facts differently from run to run. This writes every fact of every replay of
a run, replaced ones included, as JSON lines that can be committed and read
without a database. It calls no model and changes nothing in Neo4j.

    .venv/bin/python evals/export_fact_graphs.py evals/results/fact-graph-20261005-161632.jsonl

The facts go to <the rows' file name>-facts.jsonl in the same directory, in
the order of the rows, the clock-order replay before the list-order one, each
replay's facts in the order they were stored.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.longmemeval import graph_driver  # noqa: E402
from life_agent.agent.fact_store import Neo4jFactStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit(__doc__.split("\n\n")[0])
    path = Path(args[0])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    run = path.stem
    out = path.with_name(f"{run}-facts.jsonl")

    driver = graph_driver()
    found, _, _ = driver.execute_query(
        "MATCH (n:Entity) WHERE n.tag STARTS WITH $prefix RETURN DISTINCT n.tag AS tag", prefix=f"{run}:"
    )
    tags = {record["tag"] for record in found}
    lines: list[str] = []
    replays = facts_written = 0
    for row in rows:
        for order in ("clock", "list"):
            tag = f"{run}:{row['question_id']}:{order}"
            if tag not in tags:
                continue
            facts = Neo4jFactStore(driver, tag).facts()
            if order == "clock":
                # What the row counted when the question was asked is what the graph still holds.
                counted = (row["facts_stored"], row["facts_replaced"])
                held = (len(facts), sum(f.replaced_by is not None for f in facts))
                if tag != row["graph_tag"] or counted != held:
                    raise SystemExit(f"{tag}: the row counts {counted} facts stored and replaced, the graph holds {held}")
            for fact in facts:
                entry = asdict(fact)
                entry["at"] = fact.at.isoformat()
                entry["replaced_at"] = fact.replaced_at.isoformat() if fact.replaced_at else None
                lines.append(json.dumps({"tag": tag, "question_id": row["question_id"], "order": order, **entry},
                                        ensure_ascii=False))
            replays += 1
            facts_written += len(facts)
    driver.close()
    missing = [row["graph_tag"] for row in rows if row.get("graph_tag") and row["graph_tag"] not in tags]
    if missing:
        raise SystemExit(f"not in Neo4j any more: {', '.join(missing)}")
    if not lines:
        raise SystemExit(f"Neo4j holds no graph of the run {run}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{run}: {replays} replays, {facts_written} facts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
