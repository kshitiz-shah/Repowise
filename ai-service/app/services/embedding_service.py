import logging
from functools import lru_cache

from app.config import Settings, get_settings

logger = logging.getLogger("repowise.ai.embeddings")


class EmbeddingError(Exception):
    pass


class EmbeddingService:
    """Embedding service supporting Google Gemini cloud embeddings (zero-RAM footprint)
    with lazy Sentence Transformers fallback for local offline environments."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model_name = settings.embedding_model
        self._sentence_transformer_model = None
        self._gemini_client = None

        if settings.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
                logger.info("Initialized Gemini cloud embeddings (model: gemini-embedding-001, dim: 384)")
            except Exception as e:
                logger.warning("Could not initialize Gemini embeddings client: %s", e)

    def _get_sentence_transformer_model(self):
        if self._sentence_transformer_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._sentence_transformer_model = SentenceTransformer(self._model_name)
                logger.info("Loaded sentence transformer model %s", self._model_name)
            except Exception as error:
                logger.exception("Could not load embedding model")
                raise EmbeddingError("Embedding model is unavailable") from error
        return self._sentence_transformer_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # 1. Use Gemini cloud embeddings if client is available (preferred on memory-constrained servers like Render)
        if self._gemini_client:
            try:
                from google.genai import types
                results = []
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = self._gemini_client.models.embed_content(
                        model="gemini-embedding-001",
                        contents=batch,
                        config=types.EmbedContentConfig(output_dimensionality=384),
                    )
                    results.extend([emb.values for emb in response.embeddings])
                return results
            except Exception as gemini_err:
                logger.warning("Gemini embedding call failed (%s); falling back to SentenceTransformer", gemini_err)

        # 2. Fallback to local SentenceTransformer
        try:
            vectors = self._get_sentence_transformer_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return vectors.tolist()
        except EmbeddingError:
            raise
        except Exception as error:
            logger.exception("Embedding generation failed")
            raise EmbeddingError("Embedding generation failed") from error


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(get_settings())

