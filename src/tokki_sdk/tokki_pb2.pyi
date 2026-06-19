from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INIT: _ClassVar[Status]
    STREAMING: _ClassVar[Status]
    COMPLETED: _ClassVar[Status]
    FAILED: _ClassVar[Status]
    CANCELLED: _ClassVar[Status]
    PAUSED: _ClassVar[Status]
    WAITING_FOR_APPROVAL: _ClassVar[Status]
    WAITING_FOR_TOOL: _ClassVar[Status]

class Role(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER: _ClassVar[Role]
    ASSISTANT: _ClassVar[Role]
    SYSTEM: _ClassVar[Role]
    TOOL: _ClassVar[Role]

class LogLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INFO: _ClassVar[LogLevel]
    WARNING: _ClassVar[LogLevel]
    ERROR: _ClassVar[LogLevel]
    DEBUG: _ClassVar[LogLevel]

class ApprovalStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NOT_REQUIRED: _ClassVar[ApprovalStatus]
    PENDING: _ClassVar[ApprovalStatus]
    APPROVED: _ClassVar[ApprovalStatus]
    REJECTED: _ClassVar[ApprovalStatus]
    AUTO_APPROVED: _ClassVar[ApprovalStatus]

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[ErrorCode]
    DECODE_ERROR: _ClassVar[ErrorCode]
    INTERNAL_ERROR: _ClassVar[ErrorCode]
    TIMEOUT: _ClassVar[ErrorCode]
    RUNTIME_ERROR: _ClassVar[ErrorCode]
    AUTHENTICATION_ERROR: _ClassVar[ErrorCode]
    SESSION_NOT_FOUND: _ClassVar[ErrorCode]
INIT: Status
STREAMING: Status
COMPLETED: Status
FAILED: Status
CANCELLED: Status
PAUSED: Status
WAITING_FOR_APPROVAL: Status
WAITING_FOR_TOOL: Status
USER: Role
ASSISTANT: Role
SYSTEM: Role
TOOL: Role
INFO: LogLevel
WARNING: LogLevel
ERROR: LogLevel
DEBUG: LogLevel
NOT_REQUIRED: ApprovalStatus
PENDING: ApprovalStatus
APPROVED: ApprovalStatus
REJECTED: ApprovalStatus
AUTO_APPROVED: ApprovalStatus
UNKNOWN: ErrorCode
DECODE_ERROR: ErrorCode
INTERNAL_ERROR: ErrorCode
TIMEOUT: ErrorCode
RUNTIME_ERROR: ErrorCode
AUTHENTICATION_ERROR: ErrorCode
SESSION_NOT_FOUND: ErrorCode

class Attachment(_message.Message):
    __slots__ = ("mime_type", "name", "description", "url", "data", "cloud_ref")
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    CLOUD_REF_FIELD_NUMBER: _ClassVar[int]
    mime_type: str
    name: str
    description: str
    url: str
    data: bytes
    cloud_ref: str
    def __init__(self, mime_type: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., url: _Optional[str] = ..., data: _Optional[bytes] = ..., cloud_ref: _Optional[str] = ...) -> None: ...

class Thought(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class Log(_message.Message):
    __slots__ = ("level", "message", "timestamp_ms", "category", "source", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    level: LogLevel
    message: str
    timestamp_ms: int
    category: str
    source: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, level: _Optional[_Union[LogLevel, str]] = ..., message: _Optional[str] = ..., timestamp_ms: _Optional[int] = ..., category: _Optional[str] = ..., source: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class Compaction(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class ContentNode(_message.Message):
    __slots__ = ("text", "thought", "attachment", "tool_call", "tool_response", "tool_review", "subagent", "log", "compaction")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    THOUGHT_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALL_FIELD_NUMBER: _ClassVar[int]
    TOOL_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    TOOL_REVIEW_FIELD_NUMBER: _ClassVar[int]
    SUBAGENT_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    COMPACTION_FIELD_NUMBER: _ClassVar[int]
    text: str
    thought: Thought
    attachment: Attachment
    tool_call: ToolCall
    tool_response: ToolResponse
    tool_review: ToolReview
    subagent: Subagent
    log: Log
    compaction: Compaction
    def __init__(self, text: _Optional[str] = ..., thought: _Optional[_Union[Thought, _Mapping]] = ..., attachment: _Optional[_Union[Attachment, _Mapping]] = ..., tool_call: _Optional[_Union[ToolCall, _Mapping]] = ..., tool_response: _Optional[_Union[ToolResponse, _Mapping]] = ..., tool_review: _Optional[_Union[ToolReview, _Mapping]] = ..., subagent: _Optional[_Union[Subagent, _Mapping]] = ..., log: _Optional[_Union[Log, _Mapping]] = ..., compaction: _Optional[_Union[Compaction, _Mapping]] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("call_id", "tool", "action", "input", "requires_approval", "call_timestamp_ms")
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_APPROVAL_FIELD_NUMBER: _ClassVar[int]
    CALL_TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    call_id: str
    tool: str
    action: str
    input: str
    requires_approval: bool
    call_timestamp_ms: int
    def __init__(self, call_id: _Optional[str] = ..., tool: _Optional[str] = ..., action: _Optional[str] = ..., input: _Optional[str] = ..., requires_approval: bool = ..., call_timestamp_ms: _Optional[int] = ...) -> None: ...

class ContentAnnotations(_message.Message):
    __slots__ = ("audience", "priority")
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    audience: _containers.RepeatedScalarFieldContainer[str]
    priority: float
    def __init__(self, audience: _Optional[_Iterable[str]] = ..., priority: _Optional[float] = ...) -> None: ...

class TextContent(_message.Message):
    __slots__ = ("text", "annotations")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    text: str
    annotations: ContentAnnotations
    def __init__(self, text: _Optional[str] = ..., annotations: _Optional[_Union[ContentAnnotations, _Mapping]] = ...) -> None: ...

class ImageContent(_message.Message):
    __slots__ = ("data", "mime_type", "annotations")
    DATA_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    data: str
    mime_type: str
    annotations: ContentAnnotations
    def __init__(self, data: _Optional[str] = ..., mime_type: _Optional[str] = ..., annotations: _Optional[_Union[ContentAnnotations, _Mapping]] = ...) -> None: ...

class AudioContent(_message.Message):
    __slots__ = ("data", "mime_type", "annotations")
    DATA_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    data: str
    mime_type: str
    annotations: ContentAnnotations
    def __init__(self, data: _Optional[str] = ..., mime_type: _Optional[str] = ..., annotations: _Optional[_Union[ContentAnnotations, _Mapping]] = ...) -> None: ...

class ResourceLink(_message.Message):
    __slots__ = ("uri", "name", "title", "description", "mime_type", "size", "annotations")
    URI_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    uri: str
    name: str
    title: str
    description: str
    mime_type: str
    size: int
    annotations: ContentAnnotations
    def __init__(self, uri: _Optional[str] = ..., name: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., mime_type: _Optional[str] = ..., size: _Optional[int] = ..., annotations: _Optional[_Union[ContentAnnotations, _Mapping]] = ...) -> None: ...

class EmbeddedResource(_message.Message):
    __slots__ = ("uri", "mime_type", "text", "blob", "annotations")
    URI_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    BLOB_FIELD_NUMBER: _ClassVar[int]
    ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    uri: str
    mime_type: str
    text: str
    blob: bytes
    annotations: ContentAnnotations
    def __init__(self, uri: _Optional[str] = ..., mime_type: _Optional[str] = ..., text: _Optional[str] = ..., blob: _Optional[bytes] = ..., annotations: _Optional[_Union[ContentAnnotations, _Mapping]] = ...) -> None: ...

class ToolResultContentNode(_message.Message):
    __slots__ = ("text", "image", "audio", "resource_link", "embedded_resource")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    AUDIO_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_LINK_FIELD_NUMBER: _ClassVar[int]
    EMBEDDED_RESOURCE_FIELD_NUMBER: _ClassVar[int]
    text: TextContent
    image: ImageContent
    audio: AudioContent
    resource_link: ResourceLink
    embedded_resource: EmbeddedResource
    def __init__(self, text: _Optional[_Union[TextContent, _Mapping]] = ..., image: _Optional[_Union[ImageContent, _Mapping]] = ..., audio: _Optional[_Union[AudioContent, _Mapping]] = ..., resource_link: _Optional[_Union[ResourceLink, _Mapping]] = ..., embedded_resource: _Optional[_Union[EmbeddedResource, _Mapping]] = ...) -> None: ...

class ToolResultContent(_message.Message):
    __slots__ = ("nodes", "is_error")
    NODES_FIELD_NUMBER: _ClassVar[int]
    IS_ERROR_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[ToolResultContentNode]
    is_error: bool
    def __init__(self, nodes: _Optional[_Iterable[_Union[ToolResultContentNode, _Mapping]]] = ..., is_error: bool = ...) -> None: ...

class ToolResponse(_message.Message):
    __slots__ = ("call_id", "tool", "action", "content")
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    call_id: str
    tool: str
    action: str
    content: ToolResultContent
    def __init__(self, call_id: _Optional[str] = ..., tool: _Optional[str] = ..., action: _Optional[str] = ..., content: _Optional[_Union[ToolResultContent, _Mapping]] = ...) -> None: ...

class ToolReview(_message.Message):
    __slots__ = ("call_id", "decision", "reason")
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    call_id: str
    decision: ApprovalStatus
    reason: str
    def __init__(self, call_id: _Optional[str] = ..., decision: _Optional[_Union[ApprovalStatus, str]] = ..., reason: _Optional[str] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("role", "id", "parent_id", "timestamp_ms", "content", "metadata", "conversation_id")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ROLE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    role: Role
    id: str
    parent_id: str
    timestamp_ms: int
    content: _containers.RepeatedCompositeFieldContainer[ContentNode]
    metadata: _containers.ScalarMap[str, str]
    conversation_id: str
    def __init__(self, role: _Optional[_Union[Role, str]] = ..., id: _Optional[str] = ..., parent_id: _Optional[str] = ..., timestamp_ms: _Optional[int] = ..., content: _Optional[_Iterable[_Union[ContentNode, _Mapping]]] = ..., metadata: _Optional[_Mapping[str, str]] = ..., conversation_id: _Optional[str] = ...) -> None: ...

class Subagent(_message.Message):
    __slots__ = ("id", "request_id", "messages", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    id: str
    request_id: str
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, id: _Optional[str] = ..., request_id: _Optional[str] = ..., messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class InitInstruction(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PushMessagesInstruction(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ...) -> None: ...

class LlmConfig(_message.Message):
    __slots__ = ("temperature", "max_tokens", "top_p", "top_k", "stop_sequences")
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TOP_P_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    STOP_SEQUENCES_FIELD_NUMBER: _ClassVar[int]
    temperature: float
    max_tokens: int
    top_p: float
    top_k: int
    stop_sequences: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, temperature: _Optional[float] = ..., max_tokens: _Optional[int] = ..., top_p: _Optional[float] = ..., top_k: _Optional[int] = ..., stop_sequences: _Optional[_Iterable[str]] = ...) -> None: ...

class RunInstruction(_message.Message):
    __slots__ = ("config",)
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    config: LlmConfig
    def __init__(self, config: _Optional[_Union[LlmConfig, _Mapping]] = ...) -> None: ...

class Instruction(_message.Message):
    __slots__ = ("push_messages", "run")
    PUSH_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    RUN_FIELD_NUMBER: _ClassVar[int]
    push_messages: PushMessagesInstruction
    run: RunInstruction
    def __init__(self, push_messages: _Optional[_Union[PushMessagesInstruction, _Mapping]] = ..., run: _Optional[_Union[RunInstruction, _Mapping]] = ...) -> None: ...

class MessageFilter(_message.Message):
    __slots__ = ("after_id", "include", "exclude")
    AFTER_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_FIELD_NUMBER: _ClassVar[int]
    EXCLUDE_FIELD_NUMBER: _ClassVar[int]
    after_id: str
    include: _containers.RepeatedScalarFieldContainer[Role]
    exclude: _containers.RepeatedScalarFieldContainer[Role]
    def __init__(self, after_id: _Optional[str] = ..., include: _Optional[_Iterable[_Union[Role, str]]] = ..., exclude: _Optional[_Iterable[_Union[Role, str]]] = ...) -> None: ...

class Request(_message.Message):
    __slots__ = ("request_id", "conversation_id", "instructions", "filter", "metadata", "sender", "depth")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTIONS_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SENDER_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    conversation_id: str
    instructions: _containers.RepeatedCompositeFieldContainer[Instruction]
    filter: MessageFilter
    metadata: _containers.ScalarMap[str, str]
    sender: str
    depth: int
    def __init__(self, request_id: _Optional[str] = ..., conversation_id: _Optional[str] = ..., instructions: _Optional[_Iterable[_Union[Instruction, _Mapping]]] = ..., filter: _Optional[_Union[MessageFilter, _Mapping]] = ..., metadata: _Optional[_Mapping[str, str]] = ..., sender: _Optional[str] = ..., depth: _Optional[int] = ...) -> None: ...

class Delta(_message.Message):
    __slots__ = ("request_id", "messages", "state_id", "status", "error", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    STATE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    state_id: str
    status: Status
    error: ErrorCode
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, request_id: _Optional[str] = ..., messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., state_id: _Optional[str] = ..., status: _Optional[_Union[Status, str]] = ..., error: _Optional[_Union[ErrorCode, str]] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class AgentMetadata(_message.Message):
    __slots__ = ("id", "name", "description", "welcome_message", "example_queries")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    WELCOME_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EXAMPLE_QUERIES_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    welcome_message: str
    example_queries: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., welcome_message: _Optional[str] = ..., example_queries: _Optional[_Iterable[str]] = ...) -> None: ...

class PingRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PingResponse(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class GetMetadataRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMetadataResponse(_message.Message):
    __slots__ = ("metadata",)
    METADATA_FIELD_NUMBER: _ClassVar[int]
    metadata: AgentMetadata
    def __init__(self, metadata: _Optional[_Union[AgentMetadata, _Mapping]] = ...) -> None: ...

class ConversationSnippet(_message.Message):
    __slots__ = ("conversation_id", "snippet", "created_at_ms", "updated_at_ms", "message_count")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    SNIPPET_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    snippet: str
    created_at_ms: int
    updated_at_ms: int
    message_count: int
    def __init__(self, conversation_id: _Optional[str] = ..., snippet: _Optional[str] = ..., created_at_ms: _Optional[int] = ..., updated_at_ms: _Optional[int] = ..., message_count: _Optional[int] = ...) -> None: ...

class ListConversationsRequest(_message.Message):
    __slots__ = ("limit", "offset")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    limit: int
    offset: int
    def __init__(self, limit: _Optional[int] = ..., offset: _Optional[int] = ...) -> None: ...

class ListConversationsResponse(_message.Message):
    __slots__ = ("conversations",)
    CONVERSATIONS_FIELD_NUMBER: _ClassVar[int]
    conversations: _containers.RepeatedCompositeFieldContainer[ConversationSnippet]
    def __init__(self, conversations: _Optional[_Iterable[_Union[ConversationSnippet, _Mapping]]] = ...) -> None: ...

class LoadMessagesRequest(_message.Message):
    __slots__ = ("conversation_id", "limit", "offset")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    limit: int
    offset: int
    def __init__(self, conversation_id: _Optional[str] = ..., limit: _Optional[int] = ..., offset: _Optional[int] = ...) -> None: ...

class LoadMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ...) -> None: ...

class DeleteConversationRequest(_message.Message):
    __slots__ = ("conversation_id",)
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    def __init__(self, conversation_id: _Optional[str] = ...) -> None: ...

class DeleteConversationResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...
