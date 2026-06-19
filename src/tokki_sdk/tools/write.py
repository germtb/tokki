"""
Write file tool (class-based).

Write or append content to a file.
"""

from pathlib import Path

from .base import Tool
from .helpers import text_result


class WriteError(Exception):
    """Raised when file writing fails."""

    pass


class Write(Tool):
    @property
    def name(self) -> str:
        return "write"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "write",
                "description": "Write content to a file (overwrite or append)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["w", "a"],
                            "description": "Write mode: 'w' overwrite, 'a' append",
                        },
                    },
                    "required": ["file_path", "content"],
                },
            },
        }

    async def execute(self, input: dict):
        file_path: str | None = input.get("file_path")
        content: str | None = input.get("content")
        mode: str = input.get("mode", "w")

        if not file_path:
            raise WriteError("file_path cannot be empty")
        if content is None:
            raise WriteError("content is required")
        if mode not in ("w", "a"):
            raise WriteError(f"Invalid mode '{mode}': must be 'w' or 'a'")

        # Resolve and validate path (enforces boundaries if configured)
        path = self.context.resolve_path(file_path)

        parent_dir = path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise WriteError(f"Failed to create parent directory: {str(e)}")

        try:
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            file_size = path.stat().st_size
            action = "Written" if mode == "w" else "Appended to"
            return text_result(f"{action} {file_size} bytes to {file_path}")
        except Exception as e:
            raise WriteError(f"Error writing file {file_path}: {str(e)}")
