"""
Ollama vendor implementation.
"""

import logging
from typing import AsyncGenerator, Sequence

from .base import Vendor, Message, LlmConfig

logger = logging.getLogger(__name__)


class Ollama(Vendor):
    """Ollama local API vendor."""

    def __init__(self, base_url: str = "http://localhost:11434", config: LlmConfig | None = None):
        self.base_url = base_url
        self.config = config

    async def inference_no_streaming(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> Message:
        raise NotImplementedError("Ollama non-streaming inference not implemented")

    async def inference(
        self,
        messages: Sequence[Message],
        model: str,
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[Message, None]:
        raise NotImplementedError("Ollama inference not implemented")
        yield  # make this a generator
