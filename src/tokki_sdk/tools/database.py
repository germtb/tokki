"""SQLite database tool for agent interactions."""

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Tool, ToolError
from .helpers import text_result

if TYPE_CHECKING:
    from .context import ExecutionContext


class Database(Tool):
    """Tool for interacting with a local SQLite database.

    Each instance represents a single database with a semantic tool name.

    Example:
        users_db = Database(ctx, name="users_db", db_file="users.db")
    """

    def __init__(
        self,
        context: "ExecutionContext",
        name: str,
        db_file: str = "data.db",
        description: str | None = None,
        approval_required: bool = False,
    ):
        """Initialize a Database tool.

        Args:
            context: The execution context providing workspace directory.
            name: The tool name (e.g., "users_db", "analytics_db").
            db_file: The database filename in the workspace directory.
            description: Optional custom description. If not provided, a default is used.
            approval_required: Whether tool execution requires user approval.
        """
        super().__init__(context, approval_required)
        self._name = name
        self._description = description

        # Ensure db_file is safe (no path traversal)
        if "/" in db_file or "\\" in db_file or ".." in db_file:
            raise ValueError("db_file cannot contain path separators or '..'")

        # Ensure .db extension
        if not db_file.endswith(".db"):
            db_file = f"{db_file}.db"

        self._db_path = context.workspace_dir / db_file

    @property
    def name(self) -> str:
        return self._name

    @property
    def allow_a2a(self) -> bool:
        return False

    @property
    def schema(self) -> dict:
        description = self._description or (
            f"Execute SQL queries on the '{self._name}' SQLite database. "
            "Supports SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, and other SQL statements."
        )
        return {
            "type": "function",
            "function": {
                "name": self._name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to execute. Can be any valid SQLite SQL statement.",
                        },
                        "params": {
                            "type": "array",
                            "items": {},
                            "description": "Optional list of parameters for parameterized queries. Use ? placeholders in the query.",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(self, input: dict):
        query = input.get("query")
        params = input.get("params", [])

        if not query or not query.strip():
            raise ToolError("Query cannot be empty")

        try:
            result = self._execute_query(self._db_path, query.strip(), params)
            return text_result(result)
        except sqlite3.Error as e:
            raise ToolError(f"SQLite error: {e}")

    def _execute_query(self, db_path: Path, query: str, params: list) -> str:
        """Execute a SQL query and return formatted results."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)

            # Check if this is a SELECT query or similar that returns rows
            if cursor.description is not None:
                rows = cursor.fetchall()
                return self._format_select_results(cursor, rows)
            else:
                # For INSERT, UPDATE, DELETE, CREATE, etc.
                conn.commit()
                return self._format_modification_result(cursor, query)
        finally:
            cursor.close()
            conn.close()

    def _format_select_results(self, cursor: sqlite3.Cursor, rows: list) -> str:
        """Format SELECT query results as a table."""
        if not rows:
            return "Query returned 0 rows."

        # Get column names
        columns = [desc[0] for desc in cursor.description]

        # Convert rows to list of dicts for easier formatting
        results = [dict(row) for row in rows]

        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in results:
            for col in columns:
                val = str(row[col]) if row[col] is not None else "NULL"
                widths[col] = max(widths[col], len(val))

        # Build table output
        lines = []

        # Header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        lines.append(header)
        lines.append("-+-".join("-" * widths[col] for col in columns))

        # Rows
        for row in results:
            row_str = " | ".join(
                (str(row[col]) if row[col] is not None else "NULL").ljust(widths[col])
                for col in columns
            )
            lines.append(row_str)

        lines.append(f"\n({len(results)} row{'s' if len(results) != 1 else ''})")

        return "\n".join(lines)

    def _format_modification_result(self, cursor: sqlite3.Cursor, query: str) -> str:
        """Format the result of a modification query."""
        query_upper = query.upper().split()[0] if query.split() else ""

        if query_upper == "INSERT":
            return f"INSERT successful. Last row ID: {cursor.lastrowid}. Rows affected: {cursor.rowcount}"
        elif query_upper == "UPDATE":
            return f"UPDATE successful. Rows affected: {cursor.rowcount}"
        elif query_upper == "DELETE":
            return f"DELETE successful. Rows affected: {cursor.rowcount}"
        elif query_upper == "CREATE":
            return "CREATE successful."
        elif query_upper == "DROP":
            return "DROP successful."
        elif query_upper == "ALTER":
            return "ALTER successful."
        else:
            return f"Query executed successfully. Rows affected: {cursor.rowcount}"
