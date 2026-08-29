from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse

router = APIRouter(tags=["test"])


class TestData(BaseModel):
    message: str


@router.get("/test", response_model=SuccessResponse[TestData], dependencies=[Depends(require_service_key)])
def test_service() -> SuccessResponse[TestData]:
    return SuccessResponse(data=TestData(message="AI service authentication is working"))
