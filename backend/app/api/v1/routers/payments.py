"""
Pagos y gestión de cuota — Compa API
=====================================

Endpoints:
  GET  /payments/quota                       → estado de consultas del usuario
  POST /payments/add-quota                   → admin: sumar consultas
  POST /payments/pago-movil/crear            → crea pago pendiente (autenticado)
  GET  /payments/pago-movil/estado/{concepto}→ polling del estado (autenticado)
  POST /payments/r4-consulta                 → webhook R4 (validación pre-pago)
  POST /payments/r4-notifica                 → webhook R4 (confirmación de pago)
"""
import logging
from datetime import date
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.services.payments import service as pago_service
from app.services.payments.r4_client import is_allowed_ip, is_valid_token

router = APIRouter()
logger = logging.getLogger(__name__)

QUOTA_PACK   = 20
QUOTA_PREFIX = "rl:monthly"


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _aplicar_quota(user_id: str, cantidad: int = QUOTA_PACK) -> dict:
    """Suma `cantidad` consultas al bonus mensual del usuario en Redis."""
    mes = date.today().strftime("%Y-%m")
    key_uso   = f"{QUOTA_PREFIX}:{user_id}:{mes}"
    key_bonus = f"{QUOTA_PREFIX}:bonus:{user_id}:{mes}"

    redis = await _get_redis()
    try:
        bonus_actual = int(await redis.get(key_bonus) or 0)
        nuevo_bonus = bonus_actual + cantidad
        await redis.setex(key_bonus, 35 * 86400, nuevo_bonus)

        uso_actual = int(await redis.get(key_uso) or 0)
        return {
            "user_id":       user_id,
            "mes":           mes,
            "uso_actual":    uso_actual,
            "bonus_comprado": nuevo_bonus,
            "limite_efectivo": 20 + nuevo_bonus,
            "restantes":     max(0, (20 + nuevo_bonus) - uso_actual),
        }
    finally:
        await redis.aclose()


# ── GET /quota ───────────────────────────────────────────────────────────────

@router.get("/quota")
async def get_quota(current_user: dict = Depends(get_current_user)):
    """Devuelve el estado de consultas del mes actual."""
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


# ── POST /add-quota (admin) ──────────────────────────────────────────────────

class AddQuotaRequest(BaseModel):
    user_id:  Optional[str] = None
    cantidad: int = QUOTA_PACK


@router.post("/add-quota")
async def add_quota(
    body: AddQuotaRequest,
    current_user: dict = Depends(get_current_user),
):
    """Agrega consultas al usuario. ADMIN puede usarlo para cualquiera."""
    if current_user.get("rol_usuario") == "ADMIN" and body.user_id:
        target_id = body.user_id
    else:
        target_id = current_user["id_usuario"]

    resultado = await _aplicar_quota(target_id, body.cantidad)
    logger.info("add_quota | user=%s cantidad=%d bonus_total=%d",
                target_id, body.cantidad, resultado["bonus_comprado"])
    return resultado


# ── POST /pago-movil/crear (autenticado) ─────────────────────────────────────

class CrearPagoRequest(BaseModel):
    tipo_producto: str   # 'consultas_pack_30' | 'plan_ilimitado_mensual'


@router.post("/pago-movil/crear")
async def crear_pago_movil(
    body: CrearPagoRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un pago pendiente y devuelve los datos para que el usuario realice
    el Pago Móvil desde su banco (teléfono destino, banco, monto, concepto).
    """
    if body.tipo_producto not in pago_service.PRODUCTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Producto desconocido. Opciones: {list(pago_service.PRODUCTOS.keys())}",
        )

    try:
        datos = await pago_service.crear_pago_pendiente(
            db,
            id_usuario=current_user["id_usuario"],
            tipo_producto=body.tipo_producto,
        )
        return datos
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /pago-movil/estado/{concepto} (autenticado) ──────────────────────────

@router.get("/pago-movil/estado/{concepto}")
async def estado_pago(
    concepto: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve el estado del pago. El frontend hace polling cada 3 seg."""
    r = await db.execute(text("""
        SELECT id_pago, concepto, status, motivo_rechazo,
               monto_bs, monto_usd, tipo_producto,
               aprobado_en, creado_en
        FROM pagos_bolivares
        WHERE concepto = :c AND id_usuario = :uid
        LIMIT 1
    """), {"c": concepto, "uid": current_user["id_usuario"]})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    return {
        "concepto":       row.concepto,
        "status":         row.status,
        "motivo_rechazo": row.motivo_rechazo,
        "monto_bs":       float(row.monto_bs),
        "monto_usd":      float(row.monto_usd) if row.monto_usd else None,
        "tipo_producto":  row.tipo_producto,
        "aprobado_en":    row.aprobado_en.isoformat() if row.aprobado_en else None,
        "creado_en":      row.creado_en.isoformat() if row.creado_en else None,
    }


# ── POST /r4-consulta (webhook público, IP whitelist + UUID auth) ────────────

@router.post("/r4-consulta")
async def webhook_r4_consulta(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook que R4 llama ANTES de procesar el pago para validar el cliente.

    R4 envía: { IdCliente, Monto, TelefonoComercio }
    Respondemos: { status: true } si aceptamos el pago, { status: false } si no.

    Aceptamos cualquier pago entrante que llegue (R4 ya validó al cliente).
    """
    if not is_allowed_ip(request):
        raise HTTPException(status_code=403, detail="IP no autorizada")
    if not is_valid_token(request):
        raise HTTPException(status_code=403, detail="Token inválido")

    try:
        body = await request.json()
        logger.info(f"r4-consulta recibido: {body}")
    except Exception as e:
        logger.error(f"r4-consulta: body inválido: {e}")
        return {"status": False}

    # Aceptamos todos los pagos entrantes (la conciliación se hace en r4-notifica)
    return {"status": True}


# ── POST /r4-notifica (webhook público, IP whitelist + UUID auth) ────────────

@router.post("/r4-notifica")
async def webhook_r4_notifica(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook que R4 llama cuando se confirma un pago entrante.

    R4 envía: { IdComercio, TelefonoComercio, TelefonoEmisor, Concepto,
                BancoEmisor, Monto, FechaHora, Referencia, CodigoRed }

    Concilia el pago y activa el producto comprado.
    """
    if not is_allowed_ip(request):
        raise HTTPException(status_code=403, detail="IP no autorizada")
    if not is_valid_token(request):
        raise HTTPException(status_code=403, detail="Token inválido")

    try:
        notif = await request.json()
        logger.info(f"r4-notifica recibido: {notif}")
    except Exception as e:
        logger.error(f"r4-notifica: body inválido: {e}")
        return {"abono": False}

    try:
        resultado = await pago_service.conciliar_pago(db, notif)
        return resultado
    except Exception as e:
        logger.error(f"r4-notifica: error conciliando: {e}", exc_info=True)
        return {"abono": False}
