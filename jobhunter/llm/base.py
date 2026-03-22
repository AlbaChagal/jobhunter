"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Minimal interface all LLM providers must implement."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """
        Send a prompt and return the model's text response.

        Args:
            system: System / instruction prompt.
            user: User message (the actual query or document).

        Returns:
            The model's response as a plain string.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model identifier."""
        ...
