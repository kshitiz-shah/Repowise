import logging
from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.triage import BatchTriageRequest, BatchTriageResponse
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.triage_service import TriageService

logger = logging.getLogger("repowise.ai.triage_api")

router = APIRouter(tags=["triage"], dependencies=[Depends(require_service_key)])


@router.post("/triage/analyze", response_model=SuccessResponse[BatchTriageResponse])
def triage_issues(
    request: BatchTriageRequest,
    llm: LLMService = Depends(get_llm_service),
    embeddings: EmbeddingService = Depends(get_embedding_service),
) -> SuccessResponse[BatchTriageResponse]:
    service = TriageService(llm=llm, embeddings=embeddings)
    result = service.triage_repository_issues(request)
    return SuccessResponse(data=result)
