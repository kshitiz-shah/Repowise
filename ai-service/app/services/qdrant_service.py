import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.config import Settings, get_settings

logger = logging.getLogger("repowise.ai.qdrant")


class QdrantUnavailableError(Exception):
    """Raised when Qdrant cannot be reached or does not accept requests."""


class QdrantService:
    """The single boundary between RepoWise business logic and Qdrant.

    Future vector operations (upsert, search, and deletion) will live here so
    routes and RAG code never depend on the Qdrant SDK directly.
    """

    def __init__(self, settings: Settings) -> None:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        self._client = QdrantClient(url=settings.qdrant_url, api_key=api_key)

    def collection_count(self) -> int:
        """Prove the connection is usable and return a non-sensitive summary."""
        try:
            return len(self._client.get_collections().collections)
        except (ResponseHandlingException, UnexpectedResponse, OSError, TimeoutError) as error:
            logger.warning("Qdrant connectivity check failed: %s", error)
            raise QdrantUnavailableError("Qdrant is unavailable") from error


@lru_cache
def get_qdrant_service() -> QdrantService:
    return QdrantService(get_settings())
