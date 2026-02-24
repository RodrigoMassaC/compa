"""
Punto de entrada de la API Compa.
Define la app FastAPI, middleware, routers y el endpoint /health.
"""
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import check_db_connection


# ── Ciclo de vida de la aplicación ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Acciones al iniciar y al apagar la aplicación."""
    # Inicialización: el motor de DB es lazy, no hay nada que hacer aquí
    print("🚀 Compa API arrancando...")
    yield
    # Cierre: liberar recursos si fuera necesario
    print("🛑 Compa API apagando...")


# ── Instancia principal ──
app = FastAPI(
    title="Compa API",
    description="Plataforma SaaS de comparación de precios en Venezuela",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (permitir cualquier origen en desarrollo) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoint de salud ──
@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    Verifica el estado de la API, la base de datos y Redis.
    Retorna {"status":"ok","db":"ok","redis":"ok"} si todo funciona.
    """
    # Verificar conexión a PostgreSQL
    db_ok = await check_db_connection()

    # Verificar conexión a Redis
    redis_ok = False
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    status = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }


# ── Raíz ──
@app.get("/", tags=["Sistema"])
async def root():
    """Endpoint raíz de bienvenida."""
    return {"message": "Compa API v1.0 — /health para estado del sistema"}
