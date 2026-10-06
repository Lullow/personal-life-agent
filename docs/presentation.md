# Presentation

The examination is a 30-minute presentation with screen sharing, on Friday
9 October 2026. This file holds its order, the three questions it walks
through, and what to fall back on when something meant to run live does not.
The slides are a page of their own, "Ett A4 till provet", kept outside the
repo.

It restates no figure. The numbers shown are those of
[results.md](results.md), which `evals/results_table.py --check` recomputes.

## The order

| | Part | Minutes | What is shown |
|---|---|---|---|
| | Title | ½ | What the project measures, and that three things run live: the agent, the check and Neo4j. |
| 1 | The problem, live | 3 | The agent forgets. Steps 1 to 5 of [demo.md](demo.md) against `data/demo.db`: a day planned in one sentence and saved, a question about tomorrow, the sentence about the running shoes, `/quit`, a new chat, the question about the shoes, and `python -m life_agent events` to show that the meeting is still there. |
| 2 | One sheet of paper | 3 | The comparison as an exam to which one sheet of notes may be brought: the history is the notebook and the budget is the sheet. The question, the two question types, and the three hypotheses as predictions to be filled in later. |
| 3 | Four ways to fill the sheet | 3 | The four strategies on one schematic history, then `ConversationMemory` in `life_agent/agent/memory.py`. One sentence on why the search is BM25 and not a vector index (ADR 0011). |
| 4 | How one question is measured | 3 | Replay, recall, answer, grade, record, and that a rule is recorded as an ADR before the strategy it applies to is measured. The memory's error set against the model's, on `1faac195`. |
| 5 | One question through four memories | 5 | `c8c3f81d` to scale and through all four strategies, then `4b24c848` and `3ba21379`. The three questions are below. |
| 6 | The result | 5½ | The predictions filled in from the table on 122 questions in [results.md](results.md), where each strategy's errors sit, and correct answers by distance. Then `evals/results_table.py --check` and `pytest`, live. |
| 7 | The fact graph | 4 | The chain for `c6853660` on the slide and then in Neo4j, what held before the edge was replaced, and the pilot's table in [results.md](results.md), called a pilot. |
| 8 | What it means | 2½ | What the result means for the agent, what it cannot say, and [where the project departs from its proposal](vg-project.md#where-the-project-departs-from-its-proposal). |
| 9 | Conclusion | ½ | One sentence, then questions. |

The minutes are a draft. They add up to 30 and leave none for questions, and
they are set at the two timed run-throughs on Thursday 8 October. If the
time runs short, part 7 is cut down to its table first and the two later
questions of part 5 after it; part 6 is never cut.

## The three questions

One for each hypothesis in [results.md](results.md). The slides show them in
part 5. The file that sets them side by side, with what reached the model, is
written by

    .venv/bin/python evals/write_question_comparison.py c8c3f81d 4b24c848 3ba21379

to `data/longmemeval/comparison-c8c3f81d-4b24c848-3ba21379.md`, and is read in
a Markdown preview. The script reads the committed rows and the pinned
dataset and calls no model.

| Question | Asked, and the answer | `RecentTurnsMemory` | `RetrievalMemory` | `ConsolidatingMemory` |
|---|---|---|---|---|
| `c8c3f81d` | "What brand are my favorite running shoes?" Nike | "I do not know." | Nike | Nike |
| `4b24c848` | "How many tops have I bought from H&M so far?" five | "I do not know." | three | five |
| `3ba21379` | "What type of vehicle model am I currently working on?" Ford F-150 pickup truck | "I do not know." | Ford F-150 pickup truck | "I do not know." |

- `c8c3f81d` is the first hypothesis: the baseline answers only where the
  evidence is still inside its window. It is the sentence about the shoes
  from part 1, as the dataset has it.
- `4b24c848` is the mechanism the second hypothesis names, and the one the
  third names. `RetrievalMemory` had the earlier and the later turn in its
  context and answered with the earlier value. The notes of
  `ConsolidatingMemory` hold the later value only.
- `3ba21379` is what the third hypothesis did not say. The consolidator read
  both evidence turns, and its notes name neither the Mustang of the earlier
  turn nor the F-150 of the later.

`c8c3f81d` is also one of the pilot's 20 questions, so part 5 shows the
fourth strategy's answer to it as well: Nike, drawn from facts that mention
the brand, none of which names the evidence turn. The other two questions
are not among the 20.

Part 4 uses a fourth question, `1faac195`, "Where does my sister Emily
live?", for an error that is the model's and not the memory's:
`RetrievalMemory` had the evidence turn in its context, and the answer was
"I do not know."

## The fact graph

Shown on the pilot's graph for `c6853660`, where "one cup in the morning" was
replaced by "two cups in the morning". Neo4j runs in the container
`life-agent-neo4j`, started again with `docker start life-agent-neo4j`, and
its browser is at http://localhost:7474.

The chain, with the replaced edge still there:

    MATCH (a:Entity {tag: 'fact-graph-20261005-161632:c6853660:clock'})-[r:COFFEE_INTAKE]->(b)
    OPTIONAL MATCH (b)-[by:REPLACED_BY]->(c)
    RETURN a, r, b, by, c

What held at a time. On 26 May it gives one cup, and with `2023-05-27` two:

    WITH localdatetime('2023-05-26T00:00') AS t
    MATCH (a:Entity {tag: 'fact-graph-20261005-161632:c6853660:clock'})-[r:COFFEE_INTAKE]->(b)
    WHERE r.at <= t AND (r.replaced_at IS NULL OR r.replaced_at > t)
    RETURN a, r, b

Both were run against the graph on 5 October. A time is the time the
extraction ran, so it moves once per session (ADR 0018). The proposal named
ground truth at every point in time: this shows the mechanism on one example
and measures nothing.

The question is also one of the pilot's four errors. It asks whether the
limit was increased or decreased; the rule rightly replaced the earlier
value, only the newer one was shown, and the model answered "I do not know."
The graph still holds both.

## What to fall back on

| Part | Needs | If it is not there |
|---|---|---|
| 1 | the network and the model | `presentation/agent-demo-steps-1-to-5.png`, taken on 4 October. It is older than the commit that made `[y/N]` visible in the save question (`362f17c`), and its first sentence reads "träna på kl 18". |
| every part | the network, for the slides | The repo itself: [results.md](results.md) for parts 6 and 7, the interface and the classes in the editor for part 3, and the comparison file above for part 5. |
| 6 | the tokenizer's vocabulary, which the check downloads on its first run | The tables in [results.md](results.md) as they stand. `pytest` needs neither the network nor the tokenizer. |
| 7 | Docker and the Neo4j container | The chain as the slide draws it. Or the same two queries on the spike's graph for `dad224aa`, where a Saturday wake-up time of 8:30 am is replaced by 7:30 am, taken on 5 October: `presentation/neo4j-spike-dad224aa-replaced-edge.png`, `-held-on-25-may.png` and `-held-on-28-may.png`. The spike is a trial on a history no run measures (ADR 0018). Without a database, the test `test_what_held_before_a_replacement_can_still_be_asked_for` in `tests/test_memory.py` shows the rule. |

Screenshots of the pilot's chain for `c6853660` are not taken yet.
