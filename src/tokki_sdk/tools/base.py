from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ExecutionContext
    from tokki_sdk.tokki_pb2 import ToolResultContent


class ToolError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Tool(ABC):
    def __init__(self, context: "ExecutionContext", approval_required: bool = False):
        self.context = context
        self.approval_required = approval_required

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def schema(self) -> dict: ...

    @abstractmethod
    async def execute(self, input: dict) -> "ToolResultContent": ...
