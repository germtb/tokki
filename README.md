# Tokki

Tokki is a protocol and library I designed to make it easier to create and
design agents. Most other frameworks express agents as configuration, but I
often find myself wanting to express agents as code where I can control every
part of the loop.

## Features

- Async gRPC service for Tokki agents
- Protobuf types exported from `tokki_sdk`
- LLM vendor adapters for Kimi, Mistral, Anthropic, and Ollama
- Tool runtime with file, shell, grep, glob, memory, database, PDF, MCP, and
  agent-to-agent helper tools
- SQLite-backed conversation archive
- Optional workspace boundary enforcement for file tools

## Installation

```bash
pip install tokki-sdk
```

For local development:

```bash
uv sync --group dev
uv run pytest
./typecheck
```

Optional extras:

```bash
pip install "tokki-sdk[pdf]"
pip install "tokki-sdk[langchain]"
```

## Minimal Agent

```python
from tokki_sdk import Agent, Context, Role, Status
from tokki_sdk.tokki_pb2 import ContentNode


class EchoAgent(Agent):
    async def init(self, context: Context) -> bool:
        context.upsert_message_from_input(
            role=Role.SYSTEM,
            content=[ContentNode(text="You are a concise assistant.")],
        )
        return True

    async def run(self, context: Context) -> None:
        context.update_status(Status.STREAMING)
        context.upsert_message_from_input(
            role=Role.ASSISTANT,
            content=[ContentNode(text="Hello from Tokki.")],
        )
        context.update_status(Status.COMPLETED)
```

## Tool-Calling Agent

`tokki_sdk.agents.toolcall.Toolcall` implements a ReACT-style agent loop with LLM
tool calls:

```python
import os

from tokki_sdk.agents.toolcall import Toolcall
from tokki_sdk.vendor import Kimi


agent = Toolcall(
    model="moonshot-v1-auto",
    summarisation_model="moonshot-v1-8k",
    vendor=Kimi(api_key=os.environ["MOONSHOT_API_KEY"]),
)
```

The built-in tool-calling agent uses `workspace/` as its working directory and
enforces file path boundaries for file tools.

## Security Model

Tokki SDK agents are meant to run in a sandboxed environment, unless you avoid
bash tool and internet usage.

## Workspace Pattern

Agents can use a `workspace/` directory for command execution, temporary files,
generated outputs, and conversation archives. See
[`docs/WORKSPACE.md`](docs/WORKSPACE.md) for details.

## Development

Run tests:

```bash
uv run pytest
```

Run type checks:

```bash
./typecheck
```

Integration tests that call real LLM or MCP services are skipped unless the
required environment variables are set.

## License

MIT. See [`LICENSE`](LICENSE).
