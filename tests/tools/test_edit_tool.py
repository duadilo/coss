"""Tests for EditTool."""
import pytest
from pathlib import Path
from opencode.tools.edit_tool import EditTool


@pytest.fixture
def tmp_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world\nhello again\n")
    return f


@pytest.fixture
def tool():
    return EditTool()


class TestEditToolDefinition:
    def test_name(self):
        assert EditTool().definition().name == "edit"

    def test_not_read_only(self):
        assert EditTool().definition().is_read_only is False

    def test_requires_permission(self):
        assert EditTool().definition().requires_permission is True

    def test_has_replace_all_param(self):
        params = {p.name: p for p in EditTool().definition().parameters}
        assert "replace_all" in params
        assert params["replace_all"].required is False
        assert params["replace_all"].default is False


class TestEditToolExecute:
    @pytest.mark.asyncio
    async def test_basic_replacement(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="hello world",
            new_string="goodbye world",
        )
        assert not result.is_error
        assert "1 occurrence" in result.content
        assert tmp_file.read_text() == "goodbye world\nhello again\n"

    @pytest.mark.asyncio
    async def test_file_not_found(self, tool, tmp_path):
        result = await tool.execute(
            file_path=str(tmp_path / "nonexistent.txt"),
            old_string="x",
            new_string="y",
        )
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_old_string_not_found(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="this does not exist in the file",
            new_string="replacement",
        )
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_ambiguous_match_errors_without_replace_all(self, tool, tmp_file):
        # "hello" appears twice
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="hello",
            new_string="hi",
        )
        assert result.is_error
        assert "2 times" in result.content or "replace_all" in result.content

    @pytest.mark.asyncio
    async def test_replace_all_replaces_multiple(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="hello",
            new_string="hi",
            replace_all=True,
        )
        assert not result.is_error
        content = tmp_file.read_text()
        assert "hi world" in content
        assert "hi again" in content
        assert "hello" not in content

    @pytest.mark.asyncio
    async def test_replace_all_count_in_result(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="hello",
            new_string="hi",
            replace_all=True,
        )
        assert "2 occurrence" in result.content

    @pytest.mark.asyncio
    async def test_single_occurrence_without_replace_all(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="world",
            new_string="earth",
        )
        assert not result.is_error
        content = tmp_file.read_text()
        assert "earth" in content

    @pytest.mark.asyncio
    async def test_multiline_replacement(self, tool, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text("def foo():\n    return 1\n")
        result = await tool.execute(
            file_path=str(f),
            old_string="def foo():\n    return 1",
            new_string="def foo():\n    return 42",
        )
        assert not result.is_error
        assert "42" in f.read_text()

    @pytest.mark.asyncio
    async def test_replace_with_empty_string(self, tool, tmp_file):
        result = await tool.execute(
            file_path=str(tmp_file),
            old_string="hello world\n",
            new_string="",
        )
        assert not result.is_error
        assert "hello world" not in tmp_file.read_text()
