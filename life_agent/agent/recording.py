"""Measuring what a model call costs, at the client boundary.

Cost is counted on the LLM client rather than inside a memory strategy, because
a strategy that recalls more makes the *answer* call more expensive, and only
the client sees that call.  :class:`RecordingLLMClient` wraps any
:class:`~life_agent.agent.conversation.AgentLLMClient` and logs every call it
passes through.  A strategy that needs a model is handed one already labelled,
so it never knows it is being measured.

The token counter is injected: this module never imports a tokenizer, so the
app and the tests stay offline.  See
``docs/adr/0006-tokens-counted-with-o200k-base.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from life_agent.agent.conversation import AgentLLMClient
    from life_agent.agent.memory import TokenCounter


@dataclass(frozen=True)
class LLMCall:
    """One call as the recording client saw it.

    ``input_tokens`` counts the system prompt and every message's content, not
    the per-message framing the provider adds.  ``output_tokens`` counts the
    returned JSON serialised again, which may differ from what the model
    emitted in whitespace.  Both undercount the bill slightly, and by the same
    amount for every strategy.
    """

    label: str
    input_tokens: int
    output_tokens: int
    failed: bool
    # The model the call was made with, so that a cost figure can price each
    # call at its own rate (ADR 0012): the consolidator's tokens cost a
    # fraction of the answering model's.  None when the caller did not say.
    model: str | None = None


class RecordingLLMClient:
    """An ``AgentLLMClient`` that logs each call under a label.

    Several clients can share one *log*, each with its own label ("answer",
    "grade", "consolidate"), so the log records calls in the order they were
    made.  A call whose inner client returned ``None`` is logged as failed with
    no output tokens; whether it counts toward anything is the reader's
    decision, not this class's.
    """

    def __init__(
        self,
        inner: AgentLLMClient,
        *,
        label: str,
        counter: TokenCounter,
        log: list[LLMCall],
        model: str | None = None,
    ) -> None:
        self._inner = inner
        self._label = label
        self._counter = counter
        self._log = log
        self._model = model

    def chat_json(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> dict[str, Any] | None:
        result = self._inner.chat_json(system_prompt, messages)
        input_tokens = self._counter.count(system_prompt) + sum(
            self._counter.count(m["content"]) for m in messages
        )
        # ensure_ascii=False so that non-ASCII text is counted as text, not as
        # the \uXXXX escapes json.dumps would otherwise write.
        output_tokens = (
            0
            if result is None
            else self._counter.count(json.dumps(result, ensure_ascii=False))
        )
        self._log.append(
            LLMCall(
                label=self._label,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                failed=result is None,
                model=self._model,
            )
        )
        return result
