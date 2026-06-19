"""Tool executor for parsed tool calls."""

import json
import logging

from tokki_sdk.tokki_pb2 import (
    ToolCall,
    ToolResponse,
    ToolResultContent,
    ToolResultContentNode,
)

from .base import Tool, ToolError
from .context import ExecutionContext
from .helpers import error_result
import asyncio


logger = logging.getLogger(__name__)


class ToolExecutor:
    """Execute tool calls sequentially."""

    def __init__(
        self,
        tools: list[Tool],
        context: ExecutionContext | None = None,
    ):
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}
        self._context = context

    def _resolve_resource_uri(self, uri: str) -> str:
        """
        Resolve workspace-relative URIs to appropriate format.

        - With files_base_url: transforms /workspace/path to full URL
        - Local without files_base_url: transforms /workspace/path to absolute filesystem path
        - Docker without files_base_url: keeps /workspace/path as-is (backend transforms later)
        """
        if not uri.startswith("/workspace/"):
            return uri

        relative_path = uri[len("/workspace/") :]

        if self._context and self._context.files_base_url:
            return f"{self._context.files_base_url}/{relative_path}"

        if self._context:
            workspace_absolute = self._context.workspace_dir.resolve()
            if not str(workspace_absolute).startswith("/app"):
                return str(workspace_absolute / relative_path)

        return uri

    def _resolve_content_uris(
        self, nodes: list[ToolResultContentNode]
    ) -> list[ToolResultContentNode]:
        """Resolve URIs in all content nodes."""
        resolved: list[ToolResultContentNode] = []
        for item in nodes:
            which = item.WhichOneof("content")
            if which == "resource_link":
                new = ToolResultContentNode()
                new.resource_link.CopyFrom(item.resource_link)
                new.resource_link.uri = self._resolve_resource_uri(
                    item.resource_link.uri
                )
                resolved.append(new)
            elif which == "embedded_resource":
                new = ToolResultContentNode()
                new.embedded_resource.CopyFrom(item.embedded_resource)
                new.embedded_resource.uri = self._resolve_resource_uri(
                    item.embedded_resource.uri
                )
                resolved.append(new)
            else:
                resolved.append(item)
        return resolved

    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        """Return eager tool schemas only."""
        return [tool.schema for tool in self._tools.values()]

    async def execute(
        self,
        tool_calls: list[ToolCall],
        extra_tools: dict[str, Tool] | None = None,
    ) -> list[ToolResponse]:
        logger.info(f"Executing {len(tool_calls)} tool calls")

        if not tool_calls:
            return []

        if not extra_tools:
            extra_tools = {}

        results = await asyncio.gather(
            *[
                self._execute_single(
                    tool_call,
                    self._tools.get(tool_call.tool) or extra_tools.get(tool_call.tool),
                )
                for tool_call in tool_calls
            ]
        )
        return results

    async def _execute_single(
        self, tool_call: ToolCall, tool: Tool | None
    ) -> ToolResponse:
        """Execute single tool call."""
        try:
            arguments = json.loads(tool_call.input)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool input as JSON: {tool_call.input}")
            return ToolResponse(
                call_id=tool_call.call_id,
                tool=tool_call.tool,
                content=error_result(
                    f"Error: Failed to parse tool input JSON: {str(e)}"
                ),
            )

        if tool is None:
            logger.error(f"Unknown tool requested: {tool_call.tool}")
            return ToolResponse(
                call_id=tool_call.call_id,
                tool=tool_call.tool,
                content=error_result(f"Error: Unknown tool: {tool_call.tool}"),
            )

        try:
            logger.info(f"Executing tool {tool_call.tool} with arguments: {arguments}")
            result = await tool.execute(arguments)
            logger.info(
                f"Tool {tool_call.tool} executed successfully with output: {result}"
            )

            resolved_nodes = self._resolve_content_uris(list(result.nodes))
            return ToolResponse(
                call_id=tool_call.call_id,
                tool=tool_call.tool,
                content=ToolResultContent(
                    nodes=resolved_nodes, is_error=result.is_error
                ),
            )
        except ToolError as e:
            logger.error(
                f"Tool error executing tool {tool_call.tool} with arguments {arguments}: {str(e)}"
            )
            return ToolResponse(
                call_id=tool_call.call_id,
                tool=tool_call.tool,
                content=error_result(f"Error: {str(e)}"),
            )
        except Exception as e:
            logger.error(
                f"Unexpected error executing tool {tool_call.tool} with arguments {arguments}: {str(e)}"
            )
            return ToolResponse(
                call_id=tool_call.call_id,
                tool=tool_call.tool,
                content=error_result(f"Error: {str(e)}"),
            )
