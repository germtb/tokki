"""
Anthropic vendor implementation.
"""

import aiohttp
import json
import logging
from typing import AsyncGenerator, Any, Sequence
from uuid import uuid4
from time import time

from .base import Vendor, Message, LlmConfig, _extract_tool_response_text
from tokki_sdk import tokki_pb2

Role = tokki_pb2.Role
ContentNode = tokki_pb2.ContentNode
ToolCall = tokki_pb2.ToolCall

logger = logging.getLogger(__name__)


def to_anthropic_messages(messages: Sequence[Message]) -> tuple[list[dict], str | None]:
    """
    Convert tokki messages to Anthropic format.

    Returns (messages_list, system_prompt) where system messages are extracted.
    """
    anthropic_messages = []
    system_parts = []

    for msg_idx, msg in enumerate(messages):
        if msg.role == Role.SYSTEM:
            # Extract system messages separately
            system_parts.extend(
                [node.text for node in msg.content if node.HasField("text")]
            )
        elif msg.role == Role.USER:
            # Convert user messages - check if they contain tool responses
            content_blocks = []
            has_tool_responses = False

            for node in msg.content:
                if node.HasField("tool_response"):
                    has_tool_responses = True
                    response_text = _extract_tool_response_text(node.tool_response)
                    # Anthropic expects tool_result format
                    content_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": node.tool_response.call_id,
                            "content": response_text,
                        }
                    )
                elif node.HasField("text"):
                    content_blocks.append(
                        {
                            "type": "text",
                            "text": node.text,
                        }
                    )

            if has_tool_responses:
                # Deduplicate tool results by call_id (Anthropic requires unique IDs)
                seen_ids = set()
                deduped_blocks = []
                for block in content_blocks:
                    if block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id")
                        if tool_id in seen_ids:
                            logger.warning(
                                f"Skipping duplicate tool_result with id: {tool_id}"
                            )
                            continue
                        seen_ids.add(tool_id)
                    deduped_blocks.append(block)

                # If message has tool responses, use structured content
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": deduped_blocks,
                    }
                )
            else:
                # Otherwise, use simple text format
                text_parts = [
                    node.text for node in msg.content if node.HasField("text")
                ]
                if text_parts:
                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": "\n".join(text_parts),
                        }
                    )
        elif msg.role == Role.ASSISTANT:
            # Convert assistant messages
            text_parts = []
            tool_calls = []
            seen_tool_ids = set()

            for node in msg.content:
                if node.HasField("text"):
                    text_parts.append(node.text)
                elif node.HasField("tool_call"):
                    # Check for duplicate tool call IDs
                    if node.tool_call.call_id in seen_tool_ids:
                        logger.warning(
                            f"Skipping duplicate tool_call with id: {node.tool_call.call_id}"
                        )
                        continue
                    seen_tool_ids.add(node.tool_call.call_id)

                    tool_calls.append(
                        {
                            "type": "tool_use",
                            "id": node.tool_call.call_id,
                            "name": node.tool_call.tool,
                            "input": (
                                json.loads(node.tool_call.input)
                                if node.tool_call.input
                                else {}
                            ),
                        }
                    )

            # Build content blocks
            content_blocks = []
            if text_parts:
                content_blocks.append(
                    {
                        "type": "text",
                        "text": "\n".join(text_parts),
                    }
                )
            content_blocks.extend(tool_calls)

            if content_blocks:
                anthropic_messages.append(
                    {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                )

    system_prompt = "\n".join(system_parts) if system_parts else None
    return anthropic_messages, system_prompt


class Anthropic(Vendor):
    """Anthropic API vendor."""

    def __init__(self, api_key: str, config: LlmConfig | None = None):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.api_version = (
            "2023-06-01"  # Updated API versions available: 2024-01-01, etc.
        )
        self.config = config

    async def inference_no_streaming(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> Message:
        raise NotImplementedError("Anthropic non-streaming inference not implemented")

    async def inference(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[Message, None]:
        """
        Anthropic tool calling support with streaming.

        Accumulates content blocks and parses to tokki format on each event.
        """
        anthropic_messages, system = to_anthropic_messages(messages)

        # Convert OpenAI format tools to Anthropic format
        anthropic_tools = (
            self._convert_tools_to_anthropic_format(tools) if tools else None
        )

        # Build request with config options
        if self.config and self.config.HasField("max_tokens"):
            max_tokens = self.config.max_tokens

        request_data = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        # Apply optional config parameters
        if self.config:
            if self.config.HasField("temperature"):
                request_data["temperature"] = self.config.temperature
            if self.config.HasField("top_p"):
                request_data["top_p"] = self.config.top_p
            if self.config.HasField("top_k"):
                request_data["top_k"] = self.config.top_k
            if self.config.stop_sequences:
                request_data["stop_sequences"] = list(self.config.stop_sequences)

        if anthropic_tools:
            request_data["tools"] = anthropic_tools

        if system:
            request_data["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }

        message_id = str(uuid4())

        # Accumulate content blocks in order
        content_blocks: list[dict[str, Any]] = []

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/messages",
                json=request_data,
                headers=headers,
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"Anthropic API error response: {error_text}")
                response.raise_for_status()
                async for line in response.content:
                    if not line:
                        continue

                    try:
                        line_text = line.decode("utf-8").strip()
                        if not line_text or not line_text.startswith("data: "):
                            continue

                        data = json.loads(line_text[6:])  # Remove "data: " prefix
                        event_type = data.get("type")

                        # Start new content block
                        if event_type == "content_block_start":
                            block = data.get("content_block", {})
                            if block.get("type") == "text":
                                content_blocks.append({"type": "text", "text": ""})
                            elif block.get("type") == "tool_use":
                                content_blocks.append(
                                    {
                                        "type": "tool_use",
                                        "id": block.get("id"),
                                        "name": block.get("name"),
                                        "input": "",
                                    }
                                )

                        # Update content block with delta
                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            index = data.get("index", len(content_blocks) - 1)

                            if index < len(content_blocks):
                                if delta.get("type") == "text_delta":
                                    content_blocks[index]["text"] += delta.get(
                                        "text", ""
                                    )
                                elif delta.get("type") == "input_json_delta":
                                    content_blocks[index]["input"] += delta.get(
                                        "partial_json", ""
                                    )

                        # Parse accumulated blocks -> tokki ContentNodes
                        content_nodes = self._parse_anthropic_blocks(content_blocks)

                        # Only yield if we have content
                        if content_nodes:
                            msg = Message(
                                role=Role.ASSISTANT,
                                id=message_id,
                                timestamp_ms=int(time() * 1000),
                                content=content_nodes,
                            )

                            yield msg

                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning(f"Failed to parse streaming chunk: {e}")
                        continue

    def _parse_anthropic_blocks(
        self, blocks: list[dict[str, Any]]
    ) -> list[ContentNode]:
        """Parse Anthropic content blocks to tokki ContentNodes."""
        nodes = []

        for block in blocks:
            if block["type"] == "text" and block.get("text"):
                nodes.append(ContentNode(text=block["text"]))
            elif block["type"] == "tool_use" and block.get("name"):
                nodes.append(
                    ContentNode(
                        tool_call=ToolCall(
                            call_id=block.get("id") or str(uuid4()),
                            tool=block["name"],
                            input=block.get("input", ""),
                        )
                    )
                )

        return nodes

    def _convert_tools_to_anthropic_format(
        self, openai_tools: list[dict]
    ) -> list[dict]:
        """
        Convert OpenAI format tools to Anthropic format.

        OpenAI format:
        {
          "type": "function",
          "function": {
            "name": "bash",
            "description": "...",
            "parameters": {...}
          }
        }

        Anthropic format:
        {
          "name": "bash",
          "description": "...",
          "input_schema": {...}
        }
        """
        anthropic_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description"),
                        "input_schema": func.get("parameters", {}),
                    }
                )
            else:
                # If it's already in Anthropic format, pass through
                anthropic_tools.append(tool)

        return anthropic_tools
