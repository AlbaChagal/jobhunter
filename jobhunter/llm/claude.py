"""Anthropic Claude LLM client."""

from __future__ import annotations

from jobhunter.llm.base import LLMClient

_DEFAULT_MODEL = "claude-opus-4-6"
_MAX_TOKENS = 4096


class AnthropicClient(LLMClient):
    """
    LLM client backed by Anthropic's Claude models.

    Args:
        api_key: Your Anthropic API key.
        model: Model ID to use. Defaults to ``claude-opus-4-6``.
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required to use the Claude provider. "
                "Install it with: pip install anthropic"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
