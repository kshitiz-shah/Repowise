from app.providers.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key, self._model = api_key, model

    def generate_text(self, prompt: str) -> str:
        from groq import Groq
        response = Groq(api_key=self._api_key, timeout=90.0).chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16384,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned no text")
        return content
