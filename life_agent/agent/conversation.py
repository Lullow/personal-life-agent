"""The LLM-first conversation loop.

One model call per user message.  The model receives the conversation so far
and answers with a single JSON object::

    {"tool": str | null, "arguments": {...}, "reply": str}

The loop then does what the model may not do for itself:

* :class:`~life_agent.agent.tools.ToolRegistry` decides whether the tool exists
  — a hallucinated name becomes a failed lookup, never an execution;
* ``action_type`` and ``requires_confirmation`` are read **from the registry**,
  never from the model's own JSON, so a write can never present itself as a
  read;
* :func:`~life_agent.agent.policy.validate_decision_safety` re-checks the
  assembled decision;
* nothing is written here.  A mutating tool comes back as
  ``kind="needs_confirmation"`` and the caller asks the user.

See ``docs/llm-first-pivot.md`` for why this replaces the deterministic router.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.policy import validate_decision_safety
from life_agent.agent.prompts import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    AGENT_TOOL_NAMES,
    READ_ANSWER_SYSTEM_PROMPT,
)
from life_agent.agent.tools import ToolRegistry, build_default_tool_registry
from life_agent.schemas.confirmation import ConfirmationProposal
from life_agent.schemas.extraction import ExtractionResult

log = logging.getLogger(__name__)

TurnKind = Literal["reply", "display", "needs_confirmation"]

DEFAULT_HISTORY_TURNS = 10

LLM_UNAVAILABLE_TEXT = (
    "I could not reach the language model, so I did not understand that.\n"
    "Check LIFE_AGENT_LLM_BASE_URL, _API_KEY and _MODEL in your .env."
)
BAD_ARGUMENTS_TEXT = "I got that a bit wrong — could you say it once more?"
BAD_DATE_TEXT = "Which date did you mean?"
NOT_FOUND_TEXT = "I could not find anything saved that matches that."
AMBIGUOUS_TEXT = "That matches more than one saved item — which did you mean?"

# How much retrieved data to hand back to the model when it answers a read.
MAX_DATA_CHARS = 4000

# Read tools that take no arguments.  Anything date-shaped goes through
# list_day / list_range instead, so the agent always names the day it means.
_READ_HANDLERS: dict[str, str] = {
    "list_deadlines": "get_deadlines_response",
    "list_reminders": "get_reminders_response",
}


def _parse_date_argument(value: Any) -> date | None:
    """Read an ISO date out of a model-supplied argument, or ``None``."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _read_tool_call(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Read the tool name and arguments out of a model response.

    The documented envelope is ``{"tool": ..., "arguments": {...}}``, but models
    also write ``{"delete_item": {...}}`` — the right intent in the wrong shape.
    That is accepted when the key is a tool the agent actually has, since the
    registry still decides what the name is allowed to do.
    """
    raw_tool = payload.get("tool")
    if isinstance(raw_tool, str) and raw_tool.strip():
        arguments = payload.get("arguments")
        return raw_tool.strip(), arguments if isinstance(arguments, dict) else {}

    for name in AGENT_TOOL_NAMES:
        value = payload.get(name)
        if isinstance(value, dict):
            return name, value

    return None, {}


def _parse_datetime_argument(value: Any) -> datetime | None:
    """Read an ISO timestamp out of a model-supplied argument, or ``None``."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


class AgentLLMClient(Protocol):
    """Minimal interface the loop needs from an LLM client."""

    def chat_json(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> dict[str, Any] | None: ...


@dataclass
class AgentTurn:
    """The outcome of one user message.

    ``reply`` is always the model's conversational sentence.  ``kind`` says
    what the caller must do next:

    * ``"reply"`` — print the reply, nothing else happened;
    * ``"display"`` — print the reply, then ``text`` (read-only tool output);
    * ``"needs_confirmation"`` — ask the user before anything is written.
    """

    kind: TurnKind
    reply: str
    decision: AgentDecision
    text: str = ""
    proposal: ConfirmationProposal | None = None
    extraction: ExtractionResult | None = None
    data: dict[str, Any] = field(default_factory=dict)


def _no_tool_decision(intent: str, reply: str) -> AgentDecision:
    return AgentDecision(
        intent=intent,
        tool_name=None,
        action_type="clarify",
        requires_confirmation=False,
        user_facing_message=reply or None,
    )


class ConversationAgent:
    """Hold a conversation and turn each message into at most one tool call.

    Parameters
    ----------
    llm_client:
        Anything satisfying :class:`AgentLLMClient`.  Built from settings on
        first use when not supplied; inject a fake in tests.
    registry:
        Tool registry to validate against.  Defaults to the built-in one.
    db_path:
        Database path forwarded to read-only service helpers.
    max_history_turns:
        How many user+assistant pairs to send back to the model.
    reference_date:
        "Today" as the model is told it.  Injectable so tests are stable.
    """

    def __init__(
        self,
        *,
        llm_client: AgentLLMClient | None = None,
        registry: ToolRegistry | None = None,
        db_path: str | None = None,
        max_history_turns: int = DEFAULT_HISTORY_TURNS,
        reference_date: date | None = None,
    ) -> None:
        self._client = llm_client
        self._registry = registry or build_default_tool_registry()
        self._db_path = db_path
        self._max_messages = max_history_turns * 2
        self._reference_date = reference_date
        self._history: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    @property
    def history(self) -> list[dict[str, str]]:
        """The messages sent to the model, oldest first."""
        return list(self._history)

    def record_outcome(self, text: str) -> None:
        """Add what actually happened to the history.

        The caller uses this after a save so the next turn is grounded in the
        real outcome rather than in what the model claimed it did.
        """
        if text and text.strip():
            self._append("assistant", text.strip())

    def _append(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages :]

    # ------------------------------------------------------------------
    # The loop
    # ------------------------------------------------------------------

    def send(self, message: str) -> AgentTurn:
        """Send *message* to the model and act on its answer."""
        text = message.strip()
        if not text:
            return AgentTurn(kind="reply", reply="", decision=_no_tool_decision("empty", ""))

        payload = self._ask_model(text)
        if payload is None:
            return AgentTurn(
                kind="reply",
                reply=LLM_UNAVAILABLE_TEXT,
                decision=_no_tool_decision("llm_unavailable", LLM_UNAVAILABLE_TEXT),
            )

        reply = str(payload.get("reply") or "").strip()
        tool_name, arguments = _read_tool_call(payload)

        self._append("user", text)

        turn = self._act(tool_name, arguments, reply, text)
        self._append("assistant", turn.reply or turn.text)
        return turn

    def _ask_model(self, text: str) -> dict[str, Any] | None:
        client = self._get_client()
        if client is None:
            return None
        messages = [*self._history, {"role": "user", "content": text}]
        try:
            payload = client.chat_json(self.system_prompt(), messages)
        except Exception:
            log.debug("Conversation LLM call failed", exc_info=True)
            return None
        return payload if isinstance(payload, dict) else None

    def system_prompt(self) -> str:
        """The system prompt, with today's date filled in."""
        today = self._reference_date or date.today()
        return AGENT_SYSTEM_PROMPT_TEMPLATE.format(
            today=today.isoformat(), weekday=today.strftime("%A")
        )

    def _get_client(self) -> AgentLLMClient | None:
        if self._client is not None:
            return self._client
        try:
            from life_agent.llm.client import LLMClient

            client = LLMClient.from_settings()
        except Exception:
            return None
        if not client.enabled:
            return None
        self._client = client
        return client

    # ------------------------------------------------------------------
    # Tool validation and dispatch
    # ------------------------------------------------------------------

    def _act(
        self,
        tool_name: str | None,
        arguments: dict[str, Any],
        reply: str,
        message: str,
    ) -> AgentTurn:
        if tool_name is None:
            return AgentTurn(kind="reply", reply=reply, decision=_no_tool_decision("chat", reply))

        tool = self._registry.get(tool_name)
        if tool is None or tool_name not in AGENT_TOOL_NAMES:
            # A hallucinated or out-of-scope tool name: answer, do nothing.
            log.warning("Model asked for unavailable tool %r", tool_name)
            return AgentTurn(
                kind="reply", reply=reply, decision=_no_tool_decision("unavailable_tool", reply)
            )

        # action_type and requires_confirmation come from the registry, not
        # from the model — the model cannot describe a write as a read.
        decision = AgentDecision(
            intent=tool.name,
            tool_name=tool.name,
            action_type=tool.action_type,
            requires_confirmation=tool.requires_confirmation,
            arguments=arguments,
            user_facing_message=reply or None,
        )

        is_safe, reason = validate_decision_safety(decision, self._registry)
        if not is_safe:
            log.warning("Rejected unsafe decision for %r: %s", tool.name, reason)
            return AgentTurn(
                kind="reply", reply=reply, decision=_no_tool_decision("unsafe_decision", reply)
            )

        if tool.name in _READ_HANDLERS:
            return self._display(decision, reply, self._dispatch_read(tool.name), message)

        if tool.name == "list_day":
            return self._dispatch_day(decision, arguments, reply, message)

        if tool.name == "list_range":
            return self._dispatch_range(decision, arguments, reply, message)

        if tool.name == "reschedule_item":
            return self._propose_edit(decision, arguments, reply, "reschedule")

        if tool.name == "delete_item":
            return self._propose_edit(decision, arguments, reply, "delete")

        if tool.name == "save_extracted_items":
            return self._propose_save(decision, arguments, reply)

        if tool.name == "complete_activity":
            return self._propose_completion(decision, arguments, reply, message)

        # ask_clarifying_question and anything else read-only: just the reply.
        return AgentTurn(kind="reply", reply=reply, decision=decision)

    def _dispatch_read(self, tool_name: str) -> str:
        from life_agent.services import read_service

        handler = getattr(read_service, _READ_HANDLERS[tool_name])
        return handler(db_path=self._db_path)

    def _display(
        self, decision: AgentDecision, reply: str, text: str, question: str
    ) -> AgentTurn:
        """Return a read result, with the model's answer grounded in it.

        The first call wrote its reply before any data existed, so it can only
        be a lead-in.  A second call — on reads only — lets the model actually
        answer the question that was asked.  If it fails, the lead-in stands
        and the data below is unaffected.
        """
        answer = self._answer_from_data(question, decision.tool_name or "", text)
        return AgentTurn(
            kind="display", reply=answer or reply, decision=decision, text=text
        )

    def _answer_from_data(self, question: str, tool_name: str, data: str) -> str | None:
        client = self._get_client()
        if client is None:
            return None
        messages = [
            *self._history,
            {"role": "user", "content": question},
            {
                "role": "user",
                "content": f"Data from {tool_name}:\n{data[:MAX_DATA_CHARS]}",
            },
        ]
        try:
            payload = client.chat_json(READ_ANSWER_SYSTEM_PROMPT, messages)
        except Exception:
            log.debug("Read-answer call failed; keeping the lead-in", exc_info=True)
            return None
        if not isinstance(payload, dict):
            return None
        answer = str(payload.get("reply") or "").strip()
        return answer or None

    def _propose_edit(
        self,
        decision: AgentDecision,
        arguments: dict[str, Any],
        reply: str,
        flow: str,
    ) -> AgentTurn:
        """Resolve what the model described to exactly one saved row, or ask."""
        from life_agent.services.edit_service import ITEM_TYPES, find_items

        new_time: datetime | None = None
        if flow == "reschedule":
            new_time = _parse_datetime_argument(arguments.get("new_time"))
            if new_time is None:
                return AgentTurn(
                    kind="reply",
                    reply=reply or BAD_DATE_TEXT,
                    decision=_no_tool_decision("missing_time", reply),
                )

        item_type = arguments.get("item_type")
        if item_type not in ITEM_TYPES:
            item_type = None

        matches = find_items(
            title=arguments.get("title") if isinstance(arguments.get("title"), str) else None,
            item_type=item_type,
            day=_parse_date_argument(arguments.get("date")),
            db_path=self._db_path,
        )

        if not matches:
            return AgentTurn(
                kind="reply",
                reply=NOT_FOUND_TEXT,
                decision=_no_tool_decision("no_match", reply),
            )

        if len(matches) > 1:
            listing = "\n".join(f"  - {m.describe()}" for m in matches[:10])
            return AgentTurn(
                kind="reply",
                reply=AMBIGUOUS_TEXT,
                decision=_no_tool_decision("ambiguous_match", reply),
                text=listing,
            )

        return AgentTurn(
            kind="needs_confirmation",
            reply=reply,
            decision=decision,
            data={"flow": flow, "match": matches[0], "new_time": new_time},
        )

    def _dispatch_day(
        self, decision: AgentDecision, arguments: dict[str, Any], reply: str, message: str
    ) -> AgentTurn:
        from life_agent.services.read_service import get_day_response

        day = _parse_date_argument(arguments.get("date"))
        if day is None:
            # Answering for the wrong day is worse than asking which one.
            return AgentTurn(
                kind="reply",
                reply=reply or BAD_DATE_TEXT,
                decision=_no_tool_decision("missing_date", reply),
            )
        return self._display(
            decision, reply, get_day_response(day, db_path=self._db_path), message
        )

    def _dispatch_range(
        self, decision: AgentDecision, arguments: dict[str, Any], reply: str, message: str
    ) -> AgentTurn:
        from life_agent.services.read_service import get_range_response

        start = _parse_date_argument(arguments.get("from"))
        end = _parse_date_argument(arguments.get("to"))
        start, end = start or end, end or start
        if start is None or end is None:
            return AgentTurn(
                kind="reply",
                reply=reply or BAD_DATE_TEXT,
                decision=_no_tool_decision("missing_date", reply),
            )
        if end < start:
            start, end = end, start
        return self._display(
            decision, reply, get_range_response(start, end, db_path=self._db_path), message
        )

    def _propose_save(
        self, decision: AgentDecision, arguments: dict[str, Any], reply: str
    ) -> AgentTurn:
        from life_agent.services.confirmation_service import build_confirmation_proposal

        try:
            extraction = ExtractionResult.model_validate(arguments)
        except Exception:
            log.warning("Model produced arguments that are not an ExtractionResult")
            return AgentTurn(
                kind="reply",
                reply=reply or BAD_ARGUMENTS_TEXT,
                decision=_no_tool_decision("invalid_arguments", reply),
            )

        proposal = build_confirmation_proposal(extraction)
        if proposal.saveable_count == 0:
            return AgentTurn(
                kind="reply",
                reply=reply,
                decision=decision,
                proposal=proposal,
                extraction=extraction,
            )

        return AgentTurn(
            kind="needs_confirmation",
            reply=reply,
            decision=decision,
            proposal=proposal,
            extraction=extraction,
            data={"flow": "save"},
        )

    def _propose_completion(
        self,
        decision: AgentDecision,
        arguments: dict[str, Any],
        reply: str,
        message: str,
    ) -> AgentTurn:
        from life_agent.services.completion_service import find_completion_candidate

        text = str(arguments.get("text") or message)
        candidate = find_completion_candidate(text, db_path=self._db_path)
        if candidate is None:
            return AgentTurn(
                kind="reply",
                reply=reply,
                decision=decision,
                data={"flow": "complete", "candidate": None},
            )
        return AgentTurn(
            kind="needs_confirmation",
            reply=reply,
            decision=decision,
            data={"flow": "complete", "candidate": candidate},
        )
