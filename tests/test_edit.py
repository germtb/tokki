"""
Tests for Edit tool.
"""

import os
import tempfile
import pytest
from pathlib import Path
from tokki_sdk.tools import Edit, ExecutionContext
from tokki_sdk.tools.base import ToolError


def _text(result) -> str:
    """Extract text from a ToolResult."""
    return result.nodes[0].text.text if result.nodes else ""


class TestEdit:
    @pytest.mark.asyncio
    async def test_simple_replacement(self):
        """Test basic string replacement in a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("Hello world\nThis is a test\n")

            # Create context and tool
            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            # Replace text
            result = await edit.execute({
                "file_path": test_file,
                "old_string": "Hello world",
                "new_string": "Hello universe",
                "show_diff": False,
            })

            # Verify result
            text = _text(result)
            assert "Successfully replaced 1 occurrence" in text
            assert "test.txt" in text

            # Verify file was updated
            content = Path(test_file).read_text()
            assert "Hello universe" in content
            assert "Hello world" not in content

    @pytest.mark.asyncio
    async def test_multiline_replacement(self):
        """Test replacing multiple lines"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "code.py")
            original = "def foo():\n    pass\n\nprint('hello')\n"
            Path(test_file).write_text(original)

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            # Replace function
            result = await edit.execute({
                "file_path": test_file,
                "old_string": "def foo():\n    pass",
                "new_string": "def foo():\n    return 42",
                "show_diff": False,
            })

            assert "Successfully replaced" in _text(result)

            content = Path(test_file).read_text()
            assert "return 42" in content
            assert "pass" not in content

    @pytest.mark.asyncio
    async def test_string_not_found(self):
        """Test error when old_string doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("Hello world\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            with pytest.raises(ToolError) as exc_info:
                await edit.execute({
                    "file_path": test_file,
                    "old_string": "Goodbye world",
                    "new_string": "Hello universe",
                })

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_string_not_unique(self):
        """Test error when old_string appears multiple times"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("foo\nbar\nfoo\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            with pytest.raises(ToolError) as exc_info:
                await edit.execute({
                    "file_path": test_file,
                    "old_string": "foo",
                    "new_string": "baz",
                })

            assert "2 times" in str(exc_info.value)
            assert "unique" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test error when file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            with pytest.raises(ToolError) as exc_info:
                await edit.execute({
                    "file_path": os.path.join(tmpdir, "nonexistent.txt"),
                    "old_string": "foo",
                    "new_string": "bar",
                })

            assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_identical_strings(self):
        """Test error when old_string and new_string are identical"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("Hello world\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            with pytest.raises(ToolError) as exc_info:
                await edit.execute({
                    "file_path": test_file,
                    "old_string": "Hello",
                    "new_string": "Hello",
                })

            assert "identical" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_diff_generation(self):
        """Test that diff is generated and included in response"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("line 1\nline 2\nline 3\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            result = await edit.execute({
                "file_path": test_file,
                "old_string": "line 2",
                "new_string": "modified line 2",
                "show_diff": True,
            })

            # Should include diff
            text = _text(result)
            assert "Diff:" in text
            assert "@@" in text  # Unified diff markers
            assert "-line 2" in text
            assert "+modified line 2" in text

    @pytest.mark.asyncio
    async def test_diff_disabled(self):
        """Test that diff can be disabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("Hello world\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            result = await edit.execute({
                "file_path": test_file,
                "old_string": "Hello",
                "new_string": "Hi",
                "show_diff": False,
            })

            # Should not include diff
            text = _text(result)
            assert "Diff:" not in text
            assert "@@" not in text

    @pytest.mark.asyncio
    async def test_relative_path_resolution(self):
        """Test that relative paths are resolved against workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "subdir", "test.txt")
            os.makedirs(os.path.dirname(test_file))
            Path(test_file).write_text("Hello world\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            # Use relative path
            result = await edit.execute({
                "file_path": "subdir/test.txt",
                "old_string": "Hello",
                "new_string": "Hi",
                "show_diff": False,
            })

            assert "Successfully replaced" in _text(result)

            # Verify file was updated
            content = Path(test_file).read_text()
            assert "Hi world" in content

    @pytest.mark.asyncio
    async def test_preserves_other_content(self):
        """Test that only the target string is replaced"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            original = "line 1\ntarget\nline 3\nline 4\n"
            Path(test_file).write_text(original)

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            await edit.execute({
                "file_path": test_file,
                "old_string": "target",
                "new_string": "replaced",
                "show_diff": False,
            })

            content = Path(test_file).read_text()
            assert "line 1" in content
            assert "line 3" in content
            assert "line 4" in content
            assert "replaced" in content

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test editing content with special characters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("$variable = 'hello'\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            result = await edit.execute({
                "file_path": test_file,
                "old_string": "$variable = 'hello'",
                "new_string": "$variable = 'world'",
                "show_diff": False,
            })

            assert "Successfully replaced" in _text(result)

            content = Path(test_file).read_text()
            assert "$variable = 'world'" in content

    @pytest.mark.asyncio
    async def test_empty_new_string(self):
        """Test replacing with empty string (deletion)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("before\nmiddle\nafter\n")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            result = await edit.execute({
                "file_path": test_file,
                "old_string": "middle\n",
                "new_string": "",
                "show_diff": False,
            })

            assert "Successfully replaced" in _text(result)

            content = Path(test_file).read_text()
            assert "before\nafter\n" == content

    @pytest.mark.asyncio
    async def test_line_count_statistics(self):
        """Test that line count statistics are included"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).write_text("single line")

            context = ExecutionContext(workspace_dir=Path(tmpdir))
            edit = Edit(context)

            result = await edit.execute({
                "file_path": test_file,
                "old_string": "single line",
                "new_string": "line 1\nline 2\nline 3",
                "show_diff": False,
            })

            assert "1 line(s) to 3 line(s)" in _text(result)

    @pytest.mark.asyncio
    async def test_enforce_boundaries(self):
        """Test that enforce_boundaries prevents escaping workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file outside workspace
            outside_file = os.path.join(tempfile.gettempdir(), "outside.txt")
            Path(outside_file).write_text("test")

            try:
                # Create context with enforce_boundaries
                context = ExecutionContext(
                    workspace_dir=Path(tmpdir),
                    enforce_boundaries=True
                )
                edit = Edit(context)

                # Try to edit file outside workspace
                with pytest.raises(ValueError) as exc_info:
                    await edit.execute({
                        "file_path": outside_file,
                        "old_string": "test",
                        "new_string": "modified",
                    })

                assert "outside workspace" in str(exc_info.value)
            finally:
                # Cleanup
                if os.path.exists(outside_file):
                    os.remove(outside_file)
