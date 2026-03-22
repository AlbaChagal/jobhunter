"""Google Gemini LLM client."""

from __future__ import annotations

from jobhunter.llm.base import LLMClient

_DEFAULT_MODEL = "gemini-1.5-pro"


class GeminiClient(LLMClient):
    """
    LLM client backed by Google's Gemini models.

    Args:
        api_key: Your Google AI Studio API key.
        model: Model ID to use. Defaults to ``gemini-1.5-pro``.
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "The 'google-generativeai' package is required to use the Gemini provider. "
                "Install it with: pip install google-generativeai"
            )
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_id = model

    @property
    def model_name(self) -> str:
        return self._model_id

    def complete(self, system: str, user: str) -> str:
        model = self._genai.GenerativeModel(
            model_name=self._model_id,
            system_instruction=system,
        )
        response = model.generate_content(user)
        return response.text
