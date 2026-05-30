"""
Compi — el producto B2B de Compa.
==================================
Endpoints:

  Solicitudes públicas:
    POST   /b2b/solicitar                  → form de contacto (público o auth)

  Empresa del usuario logueado:
    GET    /b2b/empresa/me                 → datos de mi empresa (404 si no tengo)
    GET    /b2b/empresa/me/dashboard       → KPIs reales (Básico)
    GET    /b2b/empresa/me/precios?categoria=X
                                           → análisis de precios por rubro
    GET    /b2b/empresa/me/demograficos    → distribución sexo / edad / ciudad
    GET    /b2b/empresa/me/tendencias      → top rubros + evolución mensual
    GET    /b2b/empresa/me/visibilidad     → menciones de mi cadena + clicks

  Admin (asignación manual mientras no haya self-checkout):
    GET    /b2b/admin/solicitudes          → listar pendientes
    POST   /b2b/admin/empresas             → crear empresa desde solicitud
    PATCH  /b2b/admin/empresas/{id}        → editar plan, estado, fechas
    POST   /b2b/admin/enriquecer-historico → enriquecer consultas históricas
"""
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_optional_user
from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_empresa_del_usuario(db: AsyncSession, id_usuario: str) -> Optional[dict]:
    """Devuelve la empresa donde el usuario tiene acceso (owner/admin/viewer)."""
    r = await db.execute(text("""
        SELECT
            e.id_empresa::text,
            e.nombre_comercial,
            e.rif,
            e.sector,
            e.plan,
            e.estado,
            e.activada_en,
            e.activa_hasta,
            e.cadenas_focus,
            COALESCE(eu.rol, CASE WHEN e.id_usuario_dueno = CAST(:uid AS uuid) THEN 'owner' END) AS rol
        FROM empresas e
        LEFT JOIN empresa_usuarios eu
               ON eu.id_empresa = e.id_empresa
              AND eu.id_usuario = CAST(:uid AS uuid)
        WHERE e.estado = 'activa'
          AND (e.id_usuario_dueno = CAST(:uid AS uuid) OR eu.id_usuario IS NOT NULL)
        ORDER BY e.activada_en DESC
        LIMIT 1
    """), {"uid": id_usuario})
    row = r.mappings().first()
    return dict(row) if row else None


async def _require_empresa(db: AsyncSession, id_usuario: str) -> dict:
    empresa = await _get_empresa_del_usuario(db, id_usuario)
    if not empresa:
        raise HTTPException(
            status_code=404,
            detail="No tienes acceso a ninguna empresa Compi activa. Solicita acceso desde /empresas.",
        )
    return empresa


def _require_admin(user: dict) -> None:
    if user.get("rol_usuario") != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo ADMIN")


# ── 1. POST /b2b/solicitar (público o autenticado) ───────────────────────────

class SolicitudCreate(BaseModel):
    nombre_comercial: str
    rif:              Optional[str] = None
    sector:           Optional[str] = None       # supermercado | farmacia | bodega | otros
    contacto_nombre:  str
    contacto_email:   EmailStr
    contacto_telefono: Optional[str] = None
    plan_interes:     Optional[str] = "no_seguro"  # basico|pro|premium|no_seguro
    mensaje:          Optional[str] = None


@router.post("/solicitar", status_code=201)
async def solicitar_acceso(
    body: SolicitudCreate,
    user: Optional[dict] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una solicitud de acceso B2B. Público — no requiere login."""
    plan = body.plan_interes if body.plan_interes in ("basico","pro","premium","no_seguro") else "no_seguro"

    r = await db.execute(text("""
        INSERT INTO solicitudes_b2b (
            nombre_comercial, rif, sector,
            contacto_nombre, contacto_email, contacto_telefono,
            plan_interes, mensaje, estado
        ) VALUES (
            :nombre, :rif, :sector,
            :cnombre, :cemail, :ctel,
            :plan, :msj, 'pendiente'
        )
        RETURNING id_solicitud::text
    """), {
        "nombre": body.nombre_comercial.strip(),
        "rif":    body.rif,
        "sector": body.sector,
        "cnombre": body.contacto_nombre.strip(),
        "cemail": body.contacto_email,
        "ctel":   body.contacto_telefono,
        "plan":   plan,
        "msj":    body.mensaje,
    })
    await db.commit()
    row = r.mappings().first()
    logger.info("b2b solicitud creada: %s — %s (%s)", row["id_solicitud"], body.nombre_comercial, plan)
    return {"id_solicitud": row["id_solicitud"], "estado": "pendiente"}


# ── 2. GET /b2b/empresa/me ───────────────────────────────────────────────────

@router.get("/empresa/me")
async def mi_empresa(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve la empresa activa del usuario, o 404."""
    return await _require_empresa(db, user["id_usuario"])


# ── 3. GET /b2b/empresa/me/dashboard ─────────────────────────────────────────

@router.get("/empresa/me/dashboard")
async def dashboard_empresa(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """KPIs principales para el dashboard B2B (Plan Básico).

    Devuelve:
      - total_consultas_mes  → cuántas consultas hubo en Compa este mes
      - menciones_mi_cadena  → cuántas veces se nombró mi cadena (vis. digital)
      - rubros_top           → 5 rubros más comparados
      - tasa_bcv_actual      → última tasa BCV
      - tasa_bcv_evolucion   → últimos 30 días
    """
    empresa = await _require_empresa(db, user["id_usuario"])
    nombre_cadena = empresa["nombre_comercial"]

    # Consultas del mes
    r1 = await db.execute(text("""
        SELECT COUNT(*) AS total
        FROM consultas_usuarios
        WHERE fecha_consulta >= date_trunc('month', NOW())
    """))
    total_mes = r1.scalar() or 0

    # Menciones de mi cadena este mes
    r2 = await db.execute(text("""
        SELECT COUNT(*) AS total
        FROM consultas_usuarios
        WHERE fecha_consulta >= date_trunc('month', NOW())
          AND cadena_mencionada ILIKE :c
    """), {"c": nombre_cadena})
    menciones = r2.scalar() or 0

    # Top 5 rubros del mes
    r3 = await db.execute(text("""
        SELECT rubro_detectado AS rubro, COUNT(*) AS n
        FROM consultas_usuarios
        WHERE fecha_consulta >= date_trunc('month', NOW())
          AND rubro_detectado IS NOT NULL
        GROUP BY rubro_detectado
        ORDER BY n DESC
        LIMIT 5
    """))
    rubros_top = [dict(row) for row in r3.mappings().all()]

    # Tasa BCV actual + evolución 30d
    r4 = await db.execute(text("""
        SELECT fecha::date AS fecha, valor_usd
        FROM historico_tasa_bcv
        WHERE fecha >= NOW() - INTERVAL '30 days'
        ORDER BY fecha ASC
    """))
    bcv = [{"fecha": str(row["fecha"]), "valor": float(row["valor_usd"])} for row in r4.mappings().all()]

    return {
        "empresa": {
            "nombre": empresa["nombre_comercial"],
            "plan":   empresa["plan"],
        },
        "kpis": {
            "consultas_mes_total":      total_mes,
            "menciones_mi_cadena_mes":  menciones,
            "porcentaje_menciones":     round((menciones / total_mes * 100), 2) if total_mes else 0,
            "rubros_top":               rubros_top,
        },
        "tasa_bcv": {
            "actual":     bcv[-1]["valor"] if bcv else None,
            "evolucion":  bcv,
        },
    }


# ── 4. GET /b2b/empresa/me/precios ──────────────────────────────────────────

@router.get("/empresa/me/precios")
async def precios_por_rubro(
    categoria: Optional[str] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Análisis de precios: mín / máx / promedio del mercado para un rubro.

    Si no se especifica `categoria`, devuelve todos los rubros agregados.
    """
    await _require_empresa(db, user["id_usuario"])

    r = await db.execute(text("""
        WITH tasa AS (
            SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1
        ),
        precios_recientes AS (
            SELECT DISTINCT ON (pc.id_producto_maestro, e.id_cadena)
                pc.id_producto_maestro,
                pm.categoria,
                cc.nombre_cadena,
                CASE
                    WHEN hp.moneda_origen = 'USD' THEN hp.precio_bruto
                    WHEN hp.moneda_origen = 'VES' THEN hp.precio_bruto / (SELECT valor_usd FROM tasa)
                END AS precio_usd
            FROM historial_precios hp
            JOIN productos_crudos pc ON pc.id_producto_crudo = hp.id_producto_crudo
            JOIN productos_maestros pm ON pm.id_producto_maestro = pc.id_producto_maestro
            JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
            JOIN cadenas_comerciales cc ON cc.id_cadena = e.id_cadena
            WHERE hp.fecha_lectura >= NOW() - INTERVAL '60 days'
              AND NOT (
                (hp.moneda_origen = 'VES' AND hp.precio_bruto < 1)
                OR (hp.moneda_origen = 'USD' AND hp.precio_bruto < 0.05)
              )
              AND (:cat::text IS NULL OR pm.categoria = :cat)
            ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
        )
        SELECT
            categoria,
            COUNT(DISTINCT id_producto_maestro) AS productos,
            ROUND(MIN(precio_usd)::numeric, 2)  AS precio_min,
            ROUND(MAX(precio_usd)::numeric, 2)  AS precio_max,
            ROUND(AVG(precio_usd)::numeric, 2)  AS precio_promedio,
            ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY precio_usd)::numeric, 2) AS precio_mediano
        FROM precios_recientes
        WHERE categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY productos DESC
    """), {"cat": categoria})

    return [dict(row) for row in r.mappings().all()]


# ── 5. GET /b2b/empresa/me/demograficos ─────────────────────────────────────

@router.get("/empresa/me/demograficos")
async def demograficos(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Distribución demográfica de quienes consultan a Compa (últimos 90 días)."""
    await _require_empresa(db, user["id_usuario"])

    # Por sexo
    r1 = await db.execute(text("""
        SELECT COALESCE(u.sexo, 'no_indica') AS sexo, COUNT(c.id_consulta) AS n
        FROM consultas_usuarios c
        LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
        WHERE c.fecha_consulta >= NOW() - INTERVAL '90 days'
        GROUP BY u.sexo
        ORDER BY n DESC
    """))
    por_sexo = [dict(row) for row in r1.mappings().all()]

    # Por ciudad (top 10)
    r2 = await db.execute(text("""
        SELECT COALESCE(u.ciudad, 'no_indica') AS ciudad, COUNT(c.id_consulta) AS n
        FROM consultas_usuarios c
        LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
        WHERE c.fecha_consulta >= NOW() - INTERVAL '90 days'
          AND u.id_usuario IS NOT NULL
        GROUP BY u.ciudad
        ORDER BY n DESC
        LIMIT 10
    """))
    por_ciudad = [dict(row) for row in r2.mappings().all()]

    # Por estado
    r3 = await db.execute(text("""
        SELECT COALESCE(u.estado_ven, 'no_indica') AS estado, COUNT(c.id_consulta) AS n
        FROM consultas_usuarios c
        LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
        WHERE c.fecha_consulta >= NOW() - INTERVAL '90 days'
          AND u.id_usuario IS NOT NULL
        GROUP BY u.estado_ven
        ORDER BY n DESC
        LIMIT 10
    """))
    por_estado = [dict(row) for row in r3.mappings().all()]

    return {
        "por_sexo":   por_sexo,
        "por_ciudad": por_ciudad,
        "por_estado": por_estado,
        "rango":      "90 días",
    }


# ── 6. GET /b2b/empresa/me/tendencias ───────────────────────────────────────

@router.get("/empresa/me/tendencias")
async def tendencias(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tendencias del mercado: rubros top + evolución mensual."""
    await _require_empresa(db, user["id_usuario"])

    # Top rubros últimos 90 días
    r1 = await db.execute(text("""
        SELECT rubro_detectado AS rubro, COUNT(*) AS consultas
        FROM consultas_usuarios
        WHERE fecha_consulta >= NOW() - INTERVAL '90 days'
          AND rubro_detectado IS NOT NULL
        GROUP BY rubro_detectado
        ORDER BY consultas DESC
        LIMIT 15
    """))
    top_rubros = [dict(row) for row in r1.mappings().all()]

    # Evolución mensual de consultas totales
    r2 = await db.execute(text("""
        SELECT to_char(date_trunc('month', fecha_consulta), 'YYYY-MM') AS mes,
               COUNT(*) AS consultas
        FROM consultas_usuarios
        WHERE fecha_consulta >= NOW() - INTERVAL '12 months'
        GROUP BY date_trunc('month', fecha_consulta)
        ORDER BY mes
    """))
    evolucion = [dict(row) for row in r2.mappings().all()]

    return {
        "top_rubros":         top_rubros,
        "evolucion_mensual":  evolucion,
        "rango":              "90 días / 12 meses",
    }


# ── 7. GET /b2b/empresa/me/visibilidad ──────────────────────────────────────

@router.get("/empresa/me/visibilidad")
async def visibilidad_digital(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Visibilidad digital de la cadena del usuario."""
    empresa = await _require_empresa(db, user["id_usuario"])
    nombre = empresa["nombre_comercial"]

    # Evolución mensual de menciones de mi cadena
    r1 = await db.execute(text("""
        SELECT to_char(date_trunc('month', fecha_consulta), 'YYYY-MM') AS mes,
               COUNT(*) AS menciones
        FROM consultas_usuarios
        WHERE fecha_consulta >= NOW() - INTERVAL '12 months'
          AND cadena_mencionada ILIKE :c
        GROUP BY date_trunc('month', fecha_consulta)
        ORDER BY mes
    """), {"c": nombre})
    menciones_mensual = [dict(row) for row in r1.mappings().all()]

    # Compararme con las otras cadenas (ranking del mes)
    r2 = await db.execute(text("""
        SELECT cadena_mencionada AS cadena, COUNT(*) AS menciones
        FROM consultas_usuarios
        WHERE fecha_consulta >= date_trunc('month', NOW())
          AND cadena_mencionada IS NOT NULL
        GROUP BY cadena_mencionada
        ORDER BY menciones DESC
    """))
    ranking_cadenas = [dict(row) for row in r2.mappings().all()]

    # Clicks hacia mi cadena (si trackeamos)
    r3 = await db.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE tipo_destino = 'web') AS web,
               COUNT(*) FILTER (WHERE tipo_destino = 'whatsapp') AS whatsapp
        FROM clicks_cadena cc
        JOIN cadenas_comerciales c ON c.id_cadena = cc.id_cadena
        WHERE c.nombre_cadena ILIKE :n
          AND cc.creado_en >= NOW() - INTERVAL '30 days'
    """), {"n": nombre})
    clicks = dict(r3.mappings().first() or {"total": 0, "web": 0, "whatsapp": 0})

    return {
        "menciones_mensual":  menciones_mensual,
        "ranking_cadenas":    ranking_cadenas,
        "clicks_30d":         clicks,
    }


# ── 8. Endpoints ADMIN ──────────────────────────────────────────────────────

@router.get("/admin/solicitudes")
async def admin_solicitudes(
    estado: Optional[str] = "pendiente",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista solicitudes B2B por estado. Solo ADMIN."""
    _require_admin(user)

    r = await db.execute(text("""
        SELECT id_solicitud::text, nombre_comercial, rif, sector,
               contacto_nombre, contacto_email, contacto_telefono,
               plan_interes, mensaje, estado,
               creado_en, atendida_en,
               id_empresa_creada::text
        FROM solicitudes_b2b
        WHERE :estado::text IS NULL OR estado = :estado
        ORDER BY creado_en DESC
        LIMIT 100
    """), {"estado": estado})
    rows = [dict(row) for row in r.mappings().all()]
    for d in rows:
        for k in ("creado_en","atendida_en"):
            if d.get(k):
                d[k] = d[k].isoformat()
    return rows


class CrearEmpresaRequest(BaseModel):
    id_solicitud:     Optional[str] = None
    id_usuario_dueno: Optional[str] = None      # si None, intenta resolver por email
    nombre_comercial: str
    rif:              Optional[str] = None
    sector:           Optional[str] = None
    plan:             str = "basico"
    activa_hasta:     Optional[str] = None      # ISO date, opcional
    cadenas_focus:    Optional[list[str]] = None


@router.post("/admin/empresas", status_code=201)
async def admin_crear_empresa(
    body: CrearEmpresaRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una empresa B2B activa para un usuario (admin). Opcionalmente
    enlaza con una solicitud previa y la marca como 'activada'."""
    _require_admin(user)

    if body.plan not in ("basico","pro","premium"):
        raise HTTPException(status_code=400, detail="plan inválido")

    # Resolver dueño
    dueno_id = body.id_usuario_dueno
    if not dueno_id and body.id_solicitud:
        s = await db.execute(text("""
            SELECT contacto_email FROM solicitudes_b2b
            WHERE id_solicitud = CAST(:id AS uuid)
        """), {"id": body.id_solicitud})
        row = s.mappings().first()
        if row:
            u = await db.execute(text("""
                SELECT id_usuario::text FROM usuarios WHERE email = :e
            """), {"e": row["contacto_email"]})
            urow = u.mappings().first()
            if urow:
                dueno_id = urow["id_usuario"]

    activa_hasta_param = body.activa_hasta
    if not activa_hasta_param:
        activa_hasta_param = (date.today() + timedelta(days=30)).isoformat()

    r = await db.execute(text("""
        INSERT INTO empresas (
            id_usuario_dueno, nombre_comercial, rif, sector,
            plan, estado, activa_hasta, cadenas_focus
        ) VALUES (
            CAST(:uid AS uuid), :nombre, :rif, :sector,
            :plan, 'activa', CAST(:hasta AS timestamptz),
            :focus
        )
        RETURNING id_empresa::text
    """), {
        "uid":    dueno_id,
        "nombre": body.nombre_comercial,
        "rif":    body.rif,
        "sector": body.sector,
        "plan":   body.plan,
        "hasta":  activa_hasta_param,
        "focus":  body.cadenas_focus,
    })
    empresa_id = r.mappings().first()["id_empresa"]

    if body.id_solicitud:
        await db.execute(text("""
            UPDATE solicitudes_b2b
            SET estado = 'activada',
                id_empresa_creada = CAST(:eid AS uuid),
                atendida_en = NOW()
            WHERE id_solicitud = CAST(:sid AS uuid)
        """), {"sid": body.id_solicitud, "eid": empresa_id})

    await db.commit()
    logger.info("b2b empresa activada %s plan=%s dueño=%s", empresa_id, body.plan, dueno_id)
    return {"id_empresa": empresa_id, "estado": "activa"}


class PatchEmpresaRequest(BaseModel):
    plan:         Optional[str] = None
    estado:       Optional[str] = None
    activa_hasta: Optional[str] = None
    cadenas_focus: Optional[list[str]] = None
    notas_admin:  Optional[str] = None


@router.patch("/admin/empresas/{id_empresa}")
async def admin_editar_empresa(
    id_empresa: str,
    body: PatchEmpresaRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edita plan/estado/fechas/notas de una empresa. Solo ADMIN."""
    _require_admin(user)

    sets, params = [], {"id": id_empresa}
    if body.plan is not None:
        if body.plan not in ("basico","pro","premium"):
            raise HTTPException(400, "plan inválido")
        sets.append("plan = :plan"); params["plan"] = body.plan
    if body.estado is not None:
        if body.estado not in ("activa","pausada","cancelada"):
            raise HTTPException(400, "estado inválido")
        sets.append("estado = :estado"); params["estado"] = body.estado
    if body.activa_hasta is not None:
        sets.append("activa_hasta = CAST(:hasta AS timestamptz)"); params["hasta"] = body.activa_hasta
    if body.cadenas_focus is not None:
        sets.append("cadenas_focus = :focus"); params["focus"] = body.cadenas_focus
    if body.notas_admin is not None:
        sets.append("notas_admin = :notas"); params["notas"] = body.notas_admin

    if not sets:
        return {"ok": True, "cambios": 0}

    sets.append("actualizado_en = NOW()")
    await db.execute(text(f"""
        UPDATE empresas SET {", ".join(sets)} WHERE id_empresa = CAST(:id AS uuid)
    """), params)
    await db.commit()
    return {"ok": True, "cambios": len(sets) - 1}


# ── 9. POST /b2b/admin/enriquecer-historico (one-shot batch) ────────────────

@router.post("/admin/enriquecer-historico")
async def admin_enriquecer_historico(
    limite: int = 5000,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enriquece consultas históricas con rubro+cadena (regex). Solo ADMIN.

    Útil tras desplegar la migración para popular la columna en datos viejos.
    """
    _require_admin(user)
    from app.services.b2b.enriquecedor import enriquecer_pendientes
    n = await enriquecer_pendientes(db, limite=limite)
    return {"procesadas": n}
