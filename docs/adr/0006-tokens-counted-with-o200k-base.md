# 0006 — Tokens are counted with o200k_base, for the budget and for cost

Status: accepted
Date: 2026-09-26

## Context

The question the comparison asks is framed in tokens: "at the same token
budget, which kinds of memory question does each strategy answer, and at what
cost?". Two different numbers come out of that, and both have to be counted
the same way for every strategy:

- **the budget**: how much recalled context a strategy may hand the model,
  passed as `budget_tokens` to `retrieve()`;
- **the cost**: how many tokens a strategy makes the model read and write to
  answer one question.

0003 decided that a real tokenizer is injected where a number is published,
and that the harness refuses `ApproxTokenCounter`. It did not decide which
tokenizer, what the budget covers, or where the cost is counted.

`CLAUDE.md` requires cost to be measured on the LLM client, not inside the
memory module, because a strategy that recalls more makes the answer call more
expensive, and only the client sees that call. The client the harness uses is
`LLMClient`, reached through the `AgentLLMClient` Protocol:
`chat_json(system_prompt, messages)`, which returns parsed JSON and drops the
provider's `usage` block.

## Decision

**One tokenizer:** tiktoken's `o200k_base`, for the budget and for cost,
whichever model answers. It is the tokenizer of the gpt-4o family, which 0008
uses, so for this project the count also tracks what is billed. The
tiktoken-backed counter must encode with `disallowed_special=()`, so that a
turn which happens to contain a special-token string such as `<|endoftext|>`
is counted as ordinary text instead of raising. No turn in the pool contains
one today.

**The budget is 8000 tokens** (`DEFAULT_BUDGET_TOKENS`) for every strategy. It
counts the content of the records a strategy returns and nothing else: not role
framing, not the system prompt, not the question.

**Cost is counted at the Protocol boundary.** `RecordingLLMClient` must wrap
any `AgentLLMClient`. It is constructed with a label ("answer", "grade", and in
M3 "consolidate"), a `TokenCounter`, and a shared call log. For every call it
logs the label, the input tokens (the system prompt plus every message's
content), the output tokens (the returned JSON, serialised again) and whether
the call returned `None`. A strategy that needs a model is handed a client
already labelled, so it never knows it is being measured.

**A strategy's cost** for one question is the sum over every call it caused:
the answer call, and in M3 its consolidation calls. Only the attempt that
succeeded counts; a retry after a failed call (0008) is the provider's
failure, not the strategy's cost. Grading calls and failed attempts are logged,
since they may cost money, but they are the measurement's cost, not the
strategy's.

Before the pilot, the count for one real call is checked by hand against the
`usage` block OpenRouter returns; `scripts/check_llm_standalone.py` already
reads it off the wire.

Considered and rejected:

- **The provider's `usage` block as the reported figure.** `chat_json` does not
  return it, and a wrapper that reaches into the client's transport would only
  work for one client class, never for the fakes the tests use. `usage` also
  changes meaning with the provider's tokenizer, which is the variation this
  record removes.
- **A per-model tokenizer.** Every figure would change if the model did, and
  tokens are the unit the strategies are compared in.

## Consequences

Every strategy is budgeted and charged in the same unit, and the unit does not
move if the provider does.

The count is slightly below the bill. Per-message framing is not counted: a
few tokens per message, around 120 on a full answer call. The output count is
the JSON as serialised again, not as the model emitted it, so whitespace may
differ. Both errors are small and apply to every strategy the same way.

The prompt the model reads is larger than the budget: the budget covers
recalled content only. The reported cost is the whole call.

tiktoken becomes an eval-only dependency, installed as an optional extra.
Nothing under `life_agent/` or `tests/` imports it: `RecordingLLMClient` takes
its counter injected, and the tiktoken-backed counter lives in the harness.
tiktoken fetches its encoding file over the network the first time it is used.
