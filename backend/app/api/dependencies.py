"""
Dependencias de inyección de FastAPI para Compa.

get_current_user  → usuario autenticado o 401
get_optional_user → usuario si hay token válido, None si no hay token
check_rate_limit  → limita llamadas al agente por IP/usuario vía Redis
"""
import logging
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Rate limiting ──────────────────────────────────────────────────────────────

# Límites por ventana de 60 segundos (anti-abuso)
_RATE_ANON  = 15   # peticiones/min para usuarios anónimos (por IP)
_RATE_AUTH  = 40   # peticiones/min para usuarios autenticados (por user_id)

# Límites mensuales por plan (consultas al agente IA)
_MONTHLY_LIMITS: dict[str, int] = {
    "ANON":        10,   # sin cuenta
    "FREE":        20,   # plan gratuito
    "BASIC":      100,
    "PRO":        500,
    "ENTERPRISE": 9999,  # ilimitado práctico
    "B2B_EMPRESA": 9999,
    "ADMIN":      9999,
}


async def _get_redis() -> Optional[aioredis.Redis]:
    """Devuelve cliente Redis o None si no está disponible (nunca bloquea)."""
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
        await r.ping()
        return r
    except Exception:
        return None


async def get_city_from_ip(ip: str) -> str:
    """
    Retorna la ciudad aproximada de una IP usando ip-api.com (gratis, sin key).
    Cachea el resultado en Redis por 24h para no repetir llamadas.
    Retorna string vacío si falla o si la IP es local.
    """
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return ""

    # Intentar desde cache Redis
    redis = await _get_redis()
    cache_key = f"geo:ip:{ip}"
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                await redis.aclose()
                return cached
        except Exception:
            pass

    # Llamar a ip-api.com
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,city,regionName", "lang": "es"},
            )
            data = resp.json()
            if data.get("status") == "success":
                city = data.get("city", "")
                if redis and city:
                    try:
                        await redis.setex(cache_key, 86400, city)  # 24h
                    except Exception:
                        pass
                return city
    except Exception as exc:
        logger.debug("get_city_from_ip | error: %s", exc)
    finally:
        if redis:
            try:
                await redis.aclose()
            except Exception:
                pass

    return ""


async def check_monthly_limit(
    identifier: str,
    plan: str = "FREE",
) -> dict:
    """
    Verifica y registra el consumo mensual de consultas al agente.

    identifier : user_id (web) o phone (WhatsApp)
    plan       : FREE | BASIC | PRO | ENTERPRISE | B2B_EMPRESA | ADMIN | ANON

    Retorna {"count": N, "limit": L, "remaining": R}
    Lanza HTTPException 429 si se superó el límite.
    """
    from datetime import date
    from fastapi import HTTPException

    limit = _MONTHLY_LIMITS.get(plan, _MONTHLY_LIMITS["FREE"])
    mes   = date.today().strftime("%Y-%m")
    key   = f"rl:monthly:{identifier}:{mes}"

    redis = await _get_redis()
    if not redis:
        return {"count": 0, "limit": limit, "remaining": limit}  # fail-open

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 35 * 86400)  # 35 días, cubre fin de mes

        await redis.aclose()

        remaining = max(0, limit - count)

        if count > limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Alcanzaste el límite de {limit} consultas este mes. "
                    f"{'Actualiza tu plan en compa.com.ve para continuar.' if plan in ('FREE','ANON') else 'Contacta soporte.'}"
                ),
                headers={"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
            )

        return {"count": count, "limit": limit, "remaining": remaining}

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("monthly_limit: Redis error — %s", exc)
        return {"count": 0, "limit": limit, "remaining": limit}  # fail-open


async def check_rate_limit(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> None:
    """
    Rate limiter basado en Redis con ventana deslizante de 60 s.

    - Anónimo → clave = "rl:ip:<ip>"        límite = 15 req/min
    - Autenticado → clave = "rl:u:<user_id>" límite = 40 req/min

    Si Redis no está disponible, el check se omite silenciosamente (fail-open).
    """
    redis = await _get_redis()
    if not redis:
        return  # Redis caído → fail-open, no bloquear

    # Determinar clave e identificador
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            uid = payload.get("sub", "")
            key = f"rl:u:{uid}"
            limit = _RATE_AUTH
        except Exception:
            ip = request.client.host if request.client else "unknown"
            key = f"rl:ip:{ip}"
            limit = _RATE_ANON
    else:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:ip:{ip}"
        limit = _RATE_ANON

    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)   # primera petición → iniciar ventana de 60 s

        await redis.aclose()

        if current > limit:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail=f"Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
                headers={"Retry-After": "60"},
            )
    except Exception as exc:
        # Cualquier error de Redis → fail-open
        logger.warning("rate_limit: Redis error — %s", exc)


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Extrae y valida el JWT del header Authorization: Bearer <token>.

    Uso:
        @router.get("/ruta")
        async def mi_endpoint(user = Depends(get_current_user)):
            ...

    Raises:
        UnauthorizedError 401 si el token falta, es inválido o el usuario no existe.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Token de acceso requerido")

    token = authorization.split(" ", 1)[1]

    try:
        payload = decode_access_token(token)
        id_usuario: str | None = payload.get("sub")
        if not id_usuario:
            raise UnauthorizedError("Token inválido")
    except JWTError:
        raise UnauthorizedError("Token inválido o expirado")

    result = await db.execute(
        text("""
            SELECT
                u.id_usuario::text,
                u.email,
                u.nombre_completo,
                u.rol_usuario,
                u.telefono_wa,
                u.ciudad,
                u.estado_ven,
                u.sexo,
                u.estado_suscripcion,
                u.creado_en,
                u.ultimo_login,
                COALESCE(pm.codigo_plan, 'FREE') AS plan
            FROM usuarios u
            LEFT JOIN planes_membresia pm ON pm.id_plan = u.id_plan_actual
            WHERE u.id_usuario = CAST(:id AS uuid)
        """),
        {"id": id_usuario},
    )
    row = result.mappings().first()

    if not row:
        raise UnauthorizedError("Usuario no encontrado")

    return dict(row)


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """
    Como get_current_user pero retorna None en lugar de 401 si no hay token.
    Útil para endpoints que funcionan tanto anónimos como autenticados.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return await get_current_user(authorization=authorization, db=db)
    except UnauthorizedError:
        return None
