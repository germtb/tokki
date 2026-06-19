import asyncio
import time
import logging
from asyncio import Queue
from typing import AsyncIterator

from uuid import uuid4

# Timeout for waiting on stream deltas (5 minutes)
STREAM_TIMEOUT_SECONDS = 300

# Import protobuf types directly from generated module
from . import tokki_pb2

Role = tokki_pb2.Role
Status = tokki_pb2.Status
ContentNode = tokki_pb2.ContentNode
ToolCall = tokki_pb2.ToolCall
ToolResponse = tokki_pb2.ToolResponse
ToolReview = tokki_pb2.ToolReview
Subagent = tokki_pb2.Subagent
Message = tokki_pb2.Message
Delta = tokki_pb2.Delta
ApprovalStatus = tokki_pb2.ApprovalStatus
LlmConfig = tokki_pb2.LlmConfig


logger = logging.getLogger(__name__)


class Context:
    def __init__(
        self,
        conversation_id: str,
        messages: list[Message],
        request_id: str,
        message_store=None,
        llm_config: LlmConfig | None = None,
        files_base_url: str | None = None,
        system_prompt: str | None = None,
        sender: str | None = None,
    ):
        self.conversation_id: str = conversation_id
        self.messages: list[Message] = messages
        self.status: Status = Status.INIT
        self.state_id: str = str(uuid4())
        self.request_id: str = request_id
        self.queue: Queue[Delta | None] = Queue()
        self.llm_config: LlmConfig | None = llm_config
        self.message_store = message_store
        # Base URL for file resources (e.g., "http://localhost:8080/files/{namespace}/{agentId}")
        # Used to construct full URLs for files created by tools
        self.files_base_url: str | None = files_base_url
        # System prompt injected by the server for persona-backed agents
        self.system_prompt: str | None = system_prompt
        # Set by the server for agent-to-agent calls (the calling agent's globalId)
        self.sender: str | None = sender
        # Maps tool call IDs to message IDs for easy lookup
        self.call_id_to_message: dict[str, Message] = {}

    def _publish_delta(self, messages: list[Message] | None = None) -> None:
        delta = Delta(
            request_id=self.request_id,
            messages=messages or [],
            state_id=self.state_id,
            status=self.status,
        )

        self.queue.put_nowait(delta)

    def close_stream(self) -> None:
        logger.info(f"[close_stream] Closing stream, queue_size={self.queue.qsize()}")
        self.queue.put_nowait(None)

    async def get_stream(self) -> AsyncIterator[Delta]:
        while True:
            try:
                delta = await asyncio.wait_for(
                    self.queue.get(), timeout=STREAM_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"[get_stream] Timed out after {STREAM_TIMEOUT_SECONDS}s waiting for delta, ending stream"
                )
                break

            # None signals the end of the stream
            if delta is None:
                logger.info(
                    "[get_stream] Received close sentinel (None), ending stream"
                )
                break

            yield delta

    def update_status(self, status: Status) -> None:
        self.status = status
        self.state_id = str(uuid4())
        self._publish_delta(messages=None)

    def reset_messages(self, messages: list[Message]) -> None:
        self.messages = []

        # Persist new messages to cold storage
        if self.message_store is not None:
            for message in messages:
                self.upsert_message(message)

        self._publish_delta(messages=messages)

    def upsert_message(self, message: Message) -> None:
        message_id = message.id

        updated_list = []
        pushed = False

        for msg in self.messages:
            if msg.id == message_id:
                updated_list.append(message)
                pushed = True
            else:
                updated_list.append(msg)

        if not pushed:
            updated_list.append(message)

        # Update messages list
        self.messages = updated_list
        self.state_id = str(uuid4())

        # Persist to SQLite if store is available
        if self.message_store is not None:
            self.message_store.save_message(self.conversation_id, message)

        for content_node in message.content:
            if content_node.HasField("tool_call"):
                tool_call = content_node.tool_call
                self.call_id_to_message[tool_call.call_id] = message

        # Publish delta with just this message
        self._publish_delta(messages=[message])

    def update_toolcall_timestamp(self, call_id: str, timestamp_ms: int) -> None:
        message = self.call_id_to_message.get(call_id)
        if not message:
            logger.warning(
                f"Could not find message for tool call ID {call_id} to update timestamp"
            )
            return
        for content_node in message.content:
            if (
                content_node.HasField("tool_call")
                and content_node.tool_call.call_id == call_id
            ):
                content_node.tool_call.call_timestamp_ms = timestamp_ms
                # Re-upsert to trigger updates
                self.upsert_message(message)
                logger.info(
                    f"Updated timestamp for tool call {call_id} to {timestamp_ms}"
                )
                break

    def upsert_message_from_input(
        self,
        role: Role,
        content: list[ContentNode],
        id: str | None = None,
        timestamp: int | None = None,
        parent_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        message_id = id or str(uuid4())

        # Create the message
        new_message = Message()
        new_message.role = role
        new_message.id = message_id

        # Set timestamp
        if timestamp is not None:
            new_message.timestamp_ms = timestamp
        else:
            new_message.timestamp_ms = int(time.time() * 1000)

        # Set parent_id if provided
        if parent_id is not None:
            new_message.parent_id = parent_id

        # Set log_type when provided (only meaningful for LOG role)
        if metadata is not None:
            for key, value in metadata.items():
                new_message.metadata[key] = value

        # Set content based on what's provided (in priority order)
        if content is not None:
            new_message.content.extend(content)

        self.upsert_message(new_message)

    # Approval Helper Methods
    def find_tool_call(self, call_id: str) -> ToolCall | None:
        """Find a tool call by its ID across all messages."""
        message = self.call_id_to_message.get(call_id)
        if not message:
            return None

        for content_node in message.content:
            if (
                content_node.HasField("tool_call")
                and content_node.tool_call.call_id == call_id
            ):
                return content_node.tool_call

        return None
