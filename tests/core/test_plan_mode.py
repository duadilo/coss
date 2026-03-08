"""Tests for PlanMode."""
import pytest
from opencode.core.plan_mode import PlanMode


class TestPlanMode:
    def test_initially_inactive(self):
        pm = PlanMode()
        assert pm.is_active is False

    def test_activate(self):
        pm = PlanMode()
        pm.activate()
        assert pm.is_active is True

    def test_deactivate(self):
        pm = PlanMode()
        pm.activate()
        pm.deactivate()
        assert pm.is_active is False

    def test_toggle_activates(self):
        pm = PlanMode()
        result = pm.toggle()
        assert result is True
        assert pm.is_active is True

    def test_toggle_deactivates(self):
        pm = PlanMode()
        pm.activate()
        result = pm.toggle()
        assert result is False
        assert pm.is_active is False

    def test_toggle_returns_new_state(self):
        pm = PlanMode()
        state1 = pm.toggle()
        state2 = pm.toggle()
        assert state1 is True
        assert state2 is False

    def test_system_prompt_addendum_when_inactive(self):
        pm = PlanMode()
        assert pm.get_system_prompt_addendum() == ""

    def test_system_prompt_addendum_when_active(self):
        pm = PlanMode()
        pm.activate()
        addendum = pm.get_system_prompt_addendum()
        assert "PLAN MODE" in addendum
        assert "read-only" in addendum

    def test_system_prompt_mentions_tools(self):
        pm = PlanMode()
        pm.activate()
        addendum = pm.get_system_prompt_addendum()
        assert "glob" in addendum
        assert "grep" in addendum
        assert "read" in addendum

    def test_multiple_activations_idempotent(self):
        pm = PlanMode()
        pm.activate()
        pm.activate()
        assert pm.is_active is True

    def test_multiple_deactivations_idempotent(self):
        pm = PlanMode()
        pm.deactivate()
        pm.deactivate()
        assert pm.is_active is False
