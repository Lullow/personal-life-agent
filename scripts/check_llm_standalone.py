"""Can the LLM client be called without the agent around it?

The LongMemEval harness drives the memory layer headless: no
``ConversationAgent``, no ``ToolRegistry``, no ``AgentPolicy``. It needs to hand
the model a system prompt plus retrieved context plus a question, and get an
answer back. This script checks that against the configured model, importing
nothing from ``life_agent/agent/``.

It calls the real model three times and costs a fraction of a cent:

1. ``chat_json`` with a minimal schema of our own, ``{"answer": ...}`` — does
   the client need the agent's ``tool``/``arguments``/``reply`` envelope?
2. ``chat_json`` with a prompt that asks for prose and never mentions JSON —
   what the harness gets if it forgets the client is JSON-only.
3. The plain-text transport underneath, ``json_mode=False`` — whether a text
   path exists at all. It is private, so this is a probe, not a recommendation.

Each call also prints the provider's ``usage`` block, captured off the wire,
because ``chat_json`` does not return it.

    .venv/bin/python scripts/check_llm_standalone.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from life_agent.llm.client import LLMClient  # noqa: E402

CONTEXT = [
    {"role": "user", "content": "My sister Lina just moved to Gothenburg."},
    {"role": "assistant", "content": "That's a big move — I hope she settles in well."},
    {"role": "user", "content": "She starts her new job at the hospital on Monday."},
    {"role": "assistant", "content": "Good luck to her on the first day."},
]
QUESTION = {"role": "user", "content": "Which city does my sister live in now?"}

JSON_SYSTEM_PROMPT = (
    "Answer the user's question using only the conversation above. "
    'Respond with a JSON object of the form {"answer": "<short answer>"}.'
)
PROSE_SYSTEM_PROMPT = (
    "Answer the user's question using only the conversation above, "
    "in one short sentence."
)


def _show_usage(captured: dict) -> None:
    usage = (captured.get("response") or {}).get("usage")
    print(f"  usage on the wire: {json.dumps(usage) if usage else 'none reported'}")


def main() -> int:
    client = LLMClient.from_settings()
    if not client.enabled:
        print("LLM client is disabled: set LIFE_AGENT_LLM_BASE_URL, _API_KEY and _MODEL.")
        return 1
    print(f"model: {client.model}  base_url: {client.base_url}\n")

    # Record the raw response so the usage block is visible; chat_json drops it.
    captured: dict = {}
    transport = client._post

    def recording_post(url: str, payload: dict) -> dict:
        captured["response"] = None
        captured["response"] = transport(url, payload)
        return captured["response"]

    client._post = recording_post  # type: ignore[method-assign]
    messages = [*CONTEXT, QUESTION]

    print("1. chat_json, own minimal schema {\"answer\": ...}")
    result = client.chat_json(JSON_SYSTEM_PROMPT, messages)
    print(f"  returned: {result!r}")
    _show_usage(captured)

    print("\n2. chat_json, prose prompt that never mentions JSON")
    result = client.chat_json(PROSE_SYSTEM_PROMPT, messages)
    print(f"  returned: {result!r}")
    # chat_json swallows every error, so repeat the call underneath to see why.
    try:
        raw = client._chat_completion_messages(PROSE_SYSTEM_PROMPT, messages, json_mode=True)
        print(f"  raw content under json_mode: {raw!r}")
    except urllib.error.HTTPError as exc:
        print(f"  underlying error: HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
    except Exception as exc:
        print(f"  underlying error: {type(exc).__name__}: {exc}")

    print("\n3. plain-text transport, json_mode=False (private)")
    try:
        text = client._chat_completion_messages(PROSE_SYSTEM_PROMPT, messages, json_mode=False)
        print(f"  returned: {text!r}")
        _show_usage(captured)
    except Exception as exc:
        print(f"  error: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
