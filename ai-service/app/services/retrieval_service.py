from app.api.schemas.rag import SourceReference
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService


class RetrievalService:
    def __init__(self, embeddings: EmbeddingService, vectors: VectorService) -> None:
        self._embeddings, self._vectors = embeddings, vectors

    def retrieve(self, repository_id: str, question: str, top_k: int) -> list[dict]:
        vector = self._embeddings.embed([question])[0]
        return self._vectors.search_similar(repository_id, vector, top_k)

    @staticmethod
    def sources(results: list[dict]) -> list[SourceReference]:
        return [SourceReference(file_id=item["file_id"], file_path=item["file_path"], start_line=item["start_line"], end_line=item["end_line"], score=item["score"]) for item in results]
