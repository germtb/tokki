"""IntegrationsTool: namespace-based deferred tool loading.

MCP tools are namespaced by integration (e.g. truelayer__list_bank_accounts).
The meta-tool operates on namespaces, not individual tools:
1. list — discover available integration namespaces
2. load — mark a namespace as loaded in the trajectory

Tool instances for loaded namespaces are derived declaratively from the
conversation trajectory — no mutable state needed. The toolcall agent
uses these to populate both inference schemas and executor lazy tools.
"""

import json
import logging
import time
from collections import defaultdict

from .base import Tool
from .helpers import text_result, error_result
from .mcp import McpTool, _get_mcp_config, list_mcp_tools

logger = logging.getLogger(__name__)

# Core tools that are NOT integrations — filter these out.
CORE_TOOLS = {"discover_personas", "send_message"}

# Cache TTL for tools/list results (seconds).
_CACHE_TTL = 300


class IntegrationsTool(Tool):
    """Meta-tool that discovers and loads integration namespaces."""

    def __init__(self, context):
        super().__init__(context)
        self._cached_tools: list[dict] | None = None
        self._cache_time: float = 0

    @property
    def name(self) -> str:
        return "integrations"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "integrations",
                "description": (
                    "Discover and load external integrations (banking, email, etc.). "
                    "Call with no arguments to list available integrations. "
                    "Call with namespace to load all tools for that integration. "
                    "After loading, the integration's tools become available to call directly."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Integration namespace to load (e.g. 'truelayer'). Omit to list all.",
                        },
                    },
                },
            },
        }

    async def execute(self, input: dict):
        namespace = input.get("namespace")
        if namespace:
            return await self._handle_load(namespace)
        return await self._handle_list()

    async def _get_tools(self) -> list[dict]:
        """Return integration tool descriptors, using a 300s cache."""
        now = time.monotonic()
        if self._cached_tools is not None and (now - self._cache_time) < _CACHE_TTL:
            return self._cached_tools

        config = _get_mcp_config()
        if config is None:
            return []

        server_url, token, global_id = config
        all_tools = await list_mcp_tools(server_url, token, global_id)
        integration_tools = [t for t in all_tools if t.get("name") not in CORE_TOOLS]

        self._cached_tools = integration_tools
        self._cache_time = now
        return integration_tools

    def _group_by_namespace(self, tools: list[dict]) -> dict[str, list[dict]]:
        """Group tools by namespace prefix (e.g. 'truelayer__x' → 'truelayer')."""
        groups: dict[str, list[dict]] = defaultdict(list)
        for tool in tools:
            name = tool.get("name", "")
            if "__" in name:
                ns, _ = name.split("__", 1)
                groups[ns].append(tool)
            else:
                groups["_other"].append(tool)
        return dict(groups)

    async def get_loaded_tools(self, messages) -> list[McpTool]:
        """Derive loaded integration tools from the conversation trajectory.

        Scans messages for integrations(namespace=X) calls and returns
        McpTool instances for all loaded namespaces. Used by the agent to
        populate both inference schemas and executor lazy tools.
        """
        loaded_namespaces: set[str] = set()
        for msg in messages:
            for node in msg.content:
                if not node.HasField("tool_call"):
                    continue
                if node.tool_call.tool != "integrations":
                    continue
                try:
                    args = json.loads(node.tool_call.input)
                    ns = args.get("namespace")
                    if ns:
                        loaded_namespaces.add(ns)
                except (json.JSONDecodeError, AttributeError):
                    pass

        if not loaded_namespaces:
            return []

        tools = await self._get_tools()
        groups = self._group_by_namespace(tools)

        mcp_tools = []
        for ns in loaded_namespaces:
            for tool_def in groups.get(ns, []):
                mcp_tools.append(
                    McpTool(
                        context=self.context,
                        name=tool_def.get("name", ""),
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get("inputSchema", {}),
                    )
                )
        return mcp_tools

    async def _handle_list(self):
        try:
            tools = await self._get_tools()
        except Exception as e:
            logger.error(f"Failed to list integrations: {e}")
            return error_result(f"Failed to list integrations: {e}")

        if not tools:
            return text_result("No integrations available.")

        groups = self._group_by_namespace(tools)
        lines = ["Available integrations:\n"]
        for ns, ns_tools in sorted(groups.items()):
            if ns == "_other":
                continue
            tool_names = [t["name"].split("__", 1)[1] for t in ns_tools]
            lines.append(f"- {ns} ({len(ns_tools)} tools: {', '.join(tool_names)})")

        lines.append(
            '\nCall integrations(namespace="<name>") to load an integration\'s tools.'
        )
        return text_result("\n".join(lines))

    async def _handle_load(self, namespace: str):
        try:
            tools = await self._get_tools()
        except Exception as e:
            logger.error(f"Failed to load integration: {e}")
            return error_result(f"Failed to load integration: {e}")

        groups = self._group_by_namespace(tools)
        ns_tools = groups.get(namespace)
        if ns_tools is None:
            available = sorted(k for k in groups if k != "_other")
            return error_result(
                f'Unknown integration "{namespace}". Available: {", ".join(available) or "(none)"}'
            )

        tool_names = [t["name"] for t in ns_tools]
        return text_result(
            f"Loaded {len(ns_tools)} tools for '{namespace}': {', '.join(tool_names)}. "
            f"You can now call them directly."
        )
