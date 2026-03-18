"""
Dependencias de inyección de FastAPI para Compa.

get_current_user  → usuario autenticado o 401
get_optional_user → usuario si hay token válido, None si no hay token
"""
from typing import Optional

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token


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
            WHERE u.id_usuario = :id::uuid
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
