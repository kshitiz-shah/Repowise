import logging
from typing import Any

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.models.document import CodeChunk
from app.services.qdrant_service import QdrantService, QdrantUnavailableError

logger = logging.getLogger("repowise.ai.vectors")


class VectorService:
    """Repository-safe vector operations using one shared, metadata-filtered collection."""

    def __init__(self, qdrant: QdrantService) -> None:
        self._qdrant = qdrant
        self._client = qdrant._client
        self._collection = get_settings().qdrant_collection

    def ensure_collection(self, vector_size: int) -> None:
        try:
            if not self._client.collection_exists(self._collection):
                self._client.create_collection(
                    self._collection,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection '%s' (vector_size: %d)", self._collection, vector_size)
                # Create a payload index on repository_id for efficient multi-tenant filtering.
                # Without this, every search does a brute-force scan across ALL repository vectors.
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name="repository_id",
                    field_schema="keyword",
                )
                logger.info("Created payload index on 'repository_id' for collection '%s'", self._collection)
        except Exception as error:
            logger.exception("Failed to ensure collection in Qdrant")
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def ensure_repository_index(self) -> None:
        """Ensure the repository_id payload index exists on an already-created collection."""
        try:
            if not self._client.collection_exists(self._collection):
                return
            collection_info = self._client.get_collection(self._collection)
            existing_indexes = collection_info.payload_schema or {}
            if "repository_id" not in existing_indexes:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name="repository_id",
                    field_schema="keyword",
                )
                logger.info("Retroactively created payload index on 'repository_id' for '%s'", self._collection)
        except Exception as error:
            logger.warning("Failed to ensure repository_id index: %s", error)

    def upsert_documents(self, chunks: list[CodeChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one embedding")
        self.ensure_collection(len(vectors[0]))
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "repository_id": chunk.repository_id,
                    "file_id": chunk.file_id,
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "chunk_index": chunk.chunk_index,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                    "file_hash": chunk.file_hash,
                    "chunk_hash": chunk.chunk_hash,
                    "symbol": chunk.symbol,
                    "chunk_type": chunk.chunk_type,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            self._client.upsert(collection_name=self._collection, points=points, wait=True)
            logger.info("Upserted %d vectors for repo %s into '%s'", len(points), chunks[0].repository_id, self._collection)
        except Exception as error:
            logger.exception("Failed to upsert documents into Qdrant")
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def search_similar(
        self,
        repository_id: str,
        query_vector: list[float],
        limit: int = 15,
        filter_file_paths: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            if not self._client.collection_exists(self._collection):
                logger.info("Qdrant collection '%s' does not exist yet; returning empty results", self._collection)
                return []
        except Exception as error:
            logger.warning("Qdrant collection check failed: %s", error)
            raise QdrantUnavailableError("Qdrant is unavailable") from error

        conditions: list[Any] = [FieldCondition(key="repository_id", match=MatchValue(value=repository_id))]
        repository_filter = Filter(must=conditions)
        try:
            results = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                query_filter=repository_filter,
                limit=limit,
                with_payload=True,
            ).points
            return [{**point.payload, "score": point.score} for point in results]
        except Exception as error:
            logger.exception("Qdrant query_points failed")
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def get_chunks_for_files(
        self,
        repository_id: str,
        file_paths: list[str],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve chunks directly belonging to specified file paths for dependency expansion."""
        if not file_paths:
            return []
        try:
            if not self._client.collection_exists(self._collection):
                return []
        except Exception:
            return []

        try:
            repository_filter = Filter(
                must=[
                    FieldCondition(key="repository_id", match=MatchValue(value=repository_id)),
                ]
            )
            points, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=repository_filter,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            target_set = set(file_paths)
            matched = [p.payload for p in points if p.payload and p.payload.get("file_path") in target_set]
            return matched[:limit]
        except Exception as error:
            logger.warning("Failed to scroll chunks for files: %s", error)
            return []

    def delete_repository_vectors(self, repository_id: str) -> None:
        try:
            if not self._client.collection_exists(self._collection):
                return
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error

        repository_filter = Filter(
            must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))]
        )
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=FilterSelector(filter=repository_filter),
                wait=True,
            )
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error
