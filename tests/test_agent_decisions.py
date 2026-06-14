"""Tests for life_agent.agent.decisions."""

import pytest
from pydantic import ValidationError

from life_agent.agent.decisions import AgentDecision


class TestAgentDecisionCreation:
    def test_minimal_decision(self):
        d = AgentDecision(intent="show today")
        assert d.intent == "show today"
        assert d.tool_name is None
        assert d.action_type == "unknown"
        assert d.requires_confirmation is False
        assert d.arguments == {}
        assert d.confidence is None
        assert d.user_facing_message is None

    def test_full_decision(self):
        d = AgentDecision(
            intent="save items",
            tool_name="save_extracted_items",
            action_type="write",
            requires_confirmation=True,
            arguments={"text": "hello"},
            confidence=0.95,
            user_facing_message="Saving your items.",
        )
        assert d.intent == "save items"
        assert d.tool_name == "save_extracted_items"
        assert d.action_type == "write"
        assert d.requires_confirmation is True
        assert d.arguments == {"text": "hello"}
        assert d.confidence == 0.95
        assert d.user_facing_message == "Saving your items."


class TestConfidenceValidation:
    def test_valid_zero(self):
        d = AgentDecision(intent="x", confidence=0.0)
        assert d.confidence == 0.0

    def test_valid_one(self):
        d = AgentDecision(intent="x", confidence=1.0)
        assert d.confidence == 1.0

    def test_valid_mid(self):
        d = AgentDecision(intent="x", confidence=0.42)
        assert d.confidence == 0.42

    def test_none_is_allowed(self):
        d = AgentDecision(intent="x", confidence=None)
        assert d.confidence is None

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="confidence"):
            AgentDecision(intent="x", confidence=-0.1)

    def test_above_one_rejected(self):
        with pytest.raises(ValidationError, match="confidence"):
            AgentDecision(intent="x", confidence=1.01)


class TestIsMutating:
    @pytest.mark.parametrize("action", ["write", "update", "delete"])
    def test_mutating(self, action: str):
        d = AgentDecision(intent="x", action_type=action)
        assert d.is_mutating is True

    @pytest.mark.parametrize("action", ["read", "clarify", "unknown"])
    def test_not_mutating(self, action: str):
        d = AgentDecision(intent="x", action_type=action)
        assert d.is_mutating is False
