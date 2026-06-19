"""
Kimi (Moonshot AI) vendor implementation.
"""

import aiohttp
import json
import logging
from typing import AsyncGenerator, Any, Sequence
from uuid import uuid4
from time import time

from .base import Vendor, Message, to_openai_messages
from tokki_sdk import tokki_pb2

Role = tokki_pb2.Role
ContentNode = tokki_pb2.ContentNode
ToolCall = tokki_pb2.ToolCall
LlmConfig = tokki_pb2.LlmConfig

logger = logging.getLogger(__name__)


class Kimi(Vendor):
    """Kimi (Moonshot AI) API vendor."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.ai/v1",
        config: LlmConfig | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.config = config

    def prepare_request(
        self,
        messages: Sequence[Message],
        model: str,
        max_tokens: int,
        stream: bool,
        tools: list[dict] | None = None,
    ) -> dict:
        openai_messages = to_openai_messages(messages)

        request_data = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Apply config options
        if self.config:
            if self.config.HasField("temperature"):
                request_data["temperature"] = self.config.temperature
            if self.config.HasField("max_tokens"):
                request_data["max_tokens"] = self.config.max_tokens
            if self.config.HasField("top_p"):
                request_data["top_p"] = self.config.top_p
            if self.config.stop_sequences:
                request_data["stop"] = list(self.config.stop_sequences)

        if tools:
            request_data["tools"] = tools

        return request_data

    def prepare_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def inference_no_streaming(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> Message:
        payload = self.prepare_request(
            messages, model, max_tokens, stream=False, tools=tools
        )
        headers = self.prepare_headers()
        message_id = str(uuid4())

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            if resp.status >= 400:
                error_text = await resp.text()
                raise RuntimeError(
                    f"Kimi API error response ({resp.status}): {error_text}"
                )

            data = await resp.json()
            choice = data["choices"][0]["message"]
            content_nodes = self._parse_kimi_response(choice)

            # Only yield if we have content
            return Message(
                role=Role.ASSISTANT,
                id=message_id,
                timestamp_ms=int(time() * 1000),
                content=content_nodes,
            )

    async def inference(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[Message, None]:
        payload = self.prepare_request(
            messages, model, max_tokens=max_tokens, stream=True, tools=tools
        )
        headers = self.prepare_headers()
        message_id = str(uuid4())

        # Accumulate vendor response in native format
        accumulated_response: dict[str, Any] = {"content": "", "tool_calls": []}

        timeout = aiohttp.ClientTimeout(
            total=None,  # No total timeout
            sock_connect=30,  # 30s to establish connection
            sock_read=300,  # 5 minutes between chunks (generous for slow LLMs)
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(
                        f"Kimi API error response ({response.status}): {error_text}"
                    )
                response.raise_for_status()
                async for line in response.content:
                    if not line:
                        continue

                    try:
                        line_text = line.decode("utf-8").strip()
                        if not line_text or not line_text.startswith("data: "):
                            continue

                        if line_text == "data: [DONE]":
                            break

                        data = json.loads(line_text[6:])  # Remove "data: " prefix
                        delta = data.get("choices", [{}])[0].get("delta", {})

                        # Update accumulated response with deltas
                        if content := delta.get("content"):
                            accumulated_response["content"] += content

                        if tool_calls := delta.get("tool_calls"):
                            for tool_call in tool_calls:
                                idx = tool_call.get("index", 0)
                                # Ensure array size — assign a stable UUID upfront
                                # so call_id is consistent across streaming chunks.
                                # The API may overwrite it with its own id later.
                                while len(accumulated_response["tool_calls"]) <= idx:
                                    accumulated_response["tool_calls"].append(
                                        {
                                            "id": str(uuid4()),
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    )

                                # Update tool call at index — only set id if not already assigned
                                # (we pre-assign a stable UUID; the API may send its own later,
                                # but changing mid-stream causes mismatches with the server)
                                if (
                                    "id" in tool_call
                                    and not accumulated_response["tool_calls"][idx][
                                        "id"
                                    ]
                                ):
                                    accumulated_response["tool_calls"][idx]["id"] = (
                                        tool_call["id"]
                                    )
                                if "function" in tool_call:
                                    func = tool_call["function"]
                                    if "name" in func:
                                        accumulated_response["tool_calls"][idx][
                                            "function"
                                        ]["name"] = func["name"]
                                    if "arguments" in func:
                                        accumulated_response["tool_calls"][idx][
                                            "function"
                                        ]["arguments"] += func["arguments"]

                        # Parse accumulated response -> tokki ContentNodes
                        content_nodes = self._parse_kimi_response(accumulated_response)

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

    def _parse_kimi_response(self, response: dict[str, Any]) -> list[ContentNode]:
        """Parse Kimi response format to tokki ContentNodes."""
        nodes = []

        # Add text content if present
        if response.get("content"):
            nodes.append(ContentNode(text=response["content"]))

        # Add tool calls
        for tool_call in response.get("tool_calls", []):
            func = tool_call.get("function", {})
            if func.get("name"):
                nodes.append(
                    ContentNode(
                        tool_call=ToolCall(
                            call_id=tool_call.get("id") or str(uuid4()),
                            tool=func["name"],
                            input=func.get("arguments", ""),
                        )
                    )
                )

        return nodes
