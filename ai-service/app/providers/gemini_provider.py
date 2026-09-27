import logging
import time

from app.providers.base import LLMProvider

logger = logging.getLogger("repowise.ai.gemini")

# Retry config for transient Gemini errors (429 rate limit, 503 overloaded)
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 5  # seconds


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate_text(self, prompt: str) -> str:
        from google import genai
        from google.genai import errors as genai_errors
        from google.genai import types

        client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=15000))
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    "[Gemini] Attempt %d/%d | model=%s | prompt_len=%d chars",
                    attempt, _MAX_RETRIES, self._model, len(prompt),
                )
                response = client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                if not response.text:
                    raise ValueError("Gemini returned an empty response (no text)")
                logger.info("[Gemini] Success on attempt %d | response_len=%d chars", attempt, len(response.text))
                return response.text

            except genai_errors.ClientError as error:
                last_error = error
                error_str = str(error)

                # 429 RESOURCE_EXHAUSTED — check if it's quota exhaustion or transient rate limit
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if "quota" in error_str.lower() or "plan and billing" in error_str.lower():
                        logger.warning("[Gemini] Quota exhausted (429). Fast-failing to fallback provider.")
                        raise RuntimeError("Gemini quota exhausted. Switching to fallback provider.") from error
                    
                    wait = _RETRY_BACKOFF_BASE * attempt
                    logger.warning(
                        "[Gemini] Rate limited (429) on attempt %d/%d. Retrying in %ds...",
                        attempt, _MAX_RETRIES, wait,
                    )
                    if attempt < _MAX_RETRIES:
                        time.sleep(wait)
                        continue
                    else:
                        raise RuntimeError(
                            f"Gemini rate limit exceeded after {_MAX_RETRIES} retries."
                        ) from error

                # 400 INVALID_ARGUMENT — likely prompt too large for context window
                if "400" in error_str or "INVALID_ARGUMENT" in error_str:
                    logger.error(
                        "[Gemini] Prompt rejected (400 INVALID_ARGUMENT). "
                        "This usually means the prompt exceeded the model's context window. "
                        "prompt_len=%d chars",
                        len(prompt),
                    )
                    raise RuntimeError(
                        "The code context was too large for the AI model's input limit. "
                        "Try asking a more specific question to reduce the amount of code retrieved."
                    ) from error

                # Other client errors — not retryable
                logger.exception("[Gemini] Non-retryable client error on attempt %d", attempt)
                raise

            except Exception as error:
                last_error = error
                error_str = str(error)

                # 503 / UNAVAILABLE — server overloaded, retryable
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    wait = _RETRY_BACKOFF_BASE * attempt
                    logger.warning(
                        "[Gemini] Service unavailable (503) on attempt %d/%d. Retrying in %ds...",
                        attempt, _MAX_RETRIES, wait,
                    )
                    if attempt < _MAX_RETRIES:
                        time.sleep(wait)
                        continue

                # Unknown / unexpected error
                logger.exception("[Gemini] Unexpected error on attempt %d/%d", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE)
                    continue
                raise

        # Should not reach here, but just in case
        raise RuntimeError(f"Gemini generation failed after {_MAX_RETRIES} attempts") from last_error
