from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.indexing import IndexRepositoryData, IndexRepositoryRequest
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.indexing_service import IndexingService
from app.services.qdrant_service import QdrantService, get_qdrant_service
from app.services.vector_service import VectorService

router = APIRouter(tags=["indexing"], dependencies=[Depends(require_service_key)])


@router.post("/index/repository", response_model=SuccessResponse[IndexRepositoryData])
def index_repository(request: IndexRepositoryRequest, embeddings: EmbeddingService = Depends(get_embedding_service), qdrant: QdrantService = Depends(get_qdrant_service)) -> SuccessResponse[IndexRepositoryData]:
    return SuccessResponse(data=IndexingService(embeddings, VectorService(qdrant)).index_repository(request))
