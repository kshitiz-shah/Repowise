from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.issues import AnalyzeIssueRequest, IssueAnalysisData
from app.services.issue_service import IssueService
from app.services.llm_service import LLMService, get_llm_service

router = APIRouter(tags=["issues"], dependencies=[Depends(require_service_key)])


@router.post("/issues/analyze", response_model=SuccessResponse[IssueAnalysisData])
def analyze_issue(request: AnalyzeIssueRequest, llm: LLMService = Depends(get_llm_service)) -> SuccessResponse[IssueAnalysisData]:
    return SuccessResponse(data=IssueService(llm).analyze(request))
