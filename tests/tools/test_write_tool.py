"""Tests for WriteTool."""
import pytest
from pathlib import Path
from opencode.tools.write_tool import WriteTool


@pytest.fixture
def tool():
    return WriteTool()


class TestWriteToolDefinition:
    def test_name(self):
        assert WriteTool().definition().name == "write"

    def test_not_read_only(self):
        assert WriteTool().definition().is_read_only is False

    def test_requires_permission(self):
        assert WriteTool().definition().requires_permission is True


class TestWriteToolExecute:
    @pytest.mark.asyncio
    async def test_write_new_file(self, tool, tmp_path):
        f = tmp_path / "output.txt"
        result = await tool.execute(file_path=str(f), content="hello world")
        assert not result.is_error
        assert f.read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_write_reports_bytes(self, tool, tmp_path):
        f = tmp_path / "output.txt"
        content = "hello"
        result = await tool.execute(file_path=str(f), content=content)
        assert str(len(content)) in result.content

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, tool, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old content")
        result = await tool.execute(file_path=str(f), content="new content")
        assert not result.is_error
        assert f.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_creates_parent_directories(self, tool, tmp_path):
        f = tmp_path / "deep" / "nested" / "dir" / "file.txt"
        result = await tool.execute(file_path=str(f), content="nested")
        assert not result.is_error
        assert f.exists()
        assert f.read_text() == "nested"

    @pytest.mark.asyncio
    async def test_write_empty_content(self, tool, tmp_path):
        f = tmp_path / "empty.txt"
        result = await tool.execute(file_path=str(f), content="")
        assert not result.is_error
        assert f.read_text() == ""

    @pytest.mark.asyncio
    async def test_write_multiline_content(self, tool, tmp_path):
        f = tmp_path / "code.py"
        content = "def hello():\n    print('world')\n"
        result = await tool.execute(file_path=str(f), content=content)
        assert not result.is_error
        assert f.read_text() == content

    @pytest.mark.asyncio
    async def test_write_unicode_content(self, tool, tmp_path):
        f = tmp_path / "unicode.txt"
        content = "Hello 世界 🌍"
        result = await tool.execute(file_path=str(f), content=content)
        assert not result.is_error
        assert f.read_text() == content
