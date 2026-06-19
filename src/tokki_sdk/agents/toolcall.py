import logging
from time import time
from uuid import uuid4
from tokki_sdk import (
    Agent,
    Context,
    Role,
    Status,
    Compactor,
)
from tokki_sdk.tools import ExecutionContext
from tokki_sdk.tokki_pb2 import ContentNode, Message
from tokki_sdk.tools import (
    Read,
    Write,
    Bash,
    Glob,
    Grep,
    Memory,
    IntegrationsTool,
    ToolExecutor,
)
from tokki_sdk.tools.agent_hub import (
    AgentHubDiscoveryTool,
    AgentHubSendTool,
)
from tokki_sdk.tools.base import Tool
from tokki_sdk.vendor.base import Vendor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Toolcall(Agent):
    """
    A toolcall agent that can execute bash commands, read/write files, and search code.

    Uses a ReACT-style loop with unrestricted tools thanks to session-based isolation.
    """

    def __init__(
        self,
        model: str,
        summarisation_model: str,
        vendor: Vendor,
        max_iterations: int = 10,
    ):
        self.model = model
        self.summarisation_model = summarisation_model
        self.vendor = vendor
        self.max_iterations = max_iterations
        self.execution_context = ExecutionContext(
            workspace_dir="workspace",
            enforce_boundaries=True,
        )
        self.integrations_tool = IntegrationsTool(self.execution_context)
        self.executor = ToolExecutor(
            tools=[
                Read(self.execution_context),
                Write(self.execution_context),
                Bash(self.execution_context),
                Glob(self.execution_context),
                Grep(self.execution_context),
                Memory(self.execution_context),
                AgentHubDiscoveryTool(self.execution_context),
                AgentHubSendTool(self.execution_context),
                self.integrations_tool,
            ],
            context=self.execution_context,
        )
        self.compactor = Compactor(
            max_context_tokens=120_000, vendor=vendor, model=summarisation_model
        )

    async def init(self, context: Context) -> bool:
        # Use persona system_prompt if injected by the server, otherwise default
        if context.system_prompt:
            prompt = context.system_prompt
        else:
            prompt = "You are a helpful AI agent with access to tools.\n\nUse markdown as your response format."

        context.upsert_message_from_input(
            role=Role.SYSTEM,
            id="system-prompt",
            content=[ContentNode(text=prompt)],
        )
        return True

    async def step(self, context: Context) -> bool:
        # Get messages, compacting if over context budget
        if self.compactor.should_compact(context.messages):
            compacted_messages = await self.compactor.compact(context.messages)
            context.reset_messages(compacted_messages)

        messages = context.messages

        logger.info(f"Step with {len(messages)} messages")

        # Declaratively compute tools: eager schemas + any loaded integrations from trajectory
        tools = self.executor.get_schemas()
        loaded_tools = await self.integrations_tool.get_loaded_tools(messages)
        if loaded_tools:
            tools = tools + [t.schema for t in loaded_tools]

        streamed_messages: dict[str, Message] = {}
        async for message in self.vendor.inference(
            messages=messages,
            model=self.model,
            tools=tools,
        ):
            streamed_messages[message.id] = message
            # Update context as the message streams
            context.upsert_message(message)

        tool_calls = []

        for msg in streamed_messages.values():
            for content_node in msg.content:
                if content_node.HasField("tool_call"):
                    logger.info(
                        f"LLM requested tool call: {content_node.tool_call.tool} with input: {content_node.tool_call.input}"
                    )
                    tool_calls.append(content_node.tool_call)

        if not tool_calls:
            logger.info("No tool calls - conversation complete")
            return True  # Finished

        logger.info(f"Executing {len(tool_calls)}")

        extra_tools: dict[str, Tool] | None = (
            {t.name: t for t in loaded_tools} if loaded_tools else None
        )
        tool_responses = await self.executor.execute(tool_calls, extra_tools=extra_tools)

        context.upsert_message(
            Message(
                role=Role.TOOL,
                id=str(uuid4()),
                timestamp_ms=int(time() * 1000),
                content=[
                    ContentNode(tool_response=tool_response)
                    for tool_response in tool_responses
                ],
            )
        )

        return False  # Not finished yet

    async def run(self, context: Context) -> None:
        context.update_status(Status.STREAMING)

        # Update execution context with files_base_url from the request
        # This allows tools to return full URLs that the LLM can reference correctly
        if context.files_base_url:
            self.execution_context.files_base_url = context.files_base_url

        # Auto-init if no system message available
        if not any(m.role == Role.SYSTEM for m in context.messages):
            await self.init(context)

        # agent loop: repeatedly call LLM → execute tools → send results back
        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

            try:
                is_done = await self.step(context)
            except Exception as e:
                logger.error(f"Error during step execution: {e}")
                # Optionally, you could update the context with an error message here
                context.upsert_message_from_input(
                    role=Role.ASSISTANT,
                    content=[
                        ContentNode(
                            text=f"An error occurred during tool execution: {str(e)}"
                        )
                    ],
                )
                break

            logger.info("Step completed with is_done=%s", is_done)

            if is_done:
                logger.info("Agent signaled completion.")
                break

            if iteration == self.max_iterations - 1:
                logger.info(f"Reached max iterations ({self.max_iterations})")
                context.upsert_message_from_input(
                    role=Role.ASSISTANT,
                    content=[
                        ContentNode(
                            text=f"Reached maximum iterations ({self.max_iterations}). Would you like me to continue?"
                        )
                    ],
                )
                break

        context.update_status(Status.COMPLETED)
