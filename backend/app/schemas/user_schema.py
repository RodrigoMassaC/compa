"""
Schemas Pydantic para usuarios de Compa.

UserCreate  → body del registro
UserLogin   → body del login
UserResponse → lo que devuelve la API (nunca incluye password_hash)
TokenResponse → JWT + datos básicos del usuario
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


# ── Registro ─────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Body para POST /auth/register"""
    email: EmailStr
    password: str
    nombre_completo: str

    # Datos personales opcionales (útiles para analytics B2B)
    fecha_nacimiento: Optional[date] = None       # Calculamos edad en el backend
    sexo: Optional[str] = None                    # "M" | "F" | "OTRO"
    ciudad: Optional[str] = None                  # ej: "Maracay"
    estado_ven: Optional[str] = None              # ej: "Aragua"

    # Canal WhatsApp (opcional, para futura integración)
    telefono_wa: Optional[str] = None             # ej: "584121234567"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

    @field_validator("nombre_completo")
    @classmethod
    def nombre_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip()

    @field_validator("sexo")
    @classmethod
    def sexo_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in ("M", "F", "OTRO"):
            raise ValueError("sexo debe ser M, F u OTRO")
        return v.upper() if v else None

    @field_validator("telefono_wa")
    @classmethod
    def telefono_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Acepta formatos: +584121234567 / 584121234567 / 04121234567
        cleaned = re.sub(r"[^\d]", "", v)
        if len(cleaned) < 10:
            raise ValueError("Número de WhatsApp inválido")
        return cleaned


# ── Login ─────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    """Body para POST /auth/login"""
    email: EmailStr
    password: str


# ── Respuestas ────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Representación pública del usuario (sin password)"""
    id_usuario: str
    email: str
    nombre_completo: str
    rol_usuario: str
    plan: str                          # código del plan: FREE / BASIC / PRO / ENTERPRISE
    estado_suscripcion: str
    telefono_wa: Optional[str] = None
    ciudad: Optional[str] = None
    estado_ven: Optional[str] = None
    sexo: Optional[str] = None
    creado_en: datetime
    ultimo_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Respuesta del login/registro: JWT + info básica del usuario"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Actualizar perfil ─────────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    """Body para PUT /auth/me — todos los campos son opcionales"""
    nombre_completo: Optional[str] = None
    ciudad: Optional[str] = None
    estado_ven: Optional[str] = None
    sexo: Optional[str] = None
    telefono_wa: Optional[str] = None
    fecha_nacimiento: Optional[date] = None

    @field_validator("sexo")
    @classmethod
    def sexo_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in ("M", "F", "OTRO"):
            raise ValueError("sexo debe ser M, F u OTRO")
        return v.upper() if v else None

    @field_validator("telefono_wa")
    @classmethod
    def telefono_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = re.sub(r"[^\d]", "", v)
        if len(cleaned) < 10:
            raise ValueError("Número de WhatsApp inválido")
        return cleaned
