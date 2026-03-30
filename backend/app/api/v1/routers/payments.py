"""
Pagos y gestión de cuota — Compa API
=====================================
POST /payments/add-quota        → agrega +20 consultas al usuario (admin/webhook)
GET  /payments/quota            → consulta cuota actual del usuario autenticado

Nota: el procesador de pagos venezolano se integrará aquí cuando esté definido.
El endpoint add-quota recibirá el webhook de confirmación de pago y llamará
internamente a _aplicar_quota() para sumar las consultas.
"""
import logging
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.api.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

QUOTA_PACK   = 20      # consultas por paquete comprado
QUOTA_PREFIX = "rl:monthly"   # mismo prefijo que check_monthly_limit


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _aplicar_quota(user_id: str, cantidad: int = QUOTA_PACK) -> dict:
    """
    Suma `cantidad` consultas al límite mensual del usuario en Redis.
    Crea la clave si no existe (con TTL de 35 días).
    Retorna el estado actualizado.
    """
    mes = date.today().strftime("%Y-%m")
    key_uso    = f"{QUOTA_PREFIX}:{user_id}:{mes}"
    key_bonus  = f"{QUOTA_PREFIX}:bonus:{user_id}:{mes}"

    redis = await _get_redis()
    try:
        # Decrementar el contador de uso para "abrir espacio"
        # Alternativa limpia: guardar bonus por separado y sumarlo al límite
        bonus_actual = int(await redis.get(key_bonus) or 0)
        nuevo_bonus  = bonus_actual + cantidad
        await redis.setex(key_bonus, 35 * 86400, nuevo_bonus)

        uso_actual = int(await redis.get(key_uso) or 0)
        return {
            "user_id":       user_id,
            "mes":           mes,
            "uso_actual":    uso_actual,
            "bonus_comprado": nuevo_bonus,
            "limite_efectivo": 20 + nuevo_bonus,   # FREE base + bonus
            "restantes":     max(0, (20 + nuevo_bonus) - uso_actual),
        }
    finally:
        await redis.aclose()


# ── GET /quota ─────────────────────────────────────────────────────────────────

@router.get("/quota")
async def get_quota(current_user: dict = Depends(get_current_user)):
    """Devuelve el estado de consultas del mes actual para el usuario autenticado."""
    from app.api.dependencies import _MONTHLY_LIMITS

    mes  = date.today().strftime("%Y-%m")
    uid  = current_user["id_usuario"]
    plan = current_user.get("plan", "FREE")
    if current_user.get("rol_usuario") in ("B2B_EMPRESA", "ADMIN"):
        plan = current_user["rol_usuario"]

    base_limit = _MONTHLY_LIMITS.get(plan, 20)

    redis = await _get_redis()
    try:
        uso    = int(await redis.get(f"{QUOTA_PREFIX}:{uid}:{mes}") or 0)
        bonus  = int(await redis.get(f"{QUOTA_PREFIX}:bonus:{uid}:{mes}") or 0)
        limite = base_limit + bonus
        return {
            "plan":           plan,
            "mes":            mes,
            "uso":            uso,
            "bonus_comprado": bonus,
            "limite":         limite,
            "restantes":      max(0, limite - uso),
            "porcentaje":     round(min(100, uso / limite * 100)) if limite else 0,
        }
    finally:
        await redis.aclose()


# ── POST /add-quota ────────────────────────────────────────────────────────────
# Este endpoint se llamará desde el webhook del procesador de pagos.
# Por ahora solo está disponible para ADMIN para pruebas.

class AddQuotaRequest(BaseModel):
    user_id:  Optional[str] = None   # si es None, aplica al usuario autenticado
    cantidad: int = QUOTA_PACK

@router.post("/add-quota")
async def add_quota(
    body: AddQuotaRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Agrega consultas al usuario.
    - ADMIN puede agregar a cualquier user_id
    - Usuario normal solo puede agregar a sí mismo (body.user_id ignorado)

    Cuando el procesador de pagos esté integrado, el webhook llamará
    este endpoint tras confirmar el pago.
    """
    if current_user.get("rol_usuario") == "ADMIN" and body.user_id:
        target_id = body.user_id
    else:
        target_id = current_user["id_usuario"]

    resultado = await _aplicar_quota(target_id, body.cantidad)
    logger.info("add_quota | user=%s cantidad=%d bonus_total=%d",
                target_id, body.cantidad, resultado["bonus_comprado"])
    return resultado
