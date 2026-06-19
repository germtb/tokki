"""
Tests for streaming tool_call consistency.

Reproduces the bug where _parse_kimi_response generates a different UUID
on every streaming chunk (because accumulated_response["tool_calls"][idx]["id"]
is None), causing the server to see multiple distinct call_ids for a single
tool call. When tool_responses for the stale call_ids are saved to SQLite,
the next request sends them to the Kimi API which rejects them:
  "tool_call_id  is not found"
"""

import json
from uuid import uuid4
from time import time

from tokki_sdk.tokki_pb2 import (
    ContentNode,
    Log,
    LogLevel,
    Message,
    Role,
    ToolCall,
    ToolResponse,
    ToolResultContent,
    ToolResultContentNode,
    TextContent,
)
from tokki_sdk.vendor.kimi import Kimi
from tokki_sdk.vendor.mistral import Mistral
from tokki_sdk.vendor.base import to_openai_messages


def _simulate_streaming_chunks(vendor, chunks: list[dict]) -> list[Message]:
    """
    Simulate progressive streaming by feeding chunks into the vendor's
    accumulator and parser, collecting all yielded messages.
    """
    accumulated_response = {"content": "", "tool_calls": []}
    message_id = str(uuid4())
    messages = []

    for chunk_delta in chunks:
        # Update accumulated response (same logic as in inference())
        if content := chunk_delta.get("content"):
            accumulated_response["content"] += content

        if tool_calls := chunk_delta.get("tool_calls"):
            for tool_call in tool_calls:
                idx = tool_call.get("index", 0)
                while len(accumulated_response["tool_calls"]) <= idx:
                    accumulated_response["tool_calls"].append(
                        {"id": str(uuid4()), "function": {"name": "", "arguments": ""}}
                    )
                if "id" in tool_call and not accumulated_response["tool_calls"][idx]["id"]:
                    accumulated_response["tool_calls"][idx]["id"] = tool_call["id"]
                if "function" in tool_call:
                    func = tool_call["function"]
                    if "name" in func:
                        accumulated_response["tool_calls"][idx]["function"]["name"] = func["name"]
                    if "arguments" in func:
                        accumulated_response["tool_calls"][idx]["function"]["arguments"] += func["arguments"]

        # Parse using vendor's method
        if isinstance(vendor, Kimi):
            content_nodes = vendor._parse_kimi_response(accumulated_response)
        else:
            content_nodes = vendor._parse_mistral_response(accumulated_response)

        if content_nodes:
            msg = Message(
                role=Role.ASSISTANT,
                id=message_id,
                timestamp_ms=int(time() * 1000),
                content=content_nodes,
            )
            messages.append(msg)

    return messages


class TestStreamingToolCallConsistency:
    """Verify that tool call_ids are stable across streaming chunks."""

    def _make_vendor(self, cls):
        """Create a vendor instance (API key unused since we don't call inference)."""
        return cls(api_key="test-key")

    def test_kimi_stable_call_id_across_chunks(self):
        """call_id must be the same across all streaming chunks for a single tool call."""
        vendor = self._make_vendor(Kimi)

        # Simulate: chunk 1 has name but no id, chunk 2 has arguments, chunk 3 has id
        chunks = [
            {"tool_calls": [{"index": 0, "function": {"name": "AgentComm", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"action":'}}]},
            {"tool_calls": [{"index": 0, "id": "call_real_123", "function": {"arguments": ' "discover"}'}}]},
        ]

        messages = _simulate_streaming_chunks(vendor, chunks)
        assert len(messages) >= 2, f"Expected multiple streaming messages, got {len(messages)}"

        # Extract all call_ids across streaming messages
        call_ids = set()
        for msg in messages:
            for node in msg.content:
                if node.HasField("tool_call"):
                    call_ids.add(node.tool_call.call_id)

        # All chunks should produce the SAME call_id (the final real one, or a stable generated one)
        assert len(call_ids) == 1, (
            f"Expected 1 unique call_id across streaming chunks, got {len(call_ids)}: {call_ids}"
        )

    def test_mistral_stable_call_id_across_chunks(self):
        """Same test for Mistral vendor."""
        vendor = self._make_vendor(Mistral)

        chunks = [
            {"tool_calls": [{"index": 0, "function": {"name": "Bash", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"command":'}}]},
            {"tool_calls": [{"index": 0, "id": "call_xyz", "function": {"arguments": ' "ls"}'}}]},
        ]

        messages = _simulate_streaming_chunks(vendor, chunks)
        assert len(messages) >= 2

        call_ids = set()
        for msg in messages:
            for node in msg.content:
                if node.HasField("tool_call"):
                    call_ids.add(node.tool_call.call_id)

        assert len(call_ids) == 1, (
            f"Expected 1 unique call_id across streaming chunks, got {len(call_ids)}: {call_ids}"
        )

    def test_openai_messages_tool_response_matches_tool_call(self):
        """
        End-to-end: simulate the full flow where streaming produces an assistant
        message with tool_call, server resumes with tool_response, then a new
        request loads everything from SQLite and converts to OpenAI format.
        Every tool_response.tool_call_id must reference an existing tool_call.id.
        """
        vendor = self._make_vendor(Kimi)

        # Simulate streaming chunks (id arrives in first chunk, like typical OpenAI format)
        chunks = [
            {"tool_calls": [{"index": 0, "id": "call_abc", "function": {"name": "AgentComm", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"action": "discover"}'}}]},
        ]

        messages = _simulate_streaming_chunks(vendor, chunks)
        # Last message is the final state
        assistant_msg = messages[-1]

        # Extract the call_id from the assistant message
        call_id = None
        for node in assistant_msg.content:
            if node.HasField("tool_call"):
                call_id = node.tool_call.call_id
        assert call_id, "Assistant message should have a tool_call"

        # Simulate server creating tool_response with the same call_id
        tool_msg = Message(
            role=Role.TOOL,
            id=str(uuid4()),
            timestamp_ms=int(time() * 1000),
            content=[
                ContentNode(
                    tool_response=ToolResponse(
                        call_id=call_id,
                        tool="AgentComm",
                        content=ToolResultContent(
                            nodes=[ToolResultContentNode(text=TextContent(text="Available personas: ..."))]
                        ),
                    )
                )
            ],
        )

        # Simulate next request: system + user + assistant(tool_call) + tool(response) + assistant(text) + user
        all_messages = [
            Message(role=Role.SYSTEM, id="sys", content=[ContentNode(text="You are helpful")]),
            Message(role=Role.USER, id="u1", content=[ContentNode(text="List personas")]),
            assistant_msg,
            tool_msg,
            Message(role=Role.ASSISTANT, id="a2", content=[ContentNode(text="Here are the personas...")]),
            Message(role=Role.USER, id="u2", content=[ContentNode(text="Tell me more")]),
        ]

        openai_msgs = to_openai_messages(all_messages)

        # Collect all tool_call ids and tool_call_id references
        declared_ids = set()
        referenced_ids = set()
        for msg in openai_msgs:
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    declared_ids.add(tc["id"])
            if msg.get("role") == "tool":
                referenced_ids.add(msg["tool_call_id"])

        # Every referenced tool_call_id must exist in declared_ids
        orphaned = referenced_ids - declared_ids
        assert not orphaned, (
            f"Orphaned tool_call_ids (no matching tool_call): {orphaned}. "
            f"Declared: {declared_ids}, Referenced: {referenced_ids}"
        )

    def test_tool_response_before_tool_call_in_timestamp_order(self):
        """
        Reproduces the exact production trace from persona/germtf/pa:

        Messages loaded from SQLite ordered by timestamp_ms:
          msg 0: USER     ts=1000  "which agents are available?"
          msg 1: SYSTEM   ts=1001  system prompt
          msg 2: TOOL     ts=1005  tool_response(call_id=X, AgentComm)  <-- BEFORE tool_call!
          msg 3: ASSISTANT ts=1006  tool_call(call_id=X, AgentComm)
          msg 4: ASSISTANT ts=1010  "The available agents are..."
          msg 5: USER     ts=1015  "tell me more"

        The TOOL response (ts=1005) sorts BEFORE the ASSISTANT tool_call (ts=1006)
        because the server built the resume request timestamp before the agent saved
        its assistant message. When to_openai_messages converts these in order, the
        API sees a tool_response referencing a tool_call that hasn't been declared yet.

        The fix: to_openai_messages must ensure tool_responses are placed after their
        matching tool_calls, regardless of input ordering.
        """
        call_id = "c68b0355-b943-4075-820a-d8f3e5164df9"

        messages = [
            Message(role=Role.USER, id="u1", timestamp_ms=1000,
                    content=[ContentNode(text="which agents are available?")]),
            Message(role=Role.SYSTEM, id="sys", timestamp_ms=1001,
                    content=[ContentNode(text="You are helpful")]),
            # TOOL response BEFORE the assistant tool_call (bad timestamp ordering)
            Message(role=Role.TOOL, id="tool1", timestamp_ms=1005,
                    content=[ContentNode(tool_response=ToolResponse(
                        call_id=call_id, tool="AgentComm",
                        content=ToolResultContent(nodes=[ToolResultContentNode(text=TextContent(text="Available personas: ..."))])
                    ))]),
            Message(role=Role.ASSISTANT, id="a1", timestamp_ms=1006,
                    content=[ContentNode(tool_call=ToolCall(
                        call_id=call_id, tool="AgentComm",
                        input='{"action": "discover"}'))]),
            Message(role=Role.ASSISTANT, id="a2", timestamp_ms=1010,
                    content=[ContentNode(text="The available agents are...")]),
            Message(role=Role.USER, id="u2", timestamp_ms=1015,
                    content=[ContentNode(text="tell me more")]),
        ]

        openai_msgs = to_openai_messages(messages)

        # Find the positions of the assistant(tool_calls) and tool messages
        assistant_tc_idx = None
        tool_idx = None
        for i, msg in enumerate(openai_msgs):
            if msg.get("tool_calls"):
                assistant_tc_idx = i
            if msg.get("role") == "tool" and msg.get("tool_call_id") == call_id:
                tool_idx = i

        assert assistant_tc_idx is not None, "Should have an assistant message with tool_calls"
        assert tool_idx is not None, "Should have a tool response message"

        # The tool response MUST come AFTER the assistant message that declared the tool_call
        assert tool_idx > assistant_tc_idx, (
            f"tool response (idx={tool_idx}) must come after assistant tool_call (idx={assistant_tc_idx}). "
            f"OpenAI messages: {[m.get('role') for m in openai_msgs]}"
        )

    def test_id_arrives_late_still_stable(self):
        """
        When the API sends the id in a later chunk (not the first),
        the call_id should still be consistent across all yielded messages.
        """
        vendor = self._make_vendor(Kimi)

        # Chunk 1: name only, no id
        # Chunk 2: arguments only
        # Chunk 3: id finally arrives
        chunks = [
            {"tool_calls": [{"index": 0, "function": {"name": "AgentComm", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"action":'}}]},
            {"tool_calls": [{"index": 0, "id": "call_late", "function": {"arguments": ' "discover"}'}}]},
        ]

        messages = _simulate_streaming_chunks(vendor, chunks)

        call_ids = []
        for msg in messages:
            for node in msg.content:
                if node.HasField("tool_call"):
                    call_ids.append(node.tool_call.call_id)

        # All should be the same (stable UUID, not overwritten by the API's late id)
        assert len(set(call_ids)) == 1, (
            f"call_ids should be stable but got: {call_ids}"
        )

    def test_assistant_log_only_message_not_sent_as_empty(self):
        """
        Reproduces the code-reviewer bug: when a previous request fails, the
        error handler saves an ASSISTANT message with only a Log ContentNode.
        On the next request, _content_to_str produces "" for that message,
        and to_openai_messages sends {"role": "assistant", "content": ""}
        which Kimi rejects: "the message at position 2 with role 'assistant'
        must not be empty".

        Fix: to_openai_messages must skip assistant messages with empty content.
        """
        messages = [
            Message(role=Role.SYSTEM, id="sys", timestamp_ms=1000,
                    content=[ContentNode(text="You are helpful")]),
            Message(role=Role.USER, id="u1", timestamp_ms=1001,
                    content=[ContentNode(text="review this code")]),
            # Error handler saved this ASSISTANT message with only a log node
            Message(role=Role.ASSISTANT, id="err1", timestamp_ms=1002,
                    content=[ContentNode(log=Log(
                        level=LogLevel.ERROR,
                        message="All 3 inference attempts failed: 429 Too Many Requests",
                    ))]),
            Message(role=Role.USER, id="u2", timestamp_ms=2000,
                    content=[ContentNode(text="try again")]),
        ]

        openai_msgs = to_openai_messages(messages)

        # No assistant message should have empty content
        for msg in openai_msgs:
            if msg.get("role") == "assistant":
                content = msg.get("content")
                assert content, (
                    f"Assistant message must not have empty content, got: {msg}"
                )
