"""
End-to-end tests for the Toolcall agent with a real LLM (Kimi).

Requires MOONSHOT_API_KEY environment variable.
Run with: uv run pytest tests/test_toolcall_e2e.py -v
"""

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from tokki_sdk import Context, Role, Status
from tokki_sdk.tokki_pb2 import ContentNode
from tokki_sdk.agents.toolcall import Toolcall
from tokki_sdk.vendor import Kimi

# Skip all tests in this module if no API key
pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("MOONSHOT_API_KEY"),
        reason="MOONSHOT_API_KEY not set",
    ),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]


def _make_agent(workspace: Path, max_iterations: int = 5) -> Toolcall:
    vendor = Kimi(api_key=os.environ["MOONSHOT_API_KEY"])
    agent = Toolcall(
        model="moonshot-v1-auto",
        summarisation_model="moonshot-v1-8k",
        vendor=vendor,
        max_iterations=max_iterations,
    )
    agent.execution_context._workspace_dir = workspace
    return agent


def _make_context(**kwargs) -> Context:
    return Context(
        conversation_id="test",
        messages=[],
        request_id=str(uuid4()),
        **kwargs,
    )


def _assistant_text(ctx: Context) -> str:
    """Extract all assistant text from the context."""
    parts = []
    for msg in ctx.messages:
        if msg.role == Role.ASSISTANT:
            for node in msg.content:
                if node.HasField("text") or node.text:
                    parts.append(node.text)
    return "\n".join(parts)


def _has_tool_call(ctx: Context, tool_name: str) -> bool:
    """Check if any assistant message contains a tool call with the given name."""
    for msg in ctx.messages:
        if msg.role == Role.ASSISTANT:
            for node in msg.content:
                if node.HasField("tool_call") and node.tool_call.tool == tool_name:
                    return True
    return False


def _has_any_tool_call(ctx: Context) -> bool:
    """Check if any tool was called."""
    for msg in ctx.messages:
        if msg.role == Role.ASSISTANT:
            for node in msg.content:
                if node.HasField("tool_call"):
                    return True
    return False


class TestToolcallE2E:
    """End-to-end tests that run the Toolcall agent against a real LLM."""

    @pytest.mark.integration
    async def test_simple_question(self):
        """Agent answers a factual question without needing tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=2)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="What is 2+2? Reply with just the number.")],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            text = _assistant_text(ctx)
            assert "4" in text

    @pytest.mark.integration
    async def test_bash_tool(self):
        """Agent uses the bash tool to run a command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Use the bash tool to run `echo hello_tokki` and tell me the output.")],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "bash")
            text = _assistant_text(ctx)
            assert "hello_tokki" in text

    @pytest.mark.integration
    async def test_write_and_read(self):
        """Agent writes a file then reads it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[
                    ContentNode(
                        text=(
                            "Write the text 'avocado_test_123' to a file called test.txt, "
                            "then read it back and tell me its contents."
                        )
                    )
                ],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert (workspace / "test.txt").exists()
            assert "avocado_test_123" in (workspace / "test.txt").read_text()

    @pytest.mark.integration
    async def test_glob_tool(self):
        """Agent uses glob to find files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            (workspace / "foo.py").write_text("print('foo')")
            (workspace / "bar.py").write_text("print('bar')")
            (workspace / "readme.md").write_text("# readme")

            agent = _make_agent(workspace)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Use the glob tool to find all .py files. What .py files exist?")],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "glob")
            text = _assistant_text(ctx)
            assert "foo.py" in text
            assert "bar.py" in text

    @pytest.mark.integration
    async def test_grep_tool(self):
        """Agent uses grep to search file contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            (workspace / "data.txt").write_text("line1\nfind_me_token\nline3\n")

            agent = _make_agent(workspace)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Use the grep tool to search for the pattern 'find_me_token' in data.txt.")],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "grep")
            text = _assistant_text(ctx)
            assert "find_me_token" in text

    @pytest.mark.integration
    async def test_multi_turn(self):
        """Agent handles a follow-up message in the same context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=3)
            ctx = _make_context()

            # Turn 1
            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Write 'hello' to greet.txt")],
            )
            await agent.run(ctx)
            assert (workspace / "greet.txt").exists()

            # Turn 2 — same context, new user message
            ctx.status = Status.INIT
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Now read greet.txt and tell me what it says.")],
            )
            await agent.run(ctx)

            text = _assistant_text(ctx)
            assert "hello" in text

    @pytest.mark.integration
    async def test_max_iterations_respected(self):
        """Agent stops after hitting max_iterations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=1)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[
                    ContentNode(
                        text=(
                            "Create files a.txt, b.txt, c.txt, d.txt, e.txt "
                            "each containing their letter. Do them one at a time."
                        )
                    )
                ],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            # With max_iterations=1, the agent gets at most 1 tool-calling round
            created = [f.name for f in workspace.iterdir()]
            assert len(created) < 5

    @pytest.mark.integration
    async def test_mcp_tools_graceful_without_server(self):
        """MCP tools fail gracefully when no server is running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=2)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Use the discover_personas tool to list available personas.")],
            )

            await agent.run(ctx)

            # Agent should complete (not crash) even without MCP server
            assert ctx.status == Status.COMPLETED
            text = _assistant_text(ctx)
            assert len(text) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("TOKKI_MCP_URL"),
        reason="TOKKI_MCP_URL not set (requires running server)",
    )
    async def test_discover_personas(self):
        """Agent uses discover_personas to list available personas from the server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=3)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[ContentNode(text="Use the discover_personas tool to list all available personas. Report what you find.")],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "discover_personas")
            text = _assistant_text(ctx)
            assert len(text) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("TOKKI_MCP_URL"),
        reason="TOKKI_MCP_URL not set (requires running server)",
    )
    async def test_integrations_list(self):
        """Agent uses the integrations tool to discover available integration tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=3)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[
                    ContentNode(
                        text=(
                            "Use the integrations tool with action 'list' to discover "
                            "what integration tools are available. Report what you find."
                        )
                    )
                ],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "integrations")
            text = _assistant_text(ctx)
            # Should find TrueLayer banking tools
            assert "list_bank_accounts" in text or "bank" in text.lower()

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("TOKKI_MCP_URL"),
        reason="TOKKI_MCP_URL not set (requires running server)",
    )
    async def test_integrations_openbanking(self):
        """Agent uses list → load → call workflow to access banking tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=7)
            ctx = _make_context()

            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[
                    ContentNode(
                        text=(
                            "I want to see my bank accounts. Use the integrations tool: "
                            "first action='list' to discover tools, "
                            "then action='load' with tool_name='list_bank_accounts' to learn its schema, "
                            "then action='call' with tool_name='list_bank_accounts' to execute it. "
                            "Report what you find."
                        )
                    )
                ],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "integrations")
            text = _assistant_text(ctx)
            assert len(text) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("TOKKI_MCP_URL"),
        reason="TOKKI_MCP_URL not set (requires running server)",
    )
    async def test_send_message(self):
        """Agent uses send_message to communicate with another persona."""
        # Requires at least one published persona to send to.
        # The agent should call send_message and get a response back.
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            agent = _make_agent(workspace, max_iterations=5)
            ctx = _make_context()

            # First discover, then send — gives the LLM a real target
            await agent.init(ctx)
            ctx.upsert_message_from_input(
                role=Role.USER,
                content=[
                    ContentNode(
                        text=(
                            "First use the discover_personas tool to find available personas. "
                            "Then use the send_message tool to send the message 'hello' to the first persona you find. "
                            "Report the response you get back."
                        )
                    )
                ],
            )

            await agent.run(ctx)

            assert ctx.status == Status.COMPLETED
            assert _has_tool_call(ctx, "discover_personas")
            assert _has_tool_call(ctx, "send_message")
