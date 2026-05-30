from fastapi import APIRouter
from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        provider_mode=settings.PROVIDER_MODE,
        database="connected",
        version="0.1.0",
    )
