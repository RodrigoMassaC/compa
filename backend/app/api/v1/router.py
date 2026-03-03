from fastapi import APIRouter
from app.api.v1.routers import catalog

api_router = APIRouter()

api_router.include_router(catalog.router, prefix="/catalog", tags=["Catálogo"])
