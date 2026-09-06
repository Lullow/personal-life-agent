"""LLM client wrapper for OpenAI-compatible chat-completions APIs.

This wrapper is intentionally dependency-free: it talks to any
OpenAI-compatible endpoint (OpenAI, OpenRouter, local servers, …) using only
the Python standard library (``urllib``).  It is also intentionally *safe by
default*:

* If the provider is not fully configured (missing base URL, API key, or
  model), the client is **disabled** and ``chat_json`` returns ``None`` so the
  caller can say so rather than crash.
* Any network/parse error results in ``None`` rather than an exception, so a
  flaky provider can never take the application down.

The client only returns parsed JSON.  What that JSON is allowed to mean is
decided one layer up by the tool registry, and nothing is ever written to the
database here.
"""

import json
import os
import re
import urllib.request


def _extract_json(text: str | None) -> dict | None:
    """Best-effort parse of a model response into a JSON object.

    Tolerates Markdown code fences and leading/trailing prose by falling back
    to the first ``{...}`` block.  Returns ``None`` if no JSON object is found.
    """
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    try:
        obj = json.loads(t)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", t, re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
        except (ValueError, TypeError):
            return None
    return obj if isinstance(obj, dict) else None


class LLMClient:
    """A minimal OpenAI-compatible chat-completions client.

    The client is *enabled* only when a base URL, API key, and model are all
    available (via constructor arguments or ``LIFE_AGENT_LLM_*`` environment
    variables).  Pass ``enabled`` explicitly to override this for testing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        enabled: bool | None = None,
        model: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LIFE_AGENT_LLM_API_KEY")
        self.base_url = (
            base_url if base_url is not None else os.getenv("LIFE_AGENT_LLM_BASE_URL")
        )
        self.model = model if model is not None else os.getenv("LIFE_AGENT_LLM_MODEL")
        self.provider = (
            provider
            if provider is not None
            else os.getenv("LIFE_AGENT_LLM_PROVIDER", "openai_compatible")
        )
        self.timeout = timeout
        if enabled is None:
            self.enabled = bool(self.api_key and self.base_url and self.model)
        else:
            self.enabled = enabled

    @classmethod
    def from_settings(cls, settings=None) -> "LLMClient":
        """Build a client from application :class:`Settings`."""
        from life_agent.config import get_settings

        s = settings or get_settings()
        return cls(
            api_key=s.llm_api_key,
            base_url=s.llm_base_url,
            model=s.llm_model,
            provider=s.llm_provider,
        )

    def chat_json(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> dict | None:
        """Return a parsed JSON object for a multi-turn conversation.

        *messages* is the conversation so far as ``{"role", "content"}`` dicts
        (``"user"`` / ``"assistant"``); the system prompt is prepended here.
        This is the single JSON contract used by the conversation loop, kept
        in one place so native tool-calling can replace it later without the
        runtime noticing.

        Never raises: a disabled client, network failure, or unparseable
        response all yield ``None``.
        """
        if not self.enabled:
            return None
        try:
            content = self._chat_completion_messages(
                system_prompt, messages, json_mode=True
            )
        except Exception:
            return None
        return _extract_json(content)

    # -- low-level transport (separated so tests can monkeypatch it) --------

    def _chat_completion_messages(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
    ) -> str | None:
        """Call the chat-completions endpoint with a full message list."""
        url = (self.base_url or "").rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            "temperature": 0 if json_mode else 0.7,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post(url, payload)
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        return message.get("content")

    def _post(self, url: str, payload: dict) -> dict:
        """POST JSON to *url* with bearer auth and return the parsed response."""
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)
