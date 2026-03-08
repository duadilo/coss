"""Tests for the PermissionManager."""
import pytest
from opencode.core.message import ToolCall
from opencode.core.permissions import (
    PermissionCategory,
    PermissionDecision,
    PermissionManager,
)
from opencode.tools.base import ToolDefinition


def make_tool_def(name: str, is_read_only: bool = False, requires_permission: bool = True) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="test",
        is_read_only=is_read_only,
        requires_permission=requires_permission,
    )


def make_tool_call(name: str, arguments: dict | None = None) -> ToolCall:
    return ToolCall(id="test-id", name=name, arguments=arguments or {})


class TestPermissionCategory:
    def test_tool_category_mapping(self):
        pm = PermissionManager()
        assert pm.get_category("bash") == PermissionCategory.BASH
        assert pm.get_category("edit") == PermissionCategory.WRITE
        assert pm.get_category("write") == PermissionCategory.WRITE
        assert pm.get_category("read") == PermissionCategory.READ
        assert pm.get_category("glob") == PermissionCategory.READ
        assert pm.get_category("grep") == PermissionCategory.READ
        assert pm.get_category("web_fetch") == PermissionCategory.WEB
        assert pm.get_category("web_search") == PermissionCategory.WEB

    def test_unknown_tool_is_other(self):
        pm = PermissionManager()
        assert pm.get_category("unknown_tool") == PermissionCategory.OTHER


class TestReadOnlyTools:
    def test_read_only_no_permission_required_is_allowed(self):
        pm = PermissionManager()
        tc = make_tool_call("glob")
        td = make_tool_def("glob", is_read_only=True, requires_permission=False)
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_read_only_but_requires_permission_is_not_auto_allowed(self):
        pm = PermissionManager(auto_allow_reads=False)
        tc = make_tool_call("web_search")
        td = make_tool_def("web_search", is_read_only=True, requires_permission=True)
        assert pm.check(tc, td) == PermissionDecision.PROMPT

    def test_auto_allow_reads_allows_read_category(self):
        pm = PermissionManager(auto_allow_reads=True)
        tc = make_tool_call("read")
        td = make_tool_def("read", is_read_only=False, requires_permission=True)
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_no_auto_allow_reads_prompts_for_read(self):
        pm = PermissionManager(auto_allow_reads=False)
        tc = make_tool_call("read")
        td = make_tool_def("read", is_read_only=False, requires_permission=True)
        assert pm.check(tc, td) == PermissionDecision.PROMPT


class TestWritePermissions:
    def test_write_tool_prompts_by_default(self):
        pm = PermissionManager()
        tc = make_tool_call("write")
        td = make_tool_def("write")
        assert pm.check(tc, td) == PermissionDecision.PROMPT

    def test_auto_allow_writes_allows_write(self):
        pm = PermissionManager(auto_allow_writes=True)
        tc = make_tool_call("write")
        td = make_tool_def("write")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_auto_allow_writes_allows_edit(self):
        pm = PermissionManager(auto_allow_writes=True)
        tc = make_tool_call("edit")
        td = make_tool_def("edit")
        assert pm.check(tc, td) == PermissionDecision.ALLOW


class TestBashPermissions:
    def test_bash_prompts_by_default(self):
        pm = PermissionManager()
        tc = make_tool_call("bash", {"command": "rm -rf /"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.PROMPT

    def test_auto_allow_bash(self):
        pm = PermissionManager(auto_allow_bash=True)
        tc = make_tool_call("bash", {"command": "any command"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_bash_pattern_exact_match(self):
        pm = PermissionManager(bash_patterns=["git status"])
        tc = make_tool_call("bash", {"command": "git status"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_bash_pattern_glob_wildcard(self):
        pm = PermissionManager(bash_patterns=["git *"])
        tc = make_tool_call("bash", {"command": "git diff HEAD"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_bash_pattern_no_match(self):
        pm = PermissionManager(bash_patterns=["git *"])
        tc = make_tool_call("bash", {"command": "rm -rf /"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.PROMPT

    def test_bash_no_command_arg_falls_through(self):
        pm = PermissionManager(bash_patterns=["git *"])
        tc = make_tool_call("bash", {})  # no command key
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.PROMPT


class TestSessionAlwaysAllow:
    def test_always_allow_category(self):
        pm = PermissionManager()
        pm.always_allow_category(PermissionCategory.WRITE)
        tc = make_tool_call("edit")
        td = make_tool_def("edit")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_always_allow_bash_category(self):
        pm = PermissionManager()
        pm.always_allow_category(PermissionCategory.BASH)
        tc = make_tool_call("bash", {"command": "dangerous command"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_add_bash_pattern(self):
        pm = PermissionManager()
        pm.add_bash_pattern("pytest *")
        tc = make_tool_call("bash", {"command": "pytest tests/"})
        td = make_tool_def("bash")
        assert pm.check(tc, td) == PermissionDecision.ALLOW

    def test_bash_patterns_property(self):
        pm = PermissionManager(bash_patterns=["git *"])
        pm.add_bash_pattern("pytest *")
        assert "git *" in pm.bash_patterns
        assert "pytest *" in pm.bash_patterns
