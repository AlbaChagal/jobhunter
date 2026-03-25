"""Google Gemini LLM client."""

from __future__ import annotations

import time

from jobhunter.llm.base import LLMClient

_DEFAULT_MODEL = "gemini-1.5-flash"


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
        t0 = time.perf_counter()
        model = self._genai.GenerativeModel(
            model_name=self._model_id,
            system_instruction=system,
        )
        response = model.generate_content(user)
        elapsed = time.perf_counter() - t0
        meta = getattr(response, "usage_metadata", None)
        if meta:
            total = getattr(meta, "total_token_count", "?")
            inp = getattr(meta, "prompt_token_count", "?")
            out = getattr(meta, "candidates_token_count", "?")
            print(
                f"[llm] {self._model_id} | "
                f"in={inp} out={out} total={total} | "
                f"{elapsed:.2f}s"
            )
        return response.text
