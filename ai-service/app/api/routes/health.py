from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.config import get_settings
from app.services.qdrant_service import QdrantService, get_qdrant_service

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str
    service: str
    environment: str


class QdrantHealthData(BaseModel):
    status: str
    collections: int


@router.get("/health", response_model=SuccessResponse[HealthData])
def health() -> SuccessResponse[HealthData]:
    settings = get_settings()
    return SuccessResponse(
        data=HealthData(status="ok", service=settings.service_name, environment=settings.environment)
    )


@router.get("/health/qdrant", response_model=SuccessResponse[QdrantHealthData], dependencies=[Depends(require_service_key)])
def qdrant_health(service: QdrantService = Depends(get_qdrant_service)) -> SuccessResponse[QdrantHealthData]:
    return SuccessResponse(data=QdrantHealthData(status="ok", collections=service.collection_count()))
