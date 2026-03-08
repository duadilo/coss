"""Tests for ReadTool."""
import pytest
from pathlib import Path
from opencode.tools.read_tool import ReadTool


@pytest.fixture
def tool():
    return ReadTool()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.txt"
    lines = [f"line {i}" for i in range(1, 11)]  # lines 1-10
    f.write_text("\n".join(lines) + "\n")
    return f


class TestReadToolDefinition:
    def test_name(self):
        assert ReadTool().definition().name == "read"

    def test_is_read_only(self):
        assert ReadTool().definition().is_read_only is True

    def test_no_permission_required(self):
        assert ReadTool().definition().requires_permission is False


class TestReadToolExecute:
    @pytest.mark.asyncio
    async def test_read_full_file(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file))
        assert not result.is_error
        for i in range(1, 11):
            assert f"line {i}" in result.content

    @pytest.mark.asyncio
    async def test_line_numbers_present(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file))
        assert "1\t" in result.content or "     1\t" in result.content

    @pytest.mark.asyncio
    async def test_file_not_found(self, tool, tmp_path):
        result = await tool.execute(file_path=str(tmp_path / "missing.txt"))
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_read_with_offset(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file), offset=5)
        assert not result.is_error
        # Should start from line 5
        assert "line 5" in result.content
        # "line 1" through "line 4" should not appear (checking line 4 specifically)
        assert "line 4" not in result.content

    @pytest.mark.asyncio
    async def test_read_with_limit(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file), limit=3)
        assert not result.is_error
        assert "line 1" in result.content
        assert "line 2" in result.content
        assert "line 3" in result.content
        assert "line 4" not in result.content

    @pytest.mark.asyncio
    async def test_read_with_offset_and_limit(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file), offset=3, limit=2)
        assert not result.is_error
        # Lines 3 and 4 only
        assert "line 3" in result.content
        assert "line 4" in result.content
        assert "line 2" not in result.content
        assert "line 5" not in result.content

    @pytest.mark.asyncio
    async def test_empty_file(self, tool, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = await tool.execute(file_path=str(f))
        assert not result.is_error
        assert "empty" in result.content

    @pytest.mark.asyncio
    async def test_long_line_truncated(self, tool, tmp_path):
        f = tmp_path / "long.txt"
        f.write_text("x" * 3000 + "\n")
        result = await tool.execute(file_path=str(f))
        assert not result.is_error
        assert "..." in result.content
        # Actual content should not exceed the truncation limit significantly
        assert len(result.content) < 3000

    @pytest.mark.asyncio
    async def test_not_a_file_error(self, tool, tmp_path):
        result = await tool.execute(file_path=str(tmp_path))  # directory
        assert result.is_error
        assert "not a file" in result.content.lower()

    @pytest.mark.asyncio
    async def test_line_numbers_match_offset(self, tool, sample_file):
        result = await tool.execute(file_path=str(sample_file), offset=3, limit=3)
        # Should show lines 3, 4, 5 with their actual numbers
        assert "3\t" in result.content or "     3\t" in result.content
        assert "5\t" in result.content or "     5\t" in result.content
