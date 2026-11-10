"""
Base classes and protocols for model providers in THE RELAY.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

@dataclass
class StreamChunk:
    delta: str
    is_first: bool = False
    is_final: bool = False
    elapsed_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

@dataclass
class ProviderResponse:
    content: str
    status_code: int = 200
    source: str = "stand-in"  # "real" or "stand-in"
    tokens_in: int = 0
    tokens_out: int = 0
    first_token_ms: float = 0.0
    total_ms: float = 0.0
    headers: Dict[str, str] = field(default_factory=dict)
    retry_after_s: Optional[float] = None
    rate_limited: bool = False
    error: Optional[str] = None

class BaseProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        **kwargs
    ) -> ProviderResponse:
        """Executes a complete model completion."""
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Streams model tokens incrementally."""
        pass

