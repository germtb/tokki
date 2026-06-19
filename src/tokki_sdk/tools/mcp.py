"""MCP tool wrapper for remote server-side tools.

Wraps a remote MCP tool as a local Tool, calling the server's MCP endpoint
(JSON-RPC 2.0 over HTTP) to execute tool calls. Schemas are provided at
construction time — no discovery round-trip needed.

Also provides module-level helpers for direct MCP interaction:
- call_mcp_tool(): Call a named tool via tools/call
- list_mcp_tools(): Discover available tools via tools/list
"""

import logging
import os

import aiohttp

from .base import Tool
from .helpers import text_result, error_result

logger = logging.getLogger(__name__)


def _get_mcp_config():
    """Return (server_url, token, global_id) from environment, or None if unavailable."""
    server_url = os.environ.get("TOKKI_MCP_URL")
    token = os.environ.get("TOKKI_MCP_TOKEN")
    global_id = os.environ.get("TOKKI_GLOBAL_ID", "")
    if not server_url or not token:
        return None
    return server_url, token, global_id


async def _mcp_request(
    server_url: str, token: str, global_id: str, method: str, params: dict
):
    """Send a JSON-RPC 2.0 request to the MCP server and return the parsed response."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
        "X-Tokki-Global-Id": global_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            server_url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=600),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception(f"MCP server error ({resp.status}): {body}")

            return await resp.json()


async def call_mcp_tool(
    server_url: str, token: str, global_id: str, tool_name: str, arguments: dict
):
    """Call tools/call on the MCP server. Returns a ToolResultContent proto."""
    data = await _mcp_request(
        server_url,
        token,
        global_id,
        method="tools/call",
        params={"name": tool_name, "arguments": arguments},
    )

    # Handle JSON-RPC error
    if "error" in data and data["error"] is not None:
        return error_result(data["error"].get("message", "Unknown MCP error"))

    # Parse result
    result = data.get("result", {})
    is_error = result.get("isError", False)
    content_items = result.get("content", [])

    # Extract text from MCP content items
    texts = []
    for item in content_items:
        if item.get("type") == "text":
            texts.append(item.get("text", ""))

    text = "\n".join(texts) if texts else "(no response)"

    if is_error:
        return error_result(text)
    return text_result(text)


async def list_mcp_tools(server_url: str, token: str, global_id: str) -> list[dict]:
    """Call tools/list on the MCP server. Returns a list of tool descriptors."""
    data = await _mcp_request(
        server_url,
        token,
        global_id,
        method="tools/list",
        params={},
    )

    if "error" in data and data["error"] is not None:
        raise Exception(data["error"].get("message", "Unknown MCP error"))

    result = data.get("result", {})
    return result.get("tools", [])


class McpTool(Tool):
    """Wraps a remote MCP tool as a local Tool.

    Calls tools/call on the MCP server via JSON-RPC 2.0 over HTTP.
    """

    def __init__(self, context, name: str, description: str, input_schema: dict):
        super().__init__(context)
        self._name = name
        self._description = description
        self._input_schema = input_schema

    @property
    def name(self) -> str:
        return self._name

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self._name,
                "description": self._description,
                "parameters": self._input_schema,
            },
        }

    async def execute(self, input: dict):
        config = _get_mcp_config()
        if config is None:
            return error_result("MCP not available (no server connection)")

        server_url, token, global_id = config

        try:
            return await call_mcp_tool(server_url, token, global_id, self._name, input)
        except Exception as e:
            logger.error(f"MCP call failed for {self._name}: {e}")
            return error_result(f"MCP call failed: {e}")
