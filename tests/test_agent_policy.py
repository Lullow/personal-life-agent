"""Tests for life_agent.agent.policy."""

import pytest

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.policy import requires_confirmation, validate_decision_safety
from life_agent.agent.tools import build_default_tool_registry


class TestRequiresConfirmation:
    @pytest.mark.parametrize("action", ["write", "update", "delete"])
    def test_mutating_actions_require_confirmation(self, action: str):
        assert requires_confirmation(action) is True

    @pytest.mark.parametrize("action", ["read", "clarify"])
    def test_safe_actions_do_not_require_confirmation(self, action: str):
        assert requires_confirmation(action) is False

    def test_unknown_does_not_require_confirmation(self):
        assert requires_confirmation("unknown") is False


class TestValidateDecisionSafety:
    def test_read_decision_is_safe(self):
        d = AgentDecision(intent="show today", action_type="read")
        safe, reason = validate_decision_safety(d)
        assert safe is True
        assert reason is None

    def test_clarify_decision_is_safe(self):
        d = AgentDecision(intent="ask", action_type="clarify")
        safe, reason = validate_decision_safety(d)
        assert safe is True
        assert reason is None

    def test_unknown_action_is_unsafe(self):
        d = AgentDecision(intent="???")
        safe, reason = validate_decision_safety(d)
        assert safe is False
        assert "unknown" in reason

    def test_write_without_confirmation_is_unsafe(self):
        d = AgentDecision(
            intent="save",
            action_type="write",
            requires_confirmation=False,
        )
        safe, reason = validate_decision_safety(d)
        assert safe is False
        assert "confirmation" in reason

    def test_write_with_confirmation_is_safe(self):
        d = AgentDecision(
            intent="save",
            action_type="write",
            requires_confirmation=True,
        )
        safe, reason = validate_decision_safety(d)
        assert safe is True

    def test_update_without_confirmation_is_unsafe(self):
        d = AgentDecision(
            intent="complete",
            action_type="update",
            requires_confirmation=False,
        )
        safe, reason = validate_decision_safety(d)
        assert safe is False

    def test_delete_without_confirmation_is_unsafe(self):
        d = AgentDecision(
            intent="remove",
            action_type="delete",
            requires_confirmation=False,
        )
        safe, reason = validate_decision_safety(d)
        assert safe is False

    def test_missing_tool_is_unsafe(self):
        reg = build_default_tool_registry()
        d = AgentDecision(
            intent="do stuff",
            action_type="read",
            tool_name="nonexistent_tool",
        )
        safe, reason = validate_decision_safety(d, registry=reg)
        assert safe is False
        assert "not registered" in reason

    def test_registered_tool_is_safe(self):
        reg = build_default_tool_registry()
        d = AgentDecision(
            intent="show today",
            action_type="read",
            tool_name="list_today",
        )
        safe, reason = validate_decision_safety(d, registry=reg)
        assert safe is True

    def test_no_registry_skips_tool_check(self):
        d = AgentDecision(
            intent="show today",
            action_type="read",
            tool_name="anything",
        )
        safe, reason = validate_decision_safety(d)
        assert safe is True
