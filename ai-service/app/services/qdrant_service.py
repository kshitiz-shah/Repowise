import logging
import os
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.config import Settings, get_settings

logger = logging.getLogger("repowise.ai.qdrant")


class QdrantUnavailableError(Exception):
    """Raised when Qdrant cannot be reached or does not accept requests."""


class QdrantService:
    """The single boundary between RepoWise business logic and Qdrant.

    Supports remote Qdrant instances as well as automated fallback to
    embedded local storage so indexing and vector search work seamlessly
    in any deployment environment (Docker, Render, local).
    """

    def __init__(self, settings: Settings) -> None:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = None

        # 1. If an explicit remote HTTPS URL is specified, try connecting to it
        if settings.qdrant_url and settings.qdrant_url.startswith("https://"):
            try:
                test_client = QdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=5.0)
                test_client.get_collections()
                client = test_client
                logger.info("Successfully connected to remote Qdrant at %s", settings.qdrant_url)
            except Exception as exc:
                logger.warning("Remote Qdrant at %s unreachable: %s. Falling back to embedded storage.", settings.qdrant_url, exc)
                client = None
        elif settings.qdrant_url and not ("localhost" in settings.qdrant_url or "127.0.0.1" in settings.qdrant_url):
            try:
                test_client = QdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=3.0)
                test_client.get_collections()
                client = test_client
                logger.info("Successfully connected to Qdrant at %s", settings.qdrant_url)
            except Exception as exc:
                logger.warning("Qdrant at %s unreachable: %s. Falling back to embedded storage.", settings.qdrant_url, exc)
                client = None
        else:
            # 2. Localhost URL: check if a local Qdrant daemon is running
            try:
                test_client = QdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=1.0)
                test_client.get_collections()
                client = test_client
                logger.info("Connected to local Qdrant server at %s", settings.qdrant_url)
            except Exception:
                logger.info("No local Qdrant server active at %s. Using embedded local storage.", settings.qdrant_url)
                client = None

        # 3. Fallback to embedded in-process storage
        if client is None:
            storage_path = os.environ.get("QDRANT_STORAGE_PATH", "./qdrant_storage")
            os.makedirs(storage_path, exist_ok=True)
            self._client = QdrantClient(path=storage_path)
            logger.info("Initialized embedded Qdrant client at %s", storage_path)
        else:
            self._client = client

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

