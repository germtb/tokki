"""
Execution context for tools.

Provides a shared context for maintaining consistency across tool executions,
particularly for working directory management.
"""

from pathlib import Path

from tokki_sdk.tools.memory import MessageStore


class ExecutionContext:
    """
    Shared execution context for tools.

    Provides a consistent working directory and path resolution across
    all tool executions.
    """

    def __init__(
        self,
        workspace_dir: Path | str | None = None,
        enforce_boundaries: bool = False,
        files_base_url: str | None = None,
    ):
        """
        Initialize execution context.

        Args:
            workspace_dir: Base working directory for tools. Defaults to cwd.
            enforce_boundaries: If True, validate that paths stay within workspace.
            files_base_url: Base URL for file resources (e.g., "http://localhost:8080/files/{namespace}/{agentId}").
                           Used to construct full URLs for files in tool results.
        """
        if workspace_dir is None:
            self._workspace_dir = Path.cwd()
        elif isinstance(workspace_dir, Path):
            self._workspace_dir = workspace_dir
        else:
            self._workspace_dir = Path(workspace_dir)

        self.enforce_boundaries = enforce_boundaries
        self.files_base_url = files_base_url
        self.message_store = MessageStore(str(self._workspace_dir))

    @property
    def workspace_dir(self) -> Path:
        """The base working directory for all tools."""
        return self._workspace_dir

    def resolve_path(self, path: str | Path) -> Path:
        """
        Resolve a path against the workspace directory.

        Args:
            path: Path to resolve (can be relative or absolute)

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If enforce_boundaries is True and path is outside workspace
        """
        p = Path(path)

        # If absolute, use as-is; otherwise resolve against workspace
        if p.is_absolute():
            resolved = p
        else:
            resolved = (self._workspace_dir / p).resolve()

        # Optionally validate workspace boundaries
        if self.enforce_boundaries and not self._is_within_workspace(resolved):
            raise ValueError(
                f"Path {resolved} is outside workspace {self._workspace_dir}"
            )

        return resolved

    def _is_within_workspace(self, path: Path) -> bool:
        """Check if path is within workspace boundaries."""
        try:
            resolved = path.resolve()
            workspace = self._workspace_dir.resolve()
            return resolved.is_relative_to(workspace)
        except (ValueError, OSError):
            return False
