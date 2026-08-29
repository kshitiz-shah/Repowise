from app.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key, self._model = api_key, model

    def generate_text(self, prompt: str) -> str:
        from google import genai
        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(model=self._model, contents=prompt)
        if not response.text:
            raise ValueError("Gemini returned no text")
        return response.text
