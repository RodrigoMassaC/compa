from fastapi import APIRouter
from app.api.v1.routers import catalog, agent, auth

api_router = APIRouter()

api_router.include_router(catalog.router, prefix="/catalog", tags=["Catálogo"])
api_router.include_router(agent.router,   prefix="/agent",   tags=["Agente IA"])
api_router.include_router(auth.router,    prefix="/auth",    tags=["Autenticación"])
