"""
Utilidades de seguridad para Compa.
- Hashing de contraseñas con bcrypt (passlib)
- Creación y verificación de tokens JWT (python-jose)
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Contexto de hashing ──────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Contraseñas ──────────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    """Retorna el hash bcrypt de una contraseña en texto plano."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contraseña en texto plano con su hash almacenado."""
    return pwd_context.verify(plain_password, hashed_password)


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
