import logging

from app.api.schemas.indexing import IndexRepositoryData, IndexRepositoryRequest
from app.services.embedding_service import EmbeddingService
from app.services.repository_service import to_code_documents
from app.services.vector_service import VectorService
from app.utils.chunking import chunk_document

logger = logging.getLogger("repowise.ai.indexing")


class IndexingService:
    def __init__(self, embeddings: EmbeddingService, vectors: VectorService) -> None:
        self._embeddings, self._vectors = embeddings, vectors

    def index_repository(self, request: IndexRepositoryRequest) -> IndexRepositoryData:
        documents, skipped = to_code_documents(request.repository_id, request.files)
        if not documents:
            return IndexRepositoryData(repository_id=request.repository_id, indexed_files=0, indexed_chunks=0, skipped_files=skipped)
        if request.replace_existing:
            self._vectors.delete_repository_vectors(request.repository_id)
        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        vectors = self._embeddings.embed([chunk.content for chunk in chunks])
        self._vectors.upsert_documents(chunks, vectors)
        logger.info("Indexed repository %s: %s files, %s chunks", request.repository_id, len(documents), len(chunks))
        return IndexRepositoryData(repository_id=request.repository_id, indexed_files=len(documents), indexed_chunks=len(chunks), skipped_files=skipped)
