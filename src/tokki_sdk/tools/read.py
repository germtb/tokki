import os
from pathlib import Path

from .base import Tool, ToolError
from .helpers import text_result


class Read(Tool):
    @property
    def name(self) -> str:
        return "read"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "read",
                "description": "Read file contents with optional line range",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to read",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Line number to start reading from (1-indexed)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of lines to read",
                        },
                    },
                    "required": ["file_path"],
                },
            },
        }

    async def execute(self, input: dict):
        """
        Read file contents with optional line range.

        Similar to Claude Code's Read tool - reads files and returns contents
        with line numbers in `cat -n` format.

        Args:
            file_path: Absolute path to the file to read
            offset: Line number to start reading from (1-indexed, inclusive)
            limit: Number of lines to read from offset

        Returns:
            File contents with line numbers in format "  LINE→content"

        Raises:
            ToolError: If file cannot be read (not found, permission denied, etc.)

        Examples:
            >>> # Read entire file
            >>> content = read("/path/to/file.py")

            >>> # Read lines 10-20
            >>> content = read("/path/to/file.py", offset=10, limit=10)

            >>> # Read first 100 lines
            >>> content = read("/path/to/file.py", limit=100)
        """

        file_path: str | None = input.get("file_path", None)
        offset: int | None = input.get("offset", None)
        limit: int | None = input.get("limit", None)

        # Validate file_path
        if not file_path:
            raise ToolError("file_path cannot be empty")

        # Resolve and validate path (enforces boundaries if configured)
        path = self.context.resolve_path(file_path)

        # Check if file exists
        if not path.exists():
            raise ToolError(f"File not found: {file_path}")

        # Check if it's a file (not a directory)
        if not path.is_file():
            raise ToolError(f"Not a file: {file_path}")

        # Check if we have read permissions
        if not os.access(path, os.R_OK):
            raise ToolError(f"Permission denied: {file_path}")

        try:
            # Read the file
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # Apply offset and limit
            total_lines = len(lines)

            # Determine start and end indices
            if offset is not None:
                if offset < 1:
                    raise ToolError("offset must be >= 1 (1-indexed)")
                start_idx = offset - 1  # Convert to 0-indexed
            else:
                start_idx = 0

            if limit is not None:
                if limit < 1:
                    raise ToolError("limit must be >= 1")
                end_idx = start_idx + limit
            else:
                end_idx = total_lines

            # Check if offset is beyond file length
            if start_idx >= total_lines:
                raise ToolError(
                    f"offset {offset} is beyond file length ({total_lines} lines)"
                )

            # Slice the lines
            selected_lines = lines[start_idx:end_idx]

            # Format with line numbers (cat -n style)
            # Line numbers start from 1 or offset
            formatted_lines = []
            for i, line in enumerate(selected_lines):
                line_num = start_idx + i + 1
                # Remove trailing newline if present for formatting
                line_content = line.rstrip("\n")
                # Format: "  LINE→content"
                formatted_lines.append(f"{line_num:6}→{line_content}")

            return text_result("\n".join(formatted_lines))

        except UnicodeDecodeError:
            raise ToolError(f"File is not valid UTF-8: {file_path}")
        except Exception as e:
            raise ToolError(f"Error reading file {file_path}: {str(e)}")
