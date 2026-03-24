"""
Autenticación y gestión de cuenta — Compa API
=============================================
POST /api/v1/auth/register  → crear cuenta nueva
POST /api/v1/auth/login     → obtener JWT
GET  /api/v1/auth/me        → perfil del usuario autenticado
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.security import create_access_token, get_password_hash, verify_password
from app.api.dependencies import get_current_user
from app.schemas.user_schema import TokenResponse, UserCreate, UserLogin, UserResponse, UserUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_free_plan_id(db: AsyncSession) -> str:
    """Retorna el UUID del plan FREE."""
    result = await db.execute(
        text("SELECT id_plan::text FROM planes_membresia WHERE codigo_plan = 'FREE' LIMIT 1")
    )
    row = result.scalar()
    if not row:
        raise RuntimeError("Plan FREE no encontrado en DB — ejecuta init_db.py")
    return row


def _row_to_user_response(row: dict) -> UserResponse:
    return UserResponse(
        id_usuario=str(row["id_usuario"]),
        email=row["email"],
        nombre_completo=row["nombre_completo"],
        rol_usuario=row["rol_usuario"],
        plan=row.get("plan", "FREE"),
        estado_suscripcion=row["estado_suscripcion"],
        telefono_wa=row.get("telefono_wa"),
        ciudad=row.get("ciudad"),
        estado_ven=row.get("estado_ven"),
        sexo=row.get("sexo"),
        creado_en=row["creado_en"],
        ultimo_login=row.get("ultimo_login"),
    )


# ── POST /register ────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Crea una cuenta nueva de consumidor.
    Asigna automáticamente el plan FREE.
    Retorna JWT listo para usar.
    """
    # Verificar email único
    existing = await db.execute(
        text("SELECT 1 FROM usuarios WHERE email = :email LIMIT 1"),
        {"email": body.email},
    )
    if existing.scalar():
        raise ValidationError("Ya existe una cuenta con ese email")

    # Verificar teléfono WA único (si se proporcionó)
    if body.telefono_wa:
        existing_wa = await db.execute(
            text("SELECT 1 FROM usuarios WHERE telefono_wa = :wa LIMIT 1"),
            {"wa": body.telefono_wa},
        )
        if existing_wa.scalar():
            raise ValidationError("Ese número de WhatsApp ya está registrado")

    free_plan_id = await _get_free_plan_id(db)
    id_usuario = str(uuid.uuid4())
    password_hash = get_password_hash(body.password)

    await db.execute(
        text("""
            INSERT INTO usuarios (
                id_usuario, email, password_hash, nombre_completo,
                telefono_wa, fecha_nacimiento, sexo, ciudad, estado_ven,
                rol_usuario, id_plan_actual, estado_suscripcion
            ) VALUES (
                CAST(:id AS uuid), :email, :password_hash, :nombre,
                :telefono_wa, :fecha_nacimiento, :sexo, :ciudad, :estado_ven,
                'CONSUMIDOR', CAST(:plan_id AS uuid), 'ACTIVA'
            )
        """),
        {
            "id":               id_usuario,
            "email":            body.email,
            "password_hash":    password_hash,
            "nombre":           body.nombre_completo,
            "telefono_wa":      body.telefono_wa,
            "fecha_nacimiento": body.fecha_nacimiento,
            "sexo":             body.sexo,
            "ciudad":           body.ciudad,
            "estado_ven":       body.estado_ven,
            "plan_id":          free_plan_id,
        },
    )
    await db.commit()

    logger.info("register | nuevo usuario email=%s id=%s", body.email, id_usuario)

    token = create_access_token({"sub": id_usuario})
    user = UserResponse(
        id_usuario=id_usuario,
        email=body.email,
        nombre_completo=body.nombre_completo,
        rol_usuario="CONSUMIDOR",
        plan="FREE",
        estado_suscripcion="ACTIVA",
        telefono_wa=body.telefono_wa,
        ciudad=body.ciudad,
        estado_ven=body.estado_ven,
        sexo=body.sexo,
        creado_en=datetime.now(timezone.utc),
    )
    return TokenResponse(access_token=token, user=user)


# ── POST /login ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Autentica con email + contraseña.
    Actualiza ultimo_login y retorna JWT.
    """
    result = await db.execute(
        text("""
            SELECT
                u.id_usuario::text,
                u.email,
                u.password_hash,
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
            WHERE u.email = :email
        """),
        {"email": body.email},
    )
    row = result.mappings().first()

    if not row or not verify_password(body.password, row["password_hash"]):
        raise UnauthorizedError("Email o contraseña incorrectos")

    # Actualizar ultimo_login
    await db.execute(
        text("UPDATE usuarios SET ultimo_login = NOW() WHERE id_usuario = CAST(:id AS uuid)"),
        {"id": row["id_usuario"]},
    )
    await db.commit()

    logger.info("login | email=%s", body.email)

    token = create_access_token({"sub": row["id_usuario"]})
    return TokenResponse(access_token=token, user=_row_to_user_response(dict(row)))


# ── GET /me ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Retorna el perfil del usuario autenticado."""
    return _row_to_user_response(current_user)


# ── PUT /me ───────────────────────────────────────────────────────────────────

@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza los datos del perfil del usuario autenticado."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_user_response(current_user)

    # Verificar teléfono WA único si se cambia
    if "telefono_wa" in updates and updates["telefono_wa"] != current_user.get("telefono_wa"):
        existing = await db.execute(
            text("SELECT 1 FROM usuarios WHERE telefono_wa = :wa AND id_usuario != CAST(:id AS uuid) LIMIT 1"),
            {"wa": updates["telefono_wa"], "id": current_user["id_usuario"]},
        )
        if existing.scalar():
            raise ValidationError("Ese número de WhatsApp ya está registrado")

    set_clauses = ", ".join(f"{col} = :{col}" for col in updates)
    params = {**updates, "id": current_user["id_usuario"]}

    await db.execute(
        text(f"UPDATE usuarios SET {set_clauses} WHERE id_usuario = CAST(:id AS uuid)"),
        params,
    )
    await db.commit()

    # Releer el usuario actualizado
    result = await db.execute(
        text("""
            SELECT u.id_usuario::text, u.email, u.nombre_completo, u.rol_usuario,
                   u.telefono_wa, u.ciudad, u.estado_ven, u.sexo,
                   u.estado_suscripcion, u.creado_en, u.ultimo_login,
                   COALESCE(pm.codigo_plan, 'FREE') AS plan
            FROM usuarios u
            LEFT JOIN planes_membresia pm ON pm.id_plan = u.id_plan_actual
            WHERE u.id_usuario = CAST(:id AS uuid)
        """),
        {"id": current_user["id_usuario"]},
    )
    row = result.mappings().first()
    logger.info("update_me | id=%s campos=%s", current_user["id_usuario"], list(updates.keys()))
    return _row_to_user_response(dict(row))
