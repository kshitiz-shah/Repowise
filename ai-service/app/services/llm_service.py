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
        self._primary = self._create_primary()
        self._fallback = self._create_fallback()

    def _create_primary(self) -> LLMProvider | None:
        """Create the primary provider based on LLM_PROVIDER setting."""
        try:
            if self._settings.llm_provider == "gemini" and self._settings.gemini_api_key:
                return GeminiProvider(self._settings.gemini_api_key.get_secret_value(), self._settings.gemini_model)
            if self._settings.llm_provider == "groq" and self._settings.groq_api_key:
                return GroqProvider(self._settings.groq_api_key.get_secret_value(), self._settings.groq_model)
        except Exception as e:
            logger.warning("Failed to create primary LLM provider '%s': %s", self._settings.llm_provider, e)
        return None

    def _create_fallback(self) -> LLMProvider | None:
        """Create a fallback provider (the OTHER provider that isn't primary)."""
        try:
            if self._settings.llm_provider == "gemini" and self._settings.groq_api_key:
                key = self._settings.groq_api_key.get_secret_value()
                if key:
                    logger.info("Groq configured as fallback LLM provider (model: %s)", self._settings.groq_model)
                    return GroqProvider(key, self._settings.groq_model)
            if self._settings.llm_provider == "groq" and self._settings.gemini_api_key:
                key = self._settings.gemini_api_key.get_secret_value()
                if key:
                    logger.info("Gemini configured as fallback LLM provider (model: %s)", self._settings.gemini_model)
                    return GeminiProvider(key, self._settings.gemini_model)
        except Exception as e:
            logger.warning("Failed to create fallback LLM provider: %s", e)
        return None

    def generate_text(self, prompt: str) -> str:
        if not self._primary and not self._fallback:
            raise LLMUnavailableError(f"No API key configured for LLM provider '{self._settings.llm_provider}'")

        # Try primary provider
        if self._primary:
            try:
                return self._primary.generate_text(prompt)
            except Exception as primary_error:
                logger.warning(
                    "[LLM Fallback] Primary provider (%s) failed: %s",
                    self._settings.llm_provider, primary_error,
                )
                # If we have a fallback, try it
                if self._fallback:
                    logger.info("[LLM Fallback] Switching to fallback provider...")
                    try:
                        result = self._fallback.generate_text(prompt)
                        logger.info("[LLM Fallback] Fallback provider succeeded")
                        return result
                    except Exception as fallback_error:
                        logger.exception("[LLM Fallback] Fallback provider also failed")
                        raise LLMUnavailableError(
                            f"Both LLM providers failed. "
                            f"Primary: {primary_error}. Fallback: {fallback_error}"
                        ) from fallback_error
                else:
                    logger.exception("[LLM Error] Primary failed and no fallback configured")
                    raise LLMUnavailableError("LLM provider is unavailable") from primary_error

        # No primary, try fallback directly
        if self._fallback:
            try:
                return self._fallback.generate_text(prompt)
            except Exception as error:
                logger.exception("[LLM Error] Fallback-only provider failed")
                raise LLMUnavailableError("LLM provider is unavailable") from error

        raise LLMUnavailableError("No LLM providers available")

    def transform_query(self, question: str) -> str:
        """
        Step 1 inspired by RAG_AI (query.js:transformQuery):
        Rephrase user question into a standalone, keyword-rich query optimized
        for semantic codebase retrieval and embedding search.
        """
        prompt = (
            "You are an expert software engineer and codebase search query optimizer.\n"
            "Given the user's technical question about a repository, rephrase it into a concise, standalone search query "
            "enriched with relevant software engineering terms, potential function/class names, API endpoints, or architectural concepts.\n"
            "Only output the transformed search query and nothing else.\n\n"
            f"User Question: {question}\n"
            "Transformed Search Query:"
        )
        try:
            transformed = self.generate_text(prompt).strip().strip('"').strip("'")
            if transformed and len(transformed) >= 3:
                logger.info("[Query Transformation] '%s' -> '%s'", question, transformed)
                return transformed
        except Exception as e:
            logger.warning("[Query Transformation] Failed to transform query: %s. Using raw question.", e)
        return question

    def generate_structured(self, prompt: str, output_type: type[T]) -> T:
        raw = self.generate_text(
            f"{prompt}\n\n"
            "CRITICAL: Return ONLY a valid JSON object. No markdown fences, no explanation, no preamble. "
            "Start with {{ and end with }}. Do not wrap in ```json blocks."
        )
        cleaned = raw.strip()

        # Strip Qwen3 / DeepSeek thinking tags
        import re
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

        # Strip markdown fences
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
            logger.warning("LLM structured validation failed on raw output (first 500 chars): %s", raw[:500])
            raise LLMUnavailableError("LLM returned invalid structured output") from error


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService(get_settings())
