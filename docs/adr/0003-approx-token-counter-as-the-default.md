# 0003 — ApproxTokenCounter as the default, tiktoken injected in the eval

Status: accepted
Date: 2026-09-06

## Context

Memory budgets are expressed in tokens rather than characters, because token
cost is one of the numbers the evaluation reports and because
characters-per-token differ sharply between a dense summary and a verbose raw
turn — especially in Swedish, whose compounds split into more tokens than
their length suggests. Budgeting in characters would flatter exactly the
strategy the comparison is meant to scrutinise.

`tiktoken` is the correct tokenizer for the OpenAI-compatible endpoints this
project talks to. Two things argue against making it the default:

- It downloads its BPE files over the network on first use. `tests/conftest.py`
  neutralises the local `.env` precisely so the suite is offline and behaves
  identically on a machine with credentials and one without. A default that
  reaches the network on import would end that.
- `pyproject.toml` lists four dependencies, and `life_agent/llm/` talks HTTP
  with nothing but `urllib`. The leanness is deliberate.

## Decision

`TokenCounter` is a Protocol. The default implementation is
`ApproxTokenCounter`, which estimates four characters to the token using no
dependencies and no network.

Where a token count is *published*, a real tokenizer is injected.
`evals/longmemeval.py` will construct its strategies with a tiktoken-backed
counter.

**`evals/longmemeval.py` must raise when handed an `ApproxTokenCounter`, not
warn.** A cost table built on a four-character heuristic is indistinguishable
from a real one once it reaches a report, and a warning scrolls past. The
harness refuses to start.

That harness does not exist yet, so the requirement is recorded as a `TODO` on
`ApproxTokenCounter` in `life_agent/agent/memory.py` pointing here.

## Consequences

The test suite stays offline and the dependency list stays as it is.

Budget enforcement inside `RecentTurnsMemory` is approximate. This is
tolerable: the budget is a guard against overflowing a context window, and the
baseline is bounded by its turn window long before the budget binds.

`Retrieval.tokens_used` means different things depending on which counter was
injected. Anything reading that field for a reported figure has to know which
one it got, which is the reason the harness refuses the estimate rather than
trusting the caller to check.

The estimate under-counts Swedish specifically — the direction that matters
here, since the agent's own conversations are largely Swedish. A budget
computed with it therefore admits somewhat more context than intended rather
than less.

Adding tiktoken later is a dependency change and an eval-only import, not a
change to the interface. The Protocol is what makes that true, so it must not
acquire an implementation detail of any one tokenizer.
