"""
Edit file tool - surgical string replacement.

Performs exact string replacements in files with safety checks,
occurrence validation, and diff generation for transparency.
"""

import difflib
from pathlib import Path

from .base import Tool, ToolError
from .helpers import text_result


class Edit(Tool):
    @property
    def name(self) -> str:
        return "edit"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "edit",
                "description": "Replace exact string in file with new string. old_string must be unique in the file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file to edit",
                        },
                        "old_string": {
                            "type": "string",
                            "description": "Exact text to replace (must be unique in file)",
                        },
                        "new_string": {
                            "type": "string",
                            "description": "Replacement text",
                        },
                        "show_diff": {
                            "type": "boolean",
                            "description": "Include unified diff in response (default: true)",
                        },
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            },
        }

    async def execute(self, input: dict):
        """
        Replace exact string in a file.

        Args:
            file_path: Path to file to edit
            old_string: Exact text to replace (must be unique)
            new_string: Replacement text
            show_diff: Whether to include diff in response (default: true)

        Returns:
            Success message with optional diff

        Raises:
            ToolError: If file not found, string not found, or not unique
        """
        file_path: str | None = input.get("file_path")
        old_string: str | None = input.get("old_string")
        new_string: str | None = input.get("new_string")
        show_diff: bool = input.get("show_diff", True)

        # Validate inputs
        if not file_path:
            raise ToolError("file_path is required")
        if old_string is None:
            raise ToolError("old_string is required")
        if new_string is None:
            raise ToolError("new_string is required")
        if old_string == new_string:
            raise ToolError("old_string and new_string are identical - no changes to make")

        # Resolve and validate path (enforces boundaries if configured)
        path = self.context.resolve_path(file_path)

        # Validate file exists and is readable
        if not path.exists():
            raise ToolError(f"File not found: {file_path}")
        if not path.is_file():
            raise ToolError(f"Not a file: {file_path}")

        # Read current content
        try:
            original_content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ToolError(f"File is not valid UTF-8: {file_path}")
        except PermissionError:
            raise ToolError(f"Permission denied reading file: {file_path}")
        except Exception as e:
            raise ToolError(f"Error reading file: {str(e)}")

        # Check if old_string exists and is unique
        occurrences = original_content.count(old_string)

        if occurrences == 0:
            # Provide helpful error message
            raise ToolError(
                f"old_string not found in {file_path}. "
                f"The exact string must exist in the file. "
                f"Searched for: {self._truncate(old_string, 200)}"
            )

        if occurrences > 1:
            raise ToolError(
                f"old_string appears {occurrences} times in {file_path}. "
                f"For safety, old_string must be unique (appear exactly once). "
                f"Include more context to make it unique."
            )

        # Perform replacement
        new_content = original_content.replace(old_string, new_string)

        # Verify the replacement actually changed something
        if new_content == original_content:
            raise ToolError(
                "Replacement produced no changes. "
                "This should not happen - please report this bug."
            )

        # Write the modified content
        try:
            path.write_text(new_content, encoding="utf-8")
        except PermissionError:
            raise ToolError(f"Permission denied writing file: {file_path}")
        except OSError as e:
            if "No space left" in str(e) or getattr(e, "errno", None) == 28:
                raise ToolError(f"No space left on device: {file_path}")
            raise ToolError(f"Error writing file: {str(e)}")
        except Exception as e:
            raise ToolError(f"Error writing file: {str(e)}")

        # Build response
        response_parts = [f"Successfully replaced 1 occurrence in {file_path}"]

        # Add statistics
        old_lines = len(old_string.splitlines())
        new_lines = len(new_string.splitlines())
        response_parts.append(
            f"Changed {old_lines} line(s) to {new_lines} line(s)"
        )

        # Generate and include diff if requested
        if show_diff:
            diff = self._generate_diff(
                original_content, new_content, file_path
            )
            if diff:
                response_parts.append(f"\nDiff:\n{diff}")

        return text_result("\n".join(response_parts))

    def _generate_diff(
        self, original: str, new: str, filename: str, context_lines: int = 3
    ) -> str:
        """
        Generate unified diff between original and new content.

        Args:
            original: Original file content
            new: New file content
            filename: Name of file (for diff header)
            context_lines: Lines of context around changes (default: 3)

        Returns:
            Unified diff as string, or empty string if no changes
        """
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=context_lines,
        )

        return "".join(diff_lines)

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text for error messages."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
