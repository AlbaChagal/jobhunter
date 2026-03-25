"""Anthropic Claude LLM client."""

from __future__ import annotations

import time

from jobhunter.llm.base import LLMClient

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_MAX_TOKENS = 8192


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
        t0 = time.perf_counter()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        elapsed = time.perf_counter() - t0
        u = response.usage
        print(
            f"[llm] {self._model} | "
            f"in={u.input_tokens} out={u.output_tokens} "
            f"total={u.input_tokens + u.output_tokens} | "
            f"{elapsed:.2f}s"
        )
        return response.content[0].text
