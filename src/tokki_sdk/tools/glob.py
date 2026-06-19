"""
Glob file search tool (class-based).

Find files matching a glob pattern, returning file paths sorted by
modification time (most recent first).
"""

import re
from pathlib import Path

from .base import Tool, ToolError
from .helpers import text_result
from .accent_utils import remove_accents


class Glob(Tool):
    @property
    def name(self) -> str:
        return "glob"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "glob",
                "description": "Find files matching a glob pattern",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern (e.g., '**/*.py')",
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search (default: CWD)",
                        },
                        "accent_insensitive": {
                            "type": "boolean",
                            "description": "Match files ignoring accents (café matches cafe)",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        }

    async def execute(self, input: dict):
        pattern: str | None = input.get("pattern")
        path: str | None = input.get("path")
        accent_insensitive: bool = bool(input.get("accent_insensitive", False))

        if not pattern:
            raise ToolError("pattern is required")

        # Use context workspace if available, otherwise fall back to cwd
        if path:
            search_path = Path(path)
        else:
            search_path = self.context.workspace_dir

        if not search_path.exists():
            raise ToolError(f"Directory not found: {search_path}")
        if not search_path.is_dir():
            raise ToolError(f"Not a directory: {search_path}")

        try:
            if accent_insensitive:
                # Get all files and filter manually with accent-insensitive matching
                all_files = list(
                    search_path.rglob("*") if "**" in pattern else search_path.glob("*")
                )
                all_files = [p for p in all_files if p.is_file()]

                # Convert glob pattern to regex, removing accents from both pattern and filenames
                # Simplified: just match by normalized names
                normalized_pattern = remove_accents(pattern)
                # Convert glob wildcards to regex
                regex_pattern = (
                    normalized_pattern.replace("**", ".*")
                    .replace("*", "[^/]*")
                    .replace("?", ".")
                )
                regex = re.compile(regex_pattern, re.IGNORECASE)

                files = []
                for file_path in all_files:
                    # Normalize the relative path for matching
                    rel_path = str(file_path.relative_to(search_path))
                    normalized_rel = remove_accents(rel_path)
                    if regex.search(normalized_rel):
                        files.append(file_path)
            else:
                # Standard glob matching
                matches = list(search_path.glob(pattern))
                files = [p for p in matches if p.is_file()]

            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return text_result("\n".join(str(f) for f in files) if files else "")
        except Exception as e:
            raise ToolError(f"Glob pattern matching failed: {str(e)}")
