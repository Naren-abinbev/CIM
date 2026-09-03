from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import auth, health, incidents

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(incidents.router)