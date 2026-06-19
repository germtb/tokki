import asyncio
import logging
import os
import sys
import time
from typing import AsyncIterator
from uuid import uuid4

from tokki_sdk.agent import Agent
from tokki_sdk.tools.memory import MessageStore

import grpc  # type: ignore[import-untyped]
from grpc.aio import ServerInterceptor  # type: ignore[import-untyped]
from grpc import aio
from .tokki_pb2_grpc import add_AgentServiceServicer_to_server
from .tokki_pb2 import GetMetadataResponse, AgentMetadata
from .tokki_pb2 import (
    Log,
    LogLevel,
    Delta,
    AgentMetadata,
    Request,
    Status,
    ErrorCode,
    PingResponse,
    ListConversationsResponse,
    LoadMessagesResponse,
    DeleteConversationResponse,
)
from .tokki_pb2_grpc import AgentServiceServicer
from .context import ContentNode, Context, Role

logger = logging.getLogger(__name__)


class ParentWatcher:
    """Monitors parent process and exits when it dies (prevents orphaned agents)."""

    def __init__(self):
        self._parent_pid = os.getppid()
        self._task: asyncio.Task | None = None

    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._watch())

    async def _watch(self):
        while True:
            await asyncio.sleep(1)
            current_parent = os.getppid()
            if current_parent != self._parent_pid or current_parent == 1:
                logger.info(f"Parent process died, exiting")
                os._exit(0)


class IdleShutdown:
    """Automatically shuts down the agent after a period of inactivity."""

    def __init__(self, timeout_seconds: int):
        self.timeout = timeout_seconds
        self._last_activity = time.monotonic()
        self._task: asyncio.Task | None = None

    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._watch())

    def touch(self):
        """Reset the idle timer (called on each request)."""
        self._last_activity = time.monotonic()

    async def _watch(self):
        while True:
            await asyncio.sleep(1)
            idle = time.monotonic() - self._last_activity
            if idle >= self.timeout:
                logger.info(f"Idle timeout reached ({self.timeout}s), exiting")
                os._exit(0)


class ActivityInterceptor(ServerInterceptor):
    """gRPC interceptor that resets the idle timer on every request."""

    def __init__(self, idle_shutdown: IdleShutdown):
        self.idle_shutdown = idle_shutdown

    async def intercept_service(self, continuation, handler_call_details):
        self.idle_shutdown.touch()
        return await continuation(handler_call_details)


def get_idle_timeout_seconds() -> int:
    try:
        return int(os.environ.get("IDLE_TIMEOUT_SECONDS", "300"))
    except ValueError:
        return 300


async def run_grpc_server(service: AgentServiceServicer):
    """Run the gRPC server with the agent service."""
    cloud_provider = os.environ.get("CLOUD_PROVIDER")
    running_locally = not cloud_provider

    if running_locally:
        port = 0
        timeout_seconds = 0
        parent_watcher = ParentWatcher()
        parent_watcher.start()
    else:
        port = 50051
        timeout_seconds = get_idle_timeout_seconds()
        logger.info(
            f"Running on cloud ({cloud_provider}) with idle timeout: {timeout_seconds}s"
        )

    compression_options = [
        ("grpc.default_compression_algorithm", grpc.Compression.Gzip),
        ("grpc.default_compression_level", grpc.Compression.Gzip),
    ]

    idle_shutdown: IdleShutdown | None = None
    if timeout_seconds > 0:
        idle_shutdown = IdleShutdown(timeout_seconds=timeout_seconds)
        idle_shutdown.start()
        server = aio.server(
            interceptors=[ActivityInterceptor(idle_shutdown)],
            compression=grpc.Compression.Gzip,
            options=compression_options,
        )
    else:
        server = aio.server(
            compression=grpc.Compression.Gzip,
            options=compression_options,
        )

    add_AgentServiceServicer_to_server(service, server)
    actual_port = server.add_insecure_port(f"[::]:{port}")

    await server.start()
    logger.info(f"gRPC server running on port {actual_port}")

    if running_locally:
        print(f"TOKKI_PORT={actual_port}", file=sys.stdout, flush=True)

    if idle_shutdown is not None:
        idle_shutdown.touch()

    await server.wait_for_termination()


class AgentService(AgentServiceServicer):
    def __init__(
        self,
        agent: Agent,
        metadata: AgentMetadata,
        workspace_dir: str | None = None,
    ):
        self.agent = agent
        self.metadata: AgentMetadata = metadata
        # Determine workspace directory
        if workspace_dir:
            self._workspace_dir = workspace_dir
        elif os.environ.get("CLOUD_PROVIDER"):
            self._workspace_dir = "/app/workspace"
        else:
            self._workspace_dir = os.getcwd()
        self.message_store = MessageStore(workspace_dir=self._workspace_dir)

    async def _execute(
        self,
        request: Request,
        context: Context,
    ) -> None:
        context._publish_delta(messages=None)

        try:
            for instruction in request.instructions:
                instruction_type = instruction.WhichOneof("instruction")

                if instruction_type == "push_messages":
                    for msg in instruction.push_messages.messages:
                        context.upsert_message(msg)
                elif instruction_type == "run":
                    if instruction.run.HasField("config"):
                        context.llm_config = instruction.run.config
                    await self.agent.run(context)
                elif instruction_type == "init":
                    await self.agent.init(context)
                else:
                    raise ValueError(f"Unknown instruction type: {instruction_type}")
        except Exception as err:
            logger.error(f"Error during execution: {err}", exc_info=True)
            try:
                context.upsert_message_from_input(
                    role=Role.ASSISTANT,
                    content=[
                        ContentNode(
                            log=Log(
                                level=LogLevel.ERROR,
                                message=f"{str(err)}",
                            )
                        )
                    ],
                )
                context.update_status(Status.FAILED)
            except Exception:
                pass

    async def Ping(self, request, context):
        return PingResponse(ok=True)

    async def GetMetadata(self, request, context):
        return GetMetadataResponse(metadata=self.metadata)

    async def Execute(self, request: Request, context) -> AsyncIterator[Delta]:
        """Execute returns a stream of deltas (changed from unary Response)."""
        conversation_id = request.conversation_id or str(uuid4())
        existing_messages = self.message_store.load_messages(conversation_id)

        files_base_url = (
            request.metadata.get("files_base_url") if request.metadata else None
        )
        system_prompt = (
            request.metadata.get("system_prompt") if request.metadata else None
        )
        sender = request.sender if request.HasField("sender") else None
        ctx = Context(
            conversation_id=conversation_id,
            messages=existing_messages,
            request_id=request.request_id,
            message_store=self.message_store,
            files_base_url=files_base_url,
            system_prompt=system_prompt,
            sender=sender,
        )

        async def execute_with_fallback_close():
            try:
                await self._execute(request, ctx)
            except Exception as e:
                logger.error(f"Error during execution: {e}", exc_info=True)
                ctx.update_status(Status.FAILED)

        try:
            task = asyncio.create_task(execute_with_fallback_close())

            async for delta in ctx.get_stream():
                yield delta

            await task
        except Exception as e:
            logger.error(f"Error during Execute: {e}", exc_info=True)
            yield Delta(
                request_id=request.request_id,
                error=ErrorCode.INTERNAL_ERROR,
                metadata={"error_message": str(e)},
            )

    async def Stream(self, request: Request, context) -> AsyncIterator[Delta]:
        conversation_id = request.conversation_id or str(uuid4())
        existing_messages = self.message_store.load_messages(conversation_id)

        files_base_url = (
            request.metadata.get("files_base_url") if request.metadata else None
        )
        system_prompt = (
            request.metadata.get("system_prompt") if request.metadata else None
        )
        sender = request.sender if request.HasField("sender") else None
        ctx = Context(
            conversation_id=conversation_id,
            messages=existing_messages,
            request_id=request.request_id,
            message_store=self.message_store,
            files_base_url=files_base_url,
            system_prompt=system_prompt,
            sender=sender,
        )

        async def execute_with_fallback_close():
            try:
                await self._execute(request, ctx)
            except Exception as e:
                logger.error(f"Error during execution: {e}", exc_info=True)
                ctx.update_status(Status.FAILED)

        try:
            task = asyncio.create_task(execute_with_fallback_close())

            async for delta in ctx.get_stream():
                yield delta

            await task
        except Exception as e:
            logger.error(f"Error during Stream: {e}", exc_info=True)
            yield Delta(
                request_id=request.request_id,
                error=ErrorCode.INTERNAL_ERROR,
                metadata={"error_message": str(e)},
            )

    async def ListConversations(self, request, context):
        limit = request.limit if request.HasField("limit") else None
        offset = request.offset if request.HasField("offset") else None
        conversations = self.message_store.list_conversations(
            limit=limit, offset=offset
        )
        return ListConversationsResponse(conversations=conversations)

    async def LoadMessages(self, request, context):
        limit = request.limit if request.HasField("limit") else None
        offset = request.offset if request.HasField("offset") else None
        messages = self.message_store.load_messages(
            request.conversation_id, limit=limit, offset=offset
        )
        return LoadMessagesResponse(messages=messages)

    async def DeleteConversation(self, request, context):
        success = self.message_store.delete_conversation(request.conversation_id)
        return DeleteConversationResponse(success=success)
