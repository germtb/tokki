"""
Grep content search tool (class-based).

Search for patterns in file contents using ripgrep.
"""

import subprocess
from typing import Optional

from .base import Tool, ToolError
from .helpers import text_result
from .accent_utils import make_pattern_accent_insensitive


class Grep(Tool):
    @property
    def name(self) -> str:
        return "grep"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "Search for patterns in files using ripgrep",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern"},
                        "path": {
                            "type": "string",
                            "description": "File or directory to search",
                        },
                        "glob_pattern": {
                            "type": "string",
                            "description": "Glob filter (e.g., '*.py')",
                        },
                        "file_type": {
                            "type": "string",
                            "description": "ripgrep --type (e.g., 'py')",
                        },
                        "output_mode": {
                            "type": "string",
                            "enum": ["content", "files_with_matches", "count"],
                            "description": "Output format",
                        },
                        "case_insensitive": {
                            "type": "boolean",
                            "description": "Case insensitive",
                        },
                        "accent_insensitive": {
                            "type": "boolean",
                            "description": "Accent insensitive (matches café with cafe)",
                        },
                        "context_before": {
                            "type": "integer",
                            "description": "Lines before (content mode)",
                        },
                        "context_after": {
                            "type": "integer",
                            "description": "Lines after (content mode)",
                        },
                        "line_numbers": {
                            "type": "boolean",
                            "description": "Show line numbers (content mode)",
                        },
                        "multiline": {
                            "type": "boolean",
                            "description": "Enable multiline dotall",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        }

    async def execute(self, input: dict):
        pattern: Optional[str] = input.get("pattern")
        if not pattern:
            raise ToolError("pattern is required")

        path: Optional[str] = input.get("path")
        glob_pattern: Optional[str] = input.get("glob_pattern")
        file_type: Optional[str] = input.get("file_type")
        output_mode: str = input.get("output_mode", "files_with_matches")
        case_insensitive: bool = bool(input.get("case_insensitive", False))
        accent_insensitive: bool = bool(input.get("accent_insensitive", False))
        context_before: int = int(input.get("context_before", 0))
        context_after: int = int(input.get("context_after", 0))
        line_numbers: bool = bool(input.get("line_numbers", True))
        multiline: bool = bool(input.get("multiline", False))

        # Expand pattern for accent-insensitive matching
        if accent_insensitive:
            pattern, _ = make_pattern_accent_insensitive(pattern, method="expand")

        # Check ripgrep availability
        try:
            subprocess.run(["rg", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ToolError(
                "ripgrep (rg) not found. Install it: https://github.com/BurntSushi/ripgrep"
            )

        cmd = ["rg", pattern]

        if output_mode == "files_with_matches":
            cmd.append("--files-with-matches")
        elif output_mode == "count":
            cmd.append("--count")
        # content mode: default

        if case_insensitive:
            cmd.append("-i")

        if output_mode == "content":
            if context_before > 0:
                cmd.extend(["-B", str(context_before)])
            if context_after > 0:
                cmd.extend(["-A", str(context_after)])
            if line_numbers:
                cmd.append("-n")

        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])

        if glob_pattern:
            cmd.extend(["--glob", glob_pattern])
        if file_type:
            cmd.extend(["--type", file_type])
        if path:
            cmd.append(path)

        cwd = str(self.context.workspace_dir)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            if result.returncode in (0, 1):
                return text_result(result.stdout.strip())
            raise ToolError(f"ripgrep failed: {result.stderr}")
        except FileNotFoundError:
            raise ToolError("ripgrep (rg) not found in PATH")
        except Exception as e:
            raise ToolError(f"Search failed: {str(e)}")
