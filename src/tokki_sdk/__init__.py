"""Tokki - Simple agent protocol implementation.

This package provides a Python implementation of the tokki protocol,
matching the Rust implementation structure.
"""

# Import protobuf types
from . import tokki_pb2
from . import tokki_pb2_grpc

# Import core modules
from .agent import Agent
from .context import Context
from .service import AgentService, run_grpc_server
from .tools.memory import Compactor, MessageStore
from .persona import Persona

# Re-export commonly used types for convenience
__all__ = [
    # Core classes
    "Agent",
    "Context",
    "AgentServiceServicer",
    "AgentService",
    "AgentMetadata",
    "Status",
    "Role",
    "ErrorCode",
    "Message",
    "ContentNode",
    "ToolCall",
    "ToolResponse",
    "Subagent",
    "Instruction",
    "Request",
    "InitInstruction",
    "PushMessagesInstruction",
    "RunInstruction",
    "LlmConfig",
    "Attachment",
    "Compaction",
    "Compactor",
    "MessageStore",
    "Persona",
    "run_grpc_server",
]

Status: type[tokki_pb2.Status] = tokki_pb2.Status
AgentMetadata: type[tokki_pb2.AgentMetadata] = tokki_pb2.AgentMetadata
Role: type[tokki_pb2.Role] = tokki_pb2.Role
ErrorCode: type[tokki_pb2.ErrorCode] = tokki_pb2.ErrorCode
Message: type[tokki_pb2.Message] = tokki_pb2.Message
ContentNode: type[tokki_pb2.ContentNode] = tokki_pb2.ContentNode
ToolCall: type[tokki_pb2.ToolCall] = tokki_pb2.ToolCall
ToolResponse: type[tokki_pb2.ToolResponse] = tokki_pb2.ToolResponse
Subagent: type[tokki_pb2.Subagent] = tokki_pb2.Subagent
Instruction: type[tokki_pb2.Instruction] = tokki_pb2.Instruction
Request: type[tokki_pb2.Request] = tokki_pb2.Request
InitInstruction: type[tokki_pb2.InitInstruction] = tokki_pb2.InitInstruction
PushMessagesInstruction: type[tokki_pb2.PushMessagesInstruction] = (
    tokki_pb2.PushMessagesInstruction
)
RunInstruction: type[tokki_pb2.RunInstruction] = tokki_pb2.RunInstruction
LlmConfig: type[tokki_pb2.LlmConfig] = tokki_pb2.LlmConfig
Attachment: type[tokki_pb2.Attachment] = tokki_pb2.Attachment
Compaction: type[tokki_pb2.Compaction] = tokki_pb2.Compaction
AgentServiceServicer: type[tokki_pb2_grpc.AgentServiceServicer] = (
    tokki_pb2_grpc.AgentServiceServicer
)

__version__ = "0.1.0"
