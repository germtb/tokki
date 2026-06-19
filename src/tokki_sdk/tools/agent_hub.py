"""AgentHub tool for agent-to-agent communication.

Presents a single tool to the LLM with discover/send actions.
Delegates to the server's MCP endpoint for actual execution.
"""

import logging
import time
from uuid import uuid4

from tokki_sdk.tokki_pb2 import Message, Role, ContentNode
from tokki_sdk.tools.base import Tool
from tokki_sdk.tools.helpers import tool_result_node_to_content_node

from .mcp import McpTool

logger = logging.getLogger(__name__)


class AgentHubDiscoveryTool(Tool):
    def __init__(self, context):
        self.mcp = McpTool(
            context,
            name="discover_personas",
            description="List available personas that you can communicate with.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )

    @property
    def name(self) -> str:
        return self.mcp.name

    @property
    def schema(self) -> dict:
        return self.mcp.schema

    async def execute(self, input: dict):
        return await self.mcp.execute(input)


class AgentHubSendTool(Tool):
    def __init__(self, context):
        super().__init__(context)
        self.mcp = McpTool(
            context,
            name="send_message",
            description="Send a message to another persona and get a response. The target persona will process your message and reply.",
            input_schema={
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "The globalId of the recipient agent.",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send.",
                    },
                },
                "required": ["recipient", "message"],
            },
        )

    @property
    def name(self) -> str:
        return self.mcp.name

    @property
    def schema(self) -> dict:
        return self.mcp.schema

    async def execute(self, input: dict):
        recipient = input["recipient"]
        message = input["message"]

        self.context.message_store.save_message(
            conversation_id=recipient,
            message=Message(
                role=Role.USER,
                id=str(uuid4()),
                timestamp_ms=int(time.time() * 1000),
                content=[ContentNode(text=message)],
            ),
        )

        response = await self.mcp.execute(input)

        self.context.message_store.save_message(
            conversation_id=recipient,
            message=Message(
                role=Role.ASSISTANT,
                id=str(uuid4()),
                timestamp_ms=int(time.time() * 1000),
                content=[tool_result_node_to_content_node(n) for n in response.nodes],
            ),
        )

        return response
