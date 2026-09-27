import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.hotspots import HotspotCalculationRequest, HotspotCalculationResponse
from app.services.hotspot_service import HotspotService

logger = logging.getLogger("repowise.hotspots.route")

router = APIRouter(prefix="/hotspots", tags=["hotspots"], dependencies=[Depends(require_service_key)])
hotspot_service = HotspotService()


@router.post(
    "/calculate",
    response_model=SuccessResponse[HotspotCalculationResponse],
    status_code=status.HTTP_200_OK,
    summary="Calculate repository hotspot risk scores",
    description="Calculates normalized churn, bug density, bug-fix commits, and dependency centrality to identify risky components and files.",
)
async def calculate_hotspots(request: HotspotCalculationRequest) -> SuccessResponse[HotspotCalculationResponse]:
    try:
        result = hotspot_service.calculate_hotspots(request)
        return SuccessResponse(data=result)
    except Exception as exc:
        logger.exception("Failed to calculate hotspots for repository %s", request.repository_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hotspot calculation failed: {exc}",
        ) from exc
