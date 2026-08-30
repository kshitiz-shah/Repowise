import json
import logging
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider

logger = logging.getLogger("repowise.ai.llm")
T = TypeVar("T", bound=BaseModel)


class LLMUnavailableError(Exception):
    pass


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = self._create_provider()

    def _create_provider(self) -> LLMProvider:
        if self._settings.llm_provider == "gemini" and self._settings.gemini_api_key:
            return GeminiProvider(self._settings.gemini_api_key.get_secret_value(), self._settings.gemini_model)
        if self._settings.llm_provider == "groq" and self._settings.groq_api_key:
            return GroqProvider(self._settings.groq_api_key.get_secret_value(), self._settings.groq_model)
        raise LLMUnavailableError(f"No API key configured for LLM provider '{self._settings.llm_provider}'")

    def generate_text(self, prompt: str) -> str:
        try:
            return self._provider.generate_text(prompt)
        except LLMUnavailableError:
            raise
        except Exception as error:
            logger.exception("LLM generation failed")
            raise LLMUnavailableError("LLM provider is unavailable") from error

    def generate_structured(self, prompt: str, output_type: type[T]) -> T:
        raw = self.generate_text(f"{prompt}\n\nReturn valid JSON only.")
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return output_type.model_validate(json.loads(cleaned))
        except (json.JSONDecodeError, ValueError) as error:
            # Fallback: try finding first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return output_type.model_validate(json.loads(cleaned[start : end + 1]))
                except Exception:
                    pass
            logger.warning("LLM structured validation failed on raw output: %s", raw[:300])
            raise LLMUnavailableError("LLM returned invalid structured output") from error


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService(get_settings())
