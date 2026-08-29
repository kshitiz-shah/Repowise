import logging
from functools import lru_cache

from app.config import Settings, get_settings

logger = logging.getLogger("repowise.ai.embeddings")


class EmbeddingError(Exception):
    pass


class EmbeddingService:
    """Lazy Sentence Transformers adapter so application startup stays fast."""

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.embedding_model
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info("Loaded embedding model %s", self._model_name)
            except Exception as error:
                logger.exception("Could not load embedding model")
                raise EmbeddingError("Embedding model is unavailable") from error
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return vectors.tolist()
        except EmbeddingError:
            raise
        except Exception as error:
            logger.exception("Embedding generation failed")
            raise EmbeddingError("Embedding generation failed") from error


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(get_settings())
