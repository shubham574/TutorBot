"""Abstract base interface for LLM providers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """Abstract interface for LLM operations (chat, structured output, vision)."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> str:
        """Standard chat completion returning raw response text."""
        pass

    @abstractmethod
    async def extract_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        """Extracts and validates structured data conforming to a Pydantic model."""
        pass

    @abstractmethod
    async def extract_from_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        model: Optional[str] = None,
    ) -> str:
        """Processes an image with a vision LLM to extract text or description."""
        pass
