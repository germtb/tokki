"""Tests for to_openai_messages conversion."""

from tokki_sdk.vendor.base import to_openai_messages
from tokki_sdk.tokki_pb2 import (
    Message,
    ContentNode,
    Role,
    ToolCall,
    ToolResponse,
    ToolResultContent,
    ToolResultContentNode,
    TextContent,
)


def _make_tool_call_msg(call_id: str, tool: str, input: str) -> Message:
    return Message(
        role=Role.ASSISTANT,
        id=f"assistant-{call_id}",
        timestamp_ms=1000,
        content=[
            ContentNode(
                tool_call=ToolCall(call_id=call_id, tool=tool, input=input)
            )
        ],
    )


def _make_tool_response_msg(call_id: str, tool: str, text: str) -> Message:
    return Message(
        role=Role.TOOL,
        id=f"tool-{call_id}",
        timestamp_ms=2000,
        content=[
            ContentNode(
                tool_response=ToolResponse(
                    call_id=call_id,
                    tool=tool,
                    content=ToolResultContent(
                        nodes=[ToolResultContentNode(text=TextContent(text=text))]
                    ),
                )
            )
        ],
    )


def test_basic_tool_call_response_pair():
    """Normal case: tool_call followed by tool_response."""
    messages = [
        Message(role=Role.USER, id="u1", timestamp_ms=100, content=[ContentNode(text="hello")]),
        _make_tool_call_msg("call-1", "bash", '{"command": "ls"}'),
        _make_tool_response_msg("call-1", "bash", "file1.txt\nfile2.txt"),
    ]
    result = to_openai_messages(messages)
    assert result[0] == {"role": "user", "content": "hello"}
    assert result[1]["role"] == "assistant"
    assert result[1]["tool_calls"][0]["id"] == "call-1"
    assert result[2]["role"] == "tool"
    assert result[2]["tool_call_id"] == "call-1"
    assert "file1.txt" in result[2]["content"]


def test_orphaned_tool_call_gets_synthetic_response():
    """Tool_call with no matching tool_response gets a synthetic response."""
    messages = [
        Message(role=Role.USER, id="u1", timestamp_ms=100, content=[ContentNode(text="hello")]),
        _make_tool_call_msg("orphan-1", "AgentComm", '{"action": "send"}'),
        Message(role=Role.USER, id="u2", timestamp_ms=3000, content=[ContentNode(text="next message")]),
    ]
    result = to_openai_messages(messages)
    # Should have: user, assistant(tool_call), user, synthetic tool response (appended at end)
    assert len(result) == 4
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"
    assert result[1]["tool_calls"][0]["id"] == "orphan-1"
    assert result[2]["role"] == "user"
    # Synthetic response appended at end
    assert result[3]["role"] == "tool"
    assert result[3]["tool_call_id"] == "orphan-1"
    assert result[3]["name"] == "AgentComm"


def test_deferred_tool_response():
    """Tool_response that appears BEFORE its tool_call is deferred correctly."""
    messages = [
        Message(role=Role.USER, id="u1", timestamp_ms=100, content=[ContentNode(text="hello")]),
        _make_tool_response_msg("call-1", "bash", "output"),
        _make_tool_call_msg("call-1", "bash", '{"command": "ls"}'),
    ]
    result = to_openai_messages(messages)
    # After conversion, tool_call should come before tool_response
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"
    assert result[1]["tool_calls"][0]["id"] == "call-1"
    assert result[2]["role"] == "tool"
    assert result[2]["tool_call_id"] == "call-1"


def test_multiple_orphaned_tool_calls():
    """Multiple orphaned tool_calls each get synthetic responses."""
    messages = [
        Message(role=Role.USER, id="u1", timestamp_ms=100, content=[ContentNode(text="hello")]),
        Message(
            role=Role.ASSISTANT,
            id="a1",
            timestamp_ms=200,
            content=[
                ContentNode(tool_call=ToolCall(call_id="c1", tool="AgentComm", input='{"action":"send"}')),
                ContentNode(tool_call=ToolCall(call_id="c2", tool="bash", input='{"command":"ls"}')),
            ],
        ),
    ]
    result = to_openai_messages(messages)
    tool_responses = [r for r in result if r["role"] == "tool"]
    assert len(tool_responses) == 2
    call_ids = {r["tool_call_id"] for r in tool_responses}
    assert call_ids == {"c1", "c2"}


def test_mixed_orphaned_and_responded():
    """One tool_call has a response, another is orphaned."""
    messages = [
        Message(role=Role.USER, id="u1", timestamp_ms=100, content=[ContentNode(text="hello")]),
        Message(
            role=Role.ASSISTANT,
            id="a1",
            timestamp_ms=200,
            content=[
                ContentNode(tool_call=ToolCall(call_id="c1", tool="bash", input='{"command":"ls"}')),
                ContentNode(tool_call=ToolCall(call_id="c2", tool="AgentComm", input='{"action":"send"}')),
            ],
        ),
        _make_tool_response_msg("c1", "bash", "output"),
    ]
    result = to_openai_messages(messages)
    tool_responses = [r for r in result if r["role"] == "tool"]
    assert len(tool_responses) == 2
    # c1 has real response
    real = [r for r in tool_responses if r["tool_call_id"] == "c1"]
    assert real[0]["content"] == "output"
    # c2 has synthetic response
    synthetic = [r for r in tool_responses if r["tool_call_id"] == "c2"]
    assert "[no response recorded]" in synthetic[0]["content"]
