import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.readme import ReadmeGenerationRequest, ReadmeGenerationResponse
from app.services.readme_service import ReadmeService

logger = logging.getLogger("repowise.readme.route")

router = APIRouter(prefix="/readme", tags=["readme"], dependencies=[Depends(require_service_key)])
readme_service = ReadmeService()


@router.post(
    "/generate",
    response_model=SuccessResponse[ReadmeGenerationResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate code-grounded repository README",
    description="Analyzes package files, entry points, environment variables, and scripts to generate a verified GitHub-Flavored Markdown README.",
)
async def generate_readme(request: ReadmeGenerationRequest) -> SuccessResponse[ReadmeGenerationResponse]:
    try:
        result = readme_service.generate_readme(request)
        return SuccessResponse(data=result)
    except Exception as exc:
        logger.exception("Failed to generate README for repository %s", request.repository_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"README generation failed: {exc}",
        ) from exc
