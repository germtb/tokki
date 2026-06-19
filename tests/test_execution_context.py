"""
Tests for ExecutionContext.
"""

import os
import tempfile
import pytest
from pathlib import Path
from tokki_sdk.tools import ExecutionContext


class TestExecutionContext:
    def test_workspace_dir_as_path(self):
        """Test that workspace_dir can be a Path object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(workspace_dir=Path(tmpdir))
            assert context.workspace_dir == Path(tmpdir)
            assert isinstance(context.workspace_dir, Path)

    def test_workspace_dir_as_string(self):
        """Test that workspace_dir can be a string (regression test)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pass string instead of Path
            context = ExecutionContext(workspace_dir=tmpdir)
            assert context.workspace_dir == Path(tmpdir)
            assert isinstance(context.workspace_dir, Path)

    def test_workspace_dir_defaults_to_cwd(self):
        """Test that workspace_dir defaults to current working directory"""
        context = ExecutionContext()
        assert context.workspace_dir == Path.cwd()
        assert isinstance(context.workspace_dir, Path)

    def test_resolve_path_relative(self):
        """Test resolving relative paths against workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(workspace_dir=tmpdir)
            resolved = context.resolve_path("subdir/file.txt")
            expected = (Path(tmpdir) / "subdir" / "file.txt").resolve()
            assert resolved == expected

    def test_resolve_path_absolute(self):
        """Test resolving absolute paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(workspace_dir=tmpdir)
            abs_path = "/some/absolute/path.txt"
            resolved = context.resolve_path(abs_path)
            assert resolved == Path(abs_path)

    def test_enforce_boundaries_allows_inside(self):
        """Test that enforce_boundaries allows paths inside workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(
                workspace_dir=tmpdir,
                enforce_boundaries=True
            )
            # Should not raise
            resolved = context.resolve_path("subdir/file.txt")
            # Use resolve() to handle symlinks (e.g., /var -> /private/var on macOS)
            assert resolved.resolve().is_relative_to(Path(tmpdir).resolve())

    def test_enforce_boundaries_blocks_outside(self):
        """Test that enforce_boundaries blocks paths outside workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(
                workspace_dir=tmpdir,
                enforce_boundaries=True
            )
            # Try to access parent directory
            with pytest.raises(ValueError) as exc_info:
                context.resolve_path("../outside.txt")
            assert "outside workspace" in str(exc_info.value)

    def test_enforce_boundaries_blocks_absolute_outside(self):
        """Test that enforce_boundaries blocks absolute paths outside workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = ExecutionContext(
                workspace_dir=tmpdir,
                enforce_boundaries=True
            )
            with pytest.raises(ValueError) as exc_info:
                context.resolve_path("/tmp/outside.txt")
            assert "outside workspace" in str(exc_info.value)

    def test_resolve_path_with_string_workspace(self):
        """Test that resolve_path works when workspace_dir was passed as string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pass workspace_dir as string
            context = ExecutionContext(workspace_dir=tmpdir)

            # This should not raise "'str' object has no attribute 'resolve'"
            resolved = context.resolve_path("file.txt")
            expected = (Path(tmpdir) / "file.txt").resolve()
            assert resolved == expected
            assert isinstance(resolved, Path)
