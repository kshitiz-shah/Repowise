from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.architecture import ArchitectureData, ArchitectureRequest
from app.api.schemas.common import SuccessResponse
from app.services.architecture_service import ArchitectureService

router = APIRouter(tags=["architecture"], dependencies=[Depends(require_service_key)])


@router.post("/architecture/analyze", response_model=SuccessResponse[ArchitectureData])
def analyze_architecture(request: ArchitectureRequest) -> SuccessResponse[ArchitectureData]:
    return SuccessResponse(data=ArchitectureService().analyze(request))
