from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.investigations import router as investigations_router
from app.api.analyze import router as analyze_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(investigations_router)
api_router.include_router(analyze_router)
