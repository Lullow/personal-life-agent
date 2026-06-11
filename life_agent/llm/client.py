"""Thin LLM client wrapper.

In this step the client is intentionally a no-op: ``extract_structured``
always returns ``None`` so the extraction service falls back to the
deterministic rule-based extractor.  A real provider implementation will
live here in a future step.
"""

import os


class LLMClient:
    """A minimal LLM client placeholder.

    The constructor reads ``LIFE_AGENT_LLM_API_KEY`` from the environment but
    never makes a network request.  Set ``enabled=True`` once a real provider
    has been wired up.
    """

    def __init__(
        self,
        api_key: str | None = None,
        enabled: bool | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("LIFE_AGENT_LLM_API_KEY")
        self.model = model or os.getenv("LIFE_AGENT_LLM_MODEL")
        if enabled is None:
            self.enabled = False
        else:
            self.enabled = enabled

    def extract_structured(
        self,
        system_prompt: str,
        user_text: str,
    ) -> dict | None:
        """Return a structured JSON dict from the LLM, or *None* if unavailable.

        Real providers will be plugged in here; for now this always returns
        ``None`` so callers can fall back to the rule-based extractor.
        """
        if not self.enabled:
            return None
        return None
