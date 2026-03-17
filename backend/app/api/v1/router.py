from fastapi import APIRouter
from app.api.v1.routers import catalog

api_router = APIRouter()

api_router.include_router(catalog.router, prefix="/catalog", tags=["Catálogo"])

from app.api.v1.routers import agent
api_router.include_router(agent.router, prefix="/agent", tags=["Agente IA"])
