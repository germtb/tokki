"""
Tests for Bash tool workspace directory via ExecutionContext.
"""

import os
import tempfile
import pytest
from pathlib import Path
from tokki_sdk.tools import Bash, ExecutionContext


def _text(result) -> str:
    """Extract text from a ToolResult."""
    return result.nodes[0].text.text if result.nodes else ""


class TestBashWorkspace:
    @pytest.mark.asyncio
    async def test_uses_workspace_from_context(self):
        """Test that Bash tool uses workspace from ExecutionContext"""
        # Create a temporary directory with a workspace subdirectory
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = os.path.join(tmpdir, "workspace")
            os.makedirs(workspace_dir)

            # Create a test file in the workspace
            test_file = os.path.join(workspace_dir, "test.txt")
            Path(test_file).write_text("workspace test")

            # Create ExecutionContext with workspace
            context = ExecutionContext(workspace_dir=Path(workspace_dir))
            bash = Bash(context)

            # Execute a command that should run in workspace
            result = await bash.execute({"command": "pwd"})

            # Should be in the workspace directory (handle symlinks like /var -> /private/var)
            assert Path(_text(result).strip()).resolve() == Path(workspace_dir).resolve()

            # Verify we can access files in workspace
            result = await bash.execute({"command": "cat test.txt"})
            assert "workspace test" in _text(result)

    @pytest.mark.asyncio
    async def test_uses_cwd_when_no_explicit_workspace(self):
        """Test that Bash tool uses cwd when ExecutionContext has no explicit workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create context without explicit workspace (will use cwd)
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                context = ExecutionContext()  # No workspace_dir specified
                bash = Bash(context)

                # Should use current directory (tmpdir)
                result = await bash.execute({"command": "pwd"})
                assert tmpdir in _text(result)

            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_explicit_cwd_overrides_workspace(self):
        """Test that explicit cwd parameter overrides workspace from context"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = os.path.join(tmpdir, "workspace")
            custom_dir = os.path.join(tmpdir, "custom")
            os.makedirs(workspace_dir)
            os.makedirs(custom_dir)

            # Create context with workspace
            context = ExecutionContext(workspace_dir=Path(workspace_dir))
            bash = Bash(context)

            # Use explicit cwd - should override workspace
            result = await bash.execute({"command": "pwd", "cwd": custom_dir})

            assert "custom" in _text(result)
            assert "workspace" not in _text(result)

    @pytest.mark.asyncio
    async def test_creates_workspace_if_not_exists(self):
        """Test that workspace directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = os.path.join(tmpdir, "workspace")
            # Don't create workspace initially

            # Create context with non-existent workspace
            context = ExecutionContext(workspace_dir=Path(workspace_dir))
            bash = Bash(context)

            # Execute command - should create workspace and run there
            result = await bash.execute({"command": "pwd"})

            # Should have created and used the workspace directory
            assert workspace_dir in _text(result)
            assert os.path.exists(workspace_dir)
