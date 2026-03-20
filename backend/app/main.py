"""
Punto de entrada de la API Compa.
Define la app FastAPI, middleware, routers y el endpoint /health.
"""
import logging
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.exceptions import add_exception_handlers
from app.api.v1.router import api_router

# ── Logging básico ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compa")


# ── Ciclo de vida de la aplicación ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Acciones al iniciar y al apagar la aplicación."""
    logger.info("Compa API arrancando — env=%s", settings.env)
    yield
    logger.info("Compa API apagando...")


# ── Instancia principal ──
app = FastAPI(
    title="Compa API",
    description="Plataforma SaaS de comparación de precios en Venezuela",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Montar Routers ──
app.include_router(api_router, prefix="/api/v1")

# ── Exception handlers ──
add_exception_handlers(app)

# ── CORS ──
# En desarrollo: solo localhost:3000 (configurable via ALLOWED_ORIGINS)
# En producción: definir ALLOWED_ORIGINS=https://tudominio.com en .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
