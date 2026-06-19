"""
Bash command execution tool (class-based).

With session-based isolation, each session gets its own ephemeral container,
so commands can safely execute without restrictions. Files persist within a
session but are isolated from other sessions.
"""

import os
import subprocess

from .base import Tool, ToolError
from .helpers import text_result


class Bash(Tool):
    @property
    def name(self) -> str:
        return "bash"

    @property
    def allow_a2a(self) -> bool:
        return False

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command and return output",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash command to execute",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory",
                        },
                    },
                    "required": ["command"],
                },
            },
        }

    async def execute(self, input: dict):
        """
        Execute a bash command and return output.

        Args:
            command: Bash command to execute
            timeout: Timeout in seconds (default: 120)
            cwd: Working directory

        Returns:
            Command output (stdout + stderr combined)

        Raises:
            BashError: If command execution fails
        """

        command: str | None = input.get("command")
        timeout: int = int(input.get("timeout", 120))
        cwd: str = input.get("cwd") or str(self.context.workspace_dir)

        if not command or not command.strip():
            raise ToolError("Command cannot be empty")

        if not os.path.isdir(cwd):
            try:
                os.makedirs(cwd, exist_ok=True)
            except Exception:
                raise ToolError(f"Working directory does not exist: {cwd}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

            # Combine stdout and stderr for full output
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout.strip())
            if result.stderr:
                output_parts.append(f"[stderr]:\n{result.stderr.strip()}")

            full_output = "\n\n".join(output_parts) if output_parts else ""

            # Check return code to determine success/failure
            if result.returncode != 0:
                # Command failed - raise error with full output
                raise ToolError(full_output)

            # Command succeeded - return full output
            return text_result(full_output)

        except subprocess.TimeoutExpired:
            raise ToolError(f"Command timed out after {timeout} seconds")
        except Exception as e:
            raise ToolError(f"Command execution failed: {str(e)}")
