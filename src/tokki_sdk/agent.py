from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from tokki_sdk.context import Context

if TYPE_CHECKING:
    from .context import Context


class Agent(ABC):
    async def init(self, context: "Context") -> bool:
        return True

    @abstractmethod
    async def run(self, context: "Context") -> None: ...
