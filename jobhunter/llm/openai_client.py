"""OpenAI GPT LLM client."""

from __future__ import annotations

from jobhunter.llm.base import LLMClient

_DEFAULT_MODEL = "gpt-4o"
_MAX_TOKENS = 4096


class OpenAIClient(LLMClient):
    """
    LLM client backed by OpenAI's models.

    Args:
        api_key: Your OpenAI API key.
        model: Model ID to use. Defaults to ``gpt-4o``.
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' package is required to use the OpenAI provider. "
                "Install it with: pip install openai"
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
