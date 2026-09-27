import logging
from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.bug_localization import BugLocalizationRequest, BugLocalizationResult
from app.api.schemas.common import SuccessResponse
from app.api.schemas.indexing import IndexRepositoryRequest
from app.services.bug_localization_service import BugLocalizationService
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.indexing_service import IndexingService
from app.services.llm_service import LLMService, get_llm_service
from app.services.qdrant_service import QdrantService, get_qdrant_service
from app.services.repository_service import to_code_documents
from app.services.vector_service import VectorService

logger = logging.getLogger("repowise.ai.bug_localization_api")

router = APIRouter(tags=["bug_localization"], dependencies=[Depends(require_service_key)])


@router.post("/bugs/localize", response_model=SuccessResponse[BugLocalizationResult])
def localize_bug(
    request: BugLocalizationRequest,
    embeddings: EmbeddingService = Depends(get_embedding_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
    llm: LLMService = Depends(get_llm_service),
) -> SuccessResponse[BugLocalizationResult]:
    vector_service = VectorService(qdrant)
    documents, _ = to_code_documents(request.repository_id, request.files) if request.files else ([], 0)

    # Check if vectors exist for this repo in Qdrant; if not and files provided, auto-index
    if request.files:
        try:
            sample_vec = embeddings.embed(["test"])[0]
            existing_results = vector_service.search_similar(request.repository_id, sample_vec, limit=1)
            if not existing_results:
                logger.info(
                    "[Bug Localization] Repository %s has no vectors yet. Auto-indexing %d files...",
                    request.repository_id, len(request.files),
                )
                indexing_service = IndexingService(embeddings, vector_service)
                indexing_service.index_repository(
                    IndexRepositoryRequest(
                        repository_id=request.repository_id,
                        files=request.files,
                        replace_existing=False,
                    )
                )
        except Exception:
            logger.exception("[Bug Localization] Auto-indexing check/run failed for repository %s", request.repository_id)

    localization_service = BugLocalizationService(
        llm=llm,
        embeddings=embeddings,
        vectors=vector_service,
    )

    result = localization_service.localize(
        repository_id=request.repository_id,
        issue=request.issue,
        documents=documents,
        commit_history=request.commit_history,
        top_k=request.top_k,
        include_explanation=request.include_explanation,
    )

    return SuccessResponse(data=result)
