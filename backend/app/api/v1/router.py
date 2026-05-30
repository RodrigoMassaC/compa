from fastapi import APIRouter
from app.api.v1.routers import catalog, agent, auth, listas, webhooks, payments, b2b

api_router = APIRouter()

api_router.include_router(catalog.router,  prefix="/catalog",  tags=["Catálogo"])
api_router.include_router(agent.router,    prefix="/agent",    tags=["Agente IA"])
api_router.include_router(auth.router,     prefix="/auth",     tags=["Autenticación"])
api_router.include_router(listas.router,   prefix="/listas",   tags=["Listas de Compras"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(payments.router, prefix="/payments", tags=["Pagos y Quota"])
api_router.include_router(b2b.router,      prefix="/b2b",      tags=["Compi B2B"])
