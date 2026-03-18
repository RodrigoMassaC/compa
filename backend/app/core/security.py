"""
Utilidades de seguridad para Compa.
- Hashing de contraseñas con bcrypt directo (compatible con bcrypt >= 4.x)
- Creación y verificación de tokens JWT (python-jose)
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Contraseñas ──────────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    """Retorna el hash bcrypt de una contraseña en texto plano."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contraseña en texto plano con su hash almacenado."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un JWT firmado con HS256.

    Args:
        data: Payload a incluir (debe tener al menos 'sub' con el id_usuario).
        expires_delta: Tiempo de expiración (default: ACCESS_TOKEN_EXPIRE_MINUTES).

    Returns:
        Token JWT como string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un JWT.

    Returns:
        El payload del token.

    Raises:
        JWTError: Si el token es inválido o ha expirado.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def is_token_valid(token: str) -> bool:
    """Retorna True si el token es válido, False si no (sin lanzar excepción)."""
    try:
        decode_access_token(token)
        return True
    except JWTError:
        return False
