"""LLM provider factory and exports."""

from __future__ import annotations

from jobhunter.llm.base import LLMClient
from jobhunter.llm.claude import AnthropicClient
from jobhunter.llm.gemini_client import GeminiClient
from jobhunter.llm.openai_client import OpenAIClient

_PROVIDERS: dict[str, type[LLMClient]] = {
    "claude": AnthropicClient,
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "gpt": OpenAIClient,
    "gemini": GeminiClient,
    "google": GeminiClient,
}


def create_llm_client(provider: str, api_key: str, model: str | None = None) -> LLMClient:
    """
    Factory function for LLM clients.

    Args:
        provider: One of ``"claude"``, ``"anthropic"``, ``"openai"``, ``"gpt"``,
                  ``"gemini"``, ``"google"``.
        api_key: API key for the chosen provider.
        model: Optional model override. Uses each provider's default if omitted.

    Returns:
        A ready-to-use :class:`LLMClient` instance.

    Raises:
        ValueError: If *provider* is not recognised.
    """
    key = provider.lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Choose from: {', '.join(sorted(set(_PROVIDERS.keys())))}"
        )
    if model:
        return cls(api_key=api_key, model=model)
    return cls(api_key=api_key)


__all__ = [
    "LLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "GeminiClient",
    "create_llm_client",
]
