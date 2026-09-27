# 0007 — The baseline fills the budget instead of keeping its turn window

Status: accepted
Date: 2026-09-26

## Context

The comparison is made "at the same token budget". `RecentTurnsMemory`, as
the agent ships it, has two limits: a window of 10 turns (20 messages), and
then the budget.

Measured with `o200k_base` on the 130 eligible questions (0005), replayed as in
0004:

- The last 20 messages before the question hold 1,665 to 6,942 tokens: a median
  of about 4,000 for `single-session-user` and 4,200 for `knowledge-update`.
  **The window binds before the 8000-token budget in every question.**
- Filling the budget instead takes 22 to 90 messages, a median of 38 to 39.
- At least one evidence turn is inside the 20-message window in 6 of 61
  `single-session-user` and 8 of 69 `knowledge-update` questions. Inside the
  budget fill: 6 of 61 and 14 of 69.

With the window kept, the baseline gets roughly half the context the other
strategies get. A difference between the rows would then mix two things:
which tokens a strategy chose, and how many it was allowed.

## Decision

In the evaluation, `RecentTurnsMemory` runs **without a turn window**. Its only
limit is the token budget: it returns the most recent messages that fit in
8000 tokens.

`RecentTurnsMemory` must accept `max_turns=None` to mean no turn limit, and the
harness must construct it that way. Today it computes `max_turns * 2`, which
fails on `None`. The agent's own configuration is unchanged: the default stays
at `DEFAULT_HISTORY_TURNS`, 10 turns.

`tokens_used` is reported per question. The budget is a ceiling; how close a
strategy gets depends on the length of the messages near it.

Considered and rejected:

- **Keeping the 10-turn window.** It measures the agent as it ships, but at
  half the tokens, which confounds the comparison the project is about.
- **Running both.** One more row to explain, for a configuration the question
  does not ask about.

## Consequences

Every strategy receives the same allowance, so the differences between rows
come from what each strategy chose to spend it on.

The baseline's reach is now exactly the budget. Evidence within 8000 tokens of
the question is, by the definition in `docs/vg-project.md`, not long-term, and
those are the questions where the baseline can see it: 6 and 14. On every
long-term question its recall is zero by construction, and a correct answer
there is a guess. The floor hypothesis becomes partly a check that the harness
works.

The baseline that is measured is not the agent's configuration. The method
section has to say that the row labelled `RecentTurnsMemory` is "the most
recent messages that fit the budget", and that the agent's 10-turn window was
not measured. Before this record, the plan in `docs/vg-project.md` said the
window binds before the budget; that is still true of the agent, and no longer
describes the evaluation.

The baseline's precision falls: it now returns about 38 messages rather than
20, with the same evidence among them.

Since every strategy's answer call carries about the same context, "at what
cost" is decided by the calls a strategy adds beyond the answer, such as
consolidation, rather than by the answer call itself.

`retrieve()` always admits the newest record, even when that record alone is
larger than the budget. The largest single message in the pool is 16,857
tokens, but no question's newest message exceeds 8000, so in this pool it does
not happen. The harness must still check, and report a question as over budget
rather than truncate a message.
