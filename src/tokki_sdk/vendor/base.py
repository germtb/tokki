"""
Base vendor abstraction and helper functions.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import random
from typing import Any, AsyncGenerator, Sequence

from tokki_sdk import tokki_pb2

logger = logging.getLogger(__name__)

Message = tokki_pb2.Message
Role = tokki_pb2.Role
ContentNode = tokki_pb2.ContentNode
LlmConfig = tokki_pb2.LlmConfig


def _extract_tool_response_text(tool_response) -> str:
    """Extract text content from a ToolResponse's content field."""
    texts = []
    for node in tool_response.content.nodes:
        if node.HasField("text"):
            texts.append(node.text.text)
    return "\n".join(texts) if texts else ""


def content_to_str(content: Sequence[ContentNode]) -> str:
    """Convert a sequence of ContentNodes to a string."""
    result: list[str] = []
    for node in content:
        if node.HasField("text"):
            result.append(node.text)
        elif node.HasField("thought"):
            result.append(f"Thought: {node.thought.text}")
        elif node.HasField("tool_call"):
            name = (
                f"{node.tool_call.tool}.{node.tool_call.action}"
                if node.tool_call.action
                else node.tool_call.tool
            )
            result.append(f"Tool Call: {name}({node.tool_call.input})")
        elif node.HasField("tool_response"):
            name = (
                f"{node.tool_response.tool}.{node.tool_response.action}"
                if node.tool_response.action
                else node.tool_response.tool
            )
            response_text = _extract_tool_response_text(node.tool_response)
            result.append(f"Tool Response: {name} => {response_text}")
        elif node.HasField("compaction"):
            result.append("Compaction summary: " + node.compaction.text)
    return "\n".join(result)


def estimate_tokens(messages: Sequence[Message]) -> int:
    """Estimate token count using chars/4 heuristic."""
    total = 0
    openai_messages = to_openai_messages(messages)
    for msg in openai_messages:
        content = msg.get("content", "")
        total += len(content) if content else 0

        # Include tool_calls in token estimation
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                total += len(tc.get("function", {}).get("name", ""))
                total += len(tc.get("function", {}).get("arguments", ""))

    return total // 4


def to_openai_messages(messages: Sequence[Message]) -> list[dict]:
    """
    Convert tokki messages to OpenAI-compatible format (also works for Mistral).

    Properly handles tool calls and tool responses in structured format.
    Returns a list of dicts like: {"role": "user", "content": "..."}

    Tool responses are deferred until after their matching tool_call has been
    emitted, to handle cases where SQLite timestamp ordering puts the tool
    response before the assistant message that declared the tool_call.
    """
    result: list[dict[str, Any]] = []
    # Collect tool_response dicts keyed by call_id — inserted after their tool_call
    deferred_tool_responses: dict[str, list[dict]] = {}
    declared_tool_call_ids: set[str] = set()

    for msg in messages:
        if msg.role == Role.SYSTEM:
            result.append({"role": "system", "content": content_to_str(msg.content)})
        elif msg.role == Role.USER:
            result.append({"role": "user", "content": content_to_str(msg.content)})
        elif msg.role == Role.TOOL:
            for node in msg.content:
                if node.HasField("tool_response"):
                    response_text = _extract_tool_response_text(node.tool_response)
                    tool_msg = {
                        "role": "tool",
                        "name": node.tool_response.tool,
                        "content": response_text,
                        "tool_call_id": node.tool_response.call_id,
                    }
                    cid = node.tool_response.call_id
                    if cid in declared_tool_call_ids:
                        # tool_call already emitted — safe to append now
                        result.append(tool_msg)
                    else:
                        # Defer until the matching tool_call is emitted
                        deferred_tool_responses.setdefault(cid, []).append(tool_msg)
        elif msg.role == Role.ASSISTANT:
            tool_calls = [
                node.tool_call for node in msg.content if node.HasField("tool_call")
            ]

            text_content = "\n".join(
                [node.text for node in msg.content if node.HasField("text")]
            )

            if tool_calls:
                result.append(
                    {
                        "role": "assistant",
                        "content": text_content or None,  # type: ignore[dict-item]
                        "tool_calls": [  # type: ignore[dict-item]
                            {
                                "id": tc.call_id,
                                "type": "function",
                                "function": {
                                    "name": tc.tool,
                                    "arguments": tc.input,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                # Flush any deferred tool_responses for these call_ids
                for tc in tool_calls:
                    declared_tool_call_ids.add(tc.call_id)
                    if tc.call_id in deferred_tool_responses:
                        result.extend(deferred_tool_responses.pop(tc.call_id))
            else:
                text = content_to_str(msg.content)
                if text:  # Skip empty assistant messages (e.g. log-only error messages)
                    result.append({"role": "assistant", "content": text})

    # Append any remaining deferred responses (orphaned — no matching tool_call)
    for responses in deferred_tool_responses.values():
        result.extend(responses)

    # Inject synthetic responses for any tool_calls that never got a response.
    # This can happen when an A2A call was interrupted or the agent crashed
    # after emitting the tool_call but before the response was saved.
    responded_call_ids: set[str] = set()
    for entry in result:
        if entry.get("role") == "tool" and "tool_call_id" in entry:
            responded_call_ids.add(entry["tool_call_id"])
    for entry in result:
        if entry.get("role") == "assistant" and "tool_calls" in entry:
            for tc in entry["tool_calls"]:
                tc_id = tc.get("id", "")
                if tc_id and tc_id not in responded_call_ids:
                    result.append(
                        {
                            "role": "tool",
                            "name": tc.get("function", {}).get("name", "unknown"),
                            "content": "[no response recorded]",
                            "tool_call_id": tc_id,
                        }
                    )
                    responded_call_ids.add(tc_id)

    return result


class Vendor(ABC):
    config: LlmConfig | None = None

    @abstractmethod
    async def inference_no_streaming(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> Message:
        """
        Perform inference without streaming, returning the full response once complete.

        Args:
            messages: Conversation messages
            model: Model identifier
            tools: Tool definitions in provider-specific format
        Returns:
            The complete response message once inference is finished.
        """
        ...

    @abstractmethod
    def inference(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[Message, None]:
        """
        Perform inference with the vendor's model.

        Args:
            messages: Conversation messages
            model: Model identifier
            tools: Tool definitions in provider-specific format

        Returns:
            Async generator yielding Messages as they are produced.
        """
        ...
