"""
Tools for building coding assistant agents.

This module provides file operations, search, and command execution
utilities similar to Claude Code, enabling agents to interact with
codebases effectively.

With session-based isolation, all operations are safe - each session
runs in its own isolated container with its own filesystem.

## Basic Usage

```python
from tokki_sdk.tools import read, write, grep, glob, bash

# Read a file
content = read("/workspace/src/main.py")

# Write a file
write("/workspace/output.txt", "Hello, world!")

# Search for patterns
files = grep("TODO", output_mode="files_with_matches")

# Find files by pattern
python_files = glob("**/*.py")

# Execute bash commands (unrestricted in isolated container)
output = bash("git clone https://github.com/user/repo")
```

## With LLM Tool Use

```python
from anthropic import Anthropic
from tokki_sdk.tools.parsers import parse_anthropic_tools, format_anthropic_tool_result
from tokki_sdk.tools import execute_tools

client = Anthropic()

# Define tools for Claude
tools = [...tool definitions...]

# Get response with tool use
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Read main.py"}],
    tools=tools,
)

# Parse and execute tool calls
tool_calls = parse_anthropic_tools(message)
results = execute_tools(tool_calls)

# Format results to send back
tool_results = [
    format_anthropic_tool_result(
        tool_call_id=r.tool_call.id,
        output=r.output,
        is_error=not r.success,
    )
    for r in results
]
```
"""

from .executor import ToolExecutor
from .read import Read
from .write import Write
from .edit import Edit
from .glob import Glob
from .grep import Grep
from .bash import Bash
from .pdf import PdfTool
from .database import Database
from .memory import Memory
from .agent_hub import AgentHubDiscoveryTool, AgentHubSendTool
from .mcp import McpTool
from .integrations import IntegrationsTool
from .context import ExecutionContext
from .helpers import text_result, error_result

__all__ = [
    # Class-based tools
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "PdfTool",
    "Database",
    "Memory",
    "AgentHubDiscoveryTool",
    "AgentHubSendTool",
    "McpTool",
    "IntegrationsTool",
    # Tool execution
    "ToolExecutor",
    "ExecutionContext",
    # Helpers
    "text_result",
    "error_result",
]
