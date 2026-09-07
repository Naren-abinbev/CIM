from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import auth, health, incidents
from backend.api.routes.crisis import router as crisis_router
from backend.api.routes.duplicates import router as duplicates_router

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(incidents.router)
api_router.include_router(crisis_router)
api_router.include_router(duplicates_router)