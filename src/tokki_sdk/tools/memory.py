"""
Agent memory management: message storage, compaction, and recall.

Messages are stored in a local SQLite database, tagged by conversation_id.
The agent owns all conversation data. The Compactor manages context window
limits by only loading recent messages into the LLM context.
"""

import logging
import sqlite3
from time import time
from uuid import uuid4
import os

from tokki_sdk.tools.base import Tool
from tokki_sdk.tools.helpers import text_result, error_result
from tokki_sdk.vendor.base import Vendor, content_to_str, estimate_tokens

from .. import tokki_pb2

Message = tokki_pb2.Message
ContentNode = tokki_pb2.ContentNode
ConversationSnippet = tokki_pb2.ConversationSnippet
Role = tokki_pb2.Role
Compaction = tokki_pb2.Compaction

logger = logging.getLogger(__name__)



_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    proto BLOB NOT NULL,
    content_text TEXT,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id, timestamp_ms);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    message_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at_ms DESC);
"""


def _get_db_path(workspace_dir: str) -> str:
    archive_dir = os.path.join(workspace_dir, ".archives")
    os.makedirs(archive_dir, exist_ok=True)
    return os.path.join(archive_dir, "archive.db")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


# ---------------------------------------------------------------------------
# MessageStore
# ---------------------------------------------------------------------------


class MessageStore:
    """Stores and retrieves conversation messages in SQLite."""

    def __init__(self, workspace_dir: str = "/workspace"):
        self.workspace_dir = workspace_dir
        self._db_path = _get_db_path(workspace_dir)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            _init_db(conn)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save_message(self, conversation_id: str, message: Message) -> None:
        """Persist a message and update conversation metadata."""
        conn = self._connect()
        try:
            # Check if this is a new message or an update
            existing = conn.execute(
                "SELECT 1 FROM messages WHERE message_id = ?",
                (message.id,),
            ).fetchone()
            is_new = existing is None

            content_text = content_to_str(message.content) or None
            conn.execute(
                "INSERT OR REPLACE INTO messages "
                "(message_id, conversation_id, role, timestamp_ms, proto, content_text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message.id,
                    conversation_id,
                    int(message.role),
                    message.timestamp_ms,
                    message.SerializeToString(),
                    content_text,
                ),
            )

            # Extract snippet from text content
            snippet = ""
            if content_text and message.role in (Role.USER, Role.ASSISTANT):
                snippet = content_text[:100]

            now_ms = int(time() * 1000)

            if is_new:
                conn.execute(
                    "INSERT INTO conversations (conversation_id, created_at_ms, updated_at_ms, snippet, message_count) "
                    "VALUES (?, ?, ?, ?, 1) "
                    "ON CONFLICT(conversation_id) DO UPDATE SET "
                    "updated_at_ms = ?, "
                    "snippet = CASE WHEN ? != '' THEN ? ELSE snippet END, "
                    "message_count = message_count + 1",
                    (
                        conversation_id,
                        now_ms,
                        now_ms,
                        snippet,
                        now_ms,
                        snippet,
                        snippet,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at_ms = ?, "
                    "snippet = CASE WHEN ? != '' THEN ? ELSE snippet END "
                    "WHERE conversation_id = ?",
                    (now_ms, snippet, snippet, conversation_id),
                )
            conn.commit()
        finally:
            conn.close()

    def load_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Message]:
        """Load messages for a conversation, ordered by timestamp."""
        conn = self._connect()
        try:
            query = "SELECT proto FROM messages WHERE conversation_id = ? ORDER BY timestamp_ms"
            params: list = [conversation_id]

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)

            rows = conn.execute(query, params).fetchall()
            messages = []
            for (proto_bytes,) in rows:
                msg = Message()
                msg.ParseFromString(proto_bytes)
                messages.append(msg)
            return messages
        finally:
            conn.close()

    def list_conversations(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ConversationSnippet]:
        """List conversations ordered by updated_at_ms descending."""
        conn = self._connect()
        try:
            query = "SELECT conversation_id, created_at_ms, updated_at_ms, snippet, message_count FROM conversations ORDER BY updated_at_ms DESC"
            params: list = []

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)

            rows = conn.execute(query, params).fetchall()
            snippets = []
            for row in rows:
                snippets.append(
                    ConversationSnippet(
                        conversation_id=row[0],
                        created_at_ms=row[1],
                        updated_at_ms=row[2],
                        snippet=row[3] or "",
                        message_count=row[4],
                    )
                )
            return snippets
        finally:
            conn.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all messages and metadata for a conversation."""
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.commit()
            return True
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Compactor
# ---------------------------------------------------------------------------


_SUMMARIZATION_PROMPT = """\
Summarize the following conversation history concisely. Preserve key facts, \
decisions, and context that would be needed to continue the conversation. \
Be brief but complete.

"""


class Compactor:
    """Manages context window limits by summarizing old messages."""

    def __init__(
        self,
        max_context_tokens: int,
        vendor: Vendor,
        model: str,
        threshold: float = 0.8,
    ):
        self.max_context_tokens = max_context_tokens
        self.vendor = vendor
        self.threshold = threshold
        self.model = model

    def should_compact(self, messages: list[Message]) -> bool:
        total_tokens = estimate_tokens(messages)
        budget = int(self.max_context_tokens * self.threshold)
        if total_tokens > budget:
            logger.info(
                f"Context over budget: ~{total_tokens} tokens > {budget} (threshold {self.threshold}). Compacting."
            )
        return total_tokens > budget

    async def compact(self, messages: list[Message]) -> list[Message]:
        system_msgs = []
        non_system_msgs = []
        pending_tool_calls = {}

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_msgs.append(msg)
            else:
                non_system_msgs.append(msg)

            for node in msg.content:
                if node.HasField("tool_call"):
                    pending_tool_calls[node.tool_call.call_id] = node.tool_call
                elif node.HasField("tool_response"):
                    # Remove from pending if we see a response
                    pending_tool_calls.pop(node.tool_response.call_id, None)

        # Summarize old messages
        summary = await self._summarize(non_system_msgs)

        # Build compaction message
        compaction_msg = Message(
            role=Role.USER,
            id=str(uuid4()),
            timestamp_ms=int(time() * 1000),
            content=[
                ContentNode(compaction=Compaction(text=summary)),
            ]
            + [
                ContentNode(tool_call=tool_call)
                for tool_call in pending_tool_calls.values()
            ],
        )

        result = system_msgs + [compaction_msg]
        logger.info(
            f"Compacted {len(non_system_msgs)} old messages into summary. "
            f"Context: {len(result)} messages, ~{estimate_tokens(result)} tokens"
        )
        return result

    async def _summarize(self, messages: list[Message]) -> str:
        """Call a cheap model to summarize conversation history."""

        result = await self.vendor.inference_no_streaming(
            messages=messages
            + [
                Message(
                    role=Role.USER,
                    id=str(uuid4()),
                    timestamp_ms=int(time() * 1000),
                    content=[ContentNode(text=_SUMMARIZATION_PROMPT)],
                )
            ],
            model=self.model,
        )

        return (
            result.content[0].text
            if result.content and result.content[0].HasField("text")
            else ""
        )


class Memory(Tool):
    """Retrieves conversation messages from the SQLite store."""

    @property
    def name(self) -> str:
        return "memory"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "memory",
                "description": (
                    "Retrieve conversation messages from the message store. Use "
                    "this tool to recall earlier messages from the current or other "
                    "conversations when you need more context. "
                    "You can query by message_id, by time range (from_timestamp_ms/to_timestamp_ms), "
                    "by conversation_id, or retrieve all messages by passing no parameters."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "A specific message ID to retrieve.",
                        },
                        "conversation_id": {
                            "type": "string",
                            "description": "Filter messages to a specific conversation.",
                        },
                        "from_timestamp_ms": {
                            "type": "integer",
                            "description": "Start of the time range (epoch milliseconds, inclusive).",
                        },
                        "to_timestamp_ms": {
                            "type": "integer",
                            "description": "End of the time range (epoch milliseconds, inclusive).",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of messages to retrieve.",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Number of messages to skip before starting to return results.",
                        },
                    },
                },
            },
        }

    async def execute(self, input: dict):
        db_path = _get_db_path(str(self.context.workspace_dir))

        if not os.path.exists(db_path):
            return error_result("No messages found.")

        message_id = (
            input.get("message_id", "").strip() if input.get("message_id") else None
        )
        conversation_id = (
            input.get("conversation_id", "").strip()
            if input.get("conversation_id")
            else None
        )
        limit = input.get("limit") or 10
        offset = input.get("offset") or 0
        from_ts = input.get("from_timestamp_ms")
        to_ts = input.get("to_timestamp_ms")

        try:
            conn = sqlite3.connect(db_path)
            try:
                if message_id:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE message_id = ? LIMIT ? OFFSET ?",
                        (message_id, limit, offset),
                    ).fetchall()
                elif conversation_id and from_ts is not None and to_ts is not None:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE conversation_id = ? AND timestamp_ms BETWEEN ? AND ? ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (conversation_id, from_ts, to_ts, limit, offset),
                    ).fetchall()
                elif conversation_id:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE conversation_id = ? ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (conversation_id, limit, offset),
                    ).fetchall()
                elif from_ts is not None and to_ts is not None:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE timestamp_ms BETWEEN ? AND ? ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (from_ts, to_ts, limit, offset),
                    ).fetchall()
                elif from_ts is not None:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE timestamp_ms >= ? ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (from_ts, limit, offset),
                    ).fetchall()
                elif to_ts is not None:
                    rows = conn.execute(
                        "SELECT proto FROM messages WHERE timestamp_ms <= ? ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (to_ts, limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT proto FROM messages ORDER BY timestamp_ms LIMIT ? OFFSET ?",
                        (limit, offset),
                    ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            return error_result(f"Failed to read messages: {e}")

        if not rows:
            return text_result("No matching messages found.")

        lines = []
        for (proto_bytes,) in rows:
            msg = Message()
            msg.ParseFromString(proto_bytes)
            role = Role.Name(msg.role)
            content = content_to_str(msg.content)
            if content:
                lines.append(f"[{role}]: {content}")

        if not lines:
            return text_result("Messages have no text content.")

        transcript = "\n\n".join(lines)
        return text_result(f"Conversation ({len(rows)} messages):\n\n{transcript}")
