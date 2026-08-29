import logging

from qdrant_client.models import Distance, FieldCondition, Filter, FilterSelector, MatchValue, PointStruct, VectorParams

from app.config import get_settings
from app.models.document import CodeChunk
from app.services.qdrant_service import QdrantService, QdrantUnavailableError

logger = logging.getLogger("repowise.ai.vectors")


class VectorService:
    """Repository-safe vector operations using one shared, metadata-filtered collection."""

    def __init__(self, qdrant: QdrantService) -> None:
        self._qdrant = qdrant
        self._client = qdrant._client  # SDK access is intentionally isolated to this service.
        self._collection = get_settings().qdrant_collection

    def ensure_collection(self, vector_size: int) -> None:
        try:
            if not self._client.collection_exists(self._collection):
                self._client.create_collection(self._collection, vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE))
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def upsert_documents(self, chunks: list[CodeChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one embedding")
        self.ensure_collection(len(vectors[0]))
        points = [PointStruct(id=chunk.id, vector=vector, payload={
            "repository_id": chunk.repository_id, "file_id": chunk.file_id, "file_path": chunk.file_path,
            "language": chunk.language, "chunk_index": chunk.chunk_index, "start_line": chunk.start_line,
            "end_line": chunk.end_line, "content": chunk.content, "file_hash": chunk.file_hash, "chunk_hash": chunk.chunk_hash,
        }) for chunk, vector in zip(chunks, vectors, strict=True)]
        try:
            self._client.upsert(collection_name=self._collection, points=points, wait=True)
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def search_similar(self, repository_id: str, query_vector: list[float], limit: int) -> list[dict]:
        repository_filter = Filter(must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))])
        try:
            results = self._client.query_points(collection_name=self._collection, query=query_vector, query_filter=repository_filter, limit=limit, with_payload=True).points
            return [{**point.payload, "score": point.score} for point in results]
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error

    def delete_repository_vectors(self, repository_id: str) -> None:
        repository_filter = Filter(must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))])
        try:
            self._client.delete(collection_name=self._collection, points_selector=FilterSelector(filter=repository_filter), wait=True)
        except Exception as error:
            raise QdrantUnavailableError("Qdrant is unavailable") from error
