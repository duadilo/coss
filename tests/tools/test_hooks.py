"""Tests for HookManager."""
import pytest
from opencode.config.settings import HookEntry
from opencode.core.message import ToolCall
from opencode.hooks.manager import HookManager, HookResult


def make_tool_call(name: str = "bash", args: dict | None = None) -> ToolCall:
    return ToolCall(id="call-1", name=name, arguments=args or {"command": "ls"})


class TestHookResult:
    def test_success(self):
        hook = HookEntry(event="pre_tool_call", command="echo hi")
        result = HookResult(hook, "output", 0)
        assert result.success is True

    def test_failure(self):
        hook = HookEntry(event="pre_tool_call", command="exit 1")
        result = HookResult(hook, "error", 1)
        assert result.success is False


class TestHookManagerFindMatching:
    def test_wildcard_matches_any_tool(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="*", command="echo pre")]
        hm = HookManager(hooks)
        matching = hm._find_matching("pre_tool_call", "bash")
        assert len(matching) == 1

    def test_specific_pattern_matches(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="bash", command="guard.sh")]
        hm = HookManager(hooks)
        assert len(hm._find_matching("pre_tool_call", "bash")) == 1
        assert len(hm._find_matching("pre_tool_call", "read")) == 0

    def test_glob_pattern(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="web*", command="echo web")]
        hm = HookManager(hooks)
        assert len(hm._find_matching("pre_tool_call", "web_fetch")) == 1
        assert len(hm._find_matching("pre_tool_call", "web_search")) == 1
        assert len(hm._find_matching("pre_tool_call", "bash")) == 0

    def test_event_filter(self):
        hooks = [
            HookEntry(event="pre_tool_call", tool_pattern="*", command="pre.sh"),
            HookEntry(event="post_tool_call", tool_pattern="*", command="post.sh"),
        ]
        hm = HookManager(hooks)
        pre = hm._find_matching("pre_tool_call", "bash")
        post = hm._find_matching("post_tool_call", "bash")
        assert len(pre) == 1
        assert pre[0].command == "pre.sh"
        assert len(post) == 1
        assert post[0].command == "post.sh"

    def test_no_hooks(self):
        hm = HookManager()
        assert hm._find_matching("pre_tool_call", "bash") == []


class TestHookManagerHasBlockingFailure:
    def test_no_results_no_failure(self):
        hm = HookManager()
        assert hm.has_blocking_failure([]) is None

    def test_all_success_no_failure(self):
        hook = HookEntry(event="pre_tool_call", command="echo ok")
        results = [HookResult(hook, "ok", 0), HookResult(hook, "ok", 0)]
        hm = HookManager()
        assert hm.has_blocking_failure(results) is None

    def test_failure_returns_message(self):
        hook = HookEntry(event="pre_tool_call", command="fail.sh")
        results = [HookResult(hook, "blocked", 1)]
        hm = HookManager()
        msg = hm.has_blocking_failure(results)
        assert msg is not None
        assert "fail.sh" in msg
        assert "1" in msg

    def test_first_failure_returned(self):
        hook1 = HookEntry(event="pre_tool_call", command="check1.sh")
        hook2 = HookEntry(event="pre_tool_call", command="check2.sh")
        results = [HookResult(hook1, "err1", 1), HookResult(hook2, "err2", 2)]
        hm = HookManager()
        msg = hm.has_blocking_failure(results)
        assert "check1.sh" in msg


class TestHookManagerRunHooks:
    @pytest.mark.asyncio
    async def test_run_pre_hooks_echo(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="bash", command="echo hello")]
        hm = HookManager(hooks)
        tc = make_tool_call("bash")
        results = await hm.run_pre_hooks(tc)
        assert len(results) == 1
        assert results[0].success
        assert "hello" in results[0].output

    @pytest.mark.asyncio
    async def test_run_post_hooks(self):
        hooks = [HookEntry(event="post_tool_call", tool_pattern="*", command="echo done")]
        hm = HookManager(hooks)
        tc = make_tool_call("read")
        results = await hm.run_post_hooks(tc)
        assert len(results) == 1
        assert results[0].success

    @pytest.mark.asyncio
    async def test_hook_receives_tool_env_vars(self):
        hooks = [
            HookEntry(
                event="pre_tool_call",
                tool_pattern="bash",
                command="echo $OPENCODE_TOOL_NAME",
            )
        ]
        hm = HookManager(hooks)
        tc = make_tool_call("bash", {"command": "ls"})
        results = await hm.run_pre_hooks(tc)
        assert "bash" in results[0].output

    @pytest.mark.asyncio
    async def test_hook_failure_detected(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="*", command="exit 2")]
        hm = HookManager(hooks)
        tc = make_tool_call("bash")
        results = await hm.run_pre_hooks(tc)
        assert not results[0].success
        assert results[0].returncode == 2

    @pytest.mark.asyncio
    async def test_no_matching_hooks_returns_empty(self):
        hooks = [HookEntry(event="pre_tool_call", tool_pattern="bash", command="echo hi")]
        hm = HookManager(hooks)
        tc = make_tool_call("read")
        results = await hm.run_pre_hooks(tc)
        assert results == []
