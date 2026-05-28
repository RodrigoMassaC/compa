"""
Lógica de negocio del Pago Móvil Conciliado.

Funciones principales:
  - PRODUCTOS: catálogo de cosas que se pueden comprar (precios USD)
  - generar_concepto() → CR###### único
  - crear_pago_pendiente(...) → inserta registro y devuelve datos al usuario
  - conciliar_pago(notif) → marca pago como approved, activa el producto
  - activar_producto(...) → suma quota o activa plan ilimitado
"""
import logging
import random
import string
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Catálogo de productos comprables ─────────────────────────────────────────

PRODUCTOS = {
    "consultas_pack_30": {
        "nombre": "Pack de 30 consultas",
        "descripcion": "30 consultas adicionales que se suman a tu cuenta. No expiran.",
        "precio_usd": Decimal("1.50"),
        "tipo": "consultas",       # consultas | plan
        "cantidad": 30,
    },
    "plan_ilimitado_mensual": {
        "nombre": "Plan Ilimitado (1 mes)",
        "descripcion": "Consultas ilimitadas durante 30 días.",
        "precio_usd": Decimal("5.00"),
        "tipo": "plan",
        "dias": 30,
    },
}


# ── Generador de conceptos únicos CR###### ───────────────────────────────────

async def generar_concepto(session: AsyncSession, max_intentos: int = 10) -> str:
    """
    Genera un concepto único de 6 dígitos (CR123456) verificando que no exista
    otro pago `pending` con el mismo concepto.
    """
    for _ in range(max_intentos):
        numero = "".join(random.choices(string.digits, k=6))
        concepto = f"CR{numero}"
        existe = await session.execute(text("""
            SELECT 1 FROM pagos_bolivares
            WHERE concepto = :c AND status = 'pending'
            LIMIT 1
        """), {"c": concepto})
        if not existe.scalar():
            return concepto
    raise RuntimeError("No se pudo generar concepto único")


# ── Tasa BCV ─────────────────────────────────────────────────────────────────

async def get_tasa_bcv(session: AsyncSession) -> Decimal:
    """Lee la tasa BCV más reciente. Si no hay, lanza excepción."""
    r = await session.execute(text("""
        SELECT valor_usd FROM historico_tasa_bcv
        ORDER BY fecha DESC LIMIT 1
    """))
    valor = r.scalar()
    if not valor or valor <= 0:
        raise RuntimeError("No hay tasa BCV en DB")
    return Decimal(str(valor))


# ── Reutilización de pago pending ────────────────────────────────────────────

async def reutilizar_pending(
    session: AsyncSession,
    id_usuario: UUID,
    tipo_producto: str,
) -> Optional[dict]:
    """
    Si el usuario tiene un pago pending del MISMO producto creado hace
    menos de 15 min, lo devuelve para que no genere otro.
    """
    r = await session.execute(text("""
        SELECT id_pago, concepto, monto_bs, monto_usd, tasa_bcv, creado_en
        FROM pagos_bolivares
        WHERE id_usuario = :uid
          AND tipo_producto = :tp
          AND status = 'pending'
          AND creado_en > NOW() - INTERVAL '15 minutes'
        ORDER BY creado_en DESC
        LIMIT 1
    """), {"uid": str(id_usuario), "tp": tipo_producto})
    row = r.fetchone()
    if not row:
        return None
    return {
        "id_pago": row.id_pago,
        "concepto": row.concepto,
        "monto_bs": float(row.monto_bs),
        "monto_usd": float(row.monto_usd),
        "tasa_bcv": float(row.tasa_bcv),
    }


# ── Crear pago pendiente ─────────────────────────────────────────────────────

async def crear_pago_pendiente(
    session: AsyncSession,
    id_usuario: UUID,
    tipo_producto: str,
) -> dict:
    """
    Crea un pago pendiente. Si ya existe uno reciente del mismo producto, lo reutiliza.

    Retorna dict con todos los datos que el frontend necesita para mostrar
    al usuario las instrucciones del Pago Móvil.
    """
    if tipo_producto not in PRODUCTOS:
        raise ValueError(f"Producto desconocido: {tipo_producto}")
    producto = PRODUCTOS[tipo_producto]

    # 1. ¿Hay pending reciente del mismo producto?
    reuso = await reutilizar_pending(session, id_usuario, tipo_producto)
    if reuso:
        logger.info(f"Reutilizando pago pending {reuso['concepto']} para usuario {id_usuario}")
        return _datos_para_frontend(producto, reuso)

    # 2. Generar concepto único
    concepto = await generar_concepto(session)

    # 3. Calcular monto en Bs con tasa BCV vigente
    tasa = await get_tasa_bcv(session)
    precio_usd: Decimal = producto["precio_usd"]
    monto_bs = (precio_usd * tasa).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 4. Insertar
    referencia = f"{tipo_producto}|{concepto}"
    r = await session.execute(text("""
        INSERT INTO pagos_bolivares (
            id_usuario, concepto, referencia_interna, metodo,
            monto_bs, monto_usd, tasa_bcv, status,
            tipo_producto, cantidad
        ) VALUES (
            :uid, :c, :ref, 'pago_movil',
            :bs, :usd, :tasa, 'pending',
            :tp, :cant
        )
        RETURNING id_pago, creado_en
    """), {
        "uid": str(id_usuario),
        "c": concepto,
        "ref": referencia,
        "bs": monto_bs,
        "usd": precio_usd,
        "tasa": tasa,
        "tp": tipo_producto,
        "cant": producto.get("cantidad", 1),
    })
    row = r.fetchone()
    await session.commit()
    logger.info(f"💰 Pago pending creado: {concepto} {precio_usd}USD/{monto_bs}Bs usuario={id_usuario}")

    return _datos_para_frontend(producto, {
        "concepto": concepto,
        "monto_bs": float(monto_bs),
        "monto_usd": float(precio_usd),
        "tasa_bcv": float(tasa),
    })


def _datos_para_frontend(producto: dict, pago: dict) -> dict:
    """Construye el payload que la UI usa para mostrar las instrucciones."""
    return {
        "concepto": pago["concepto"],
        "monto_bs": pago["monto_bs"],
        "monto_usd": pago["monto_usd"],
        "tasa_bcv": pago["tasa_bcv"],
        "destino": {
            "telefono": settings.r4_commerce_phone,
            "banco": settings.r4_commerce_bank,
            "rif": settings.r4_commerce_id,
        },
        "producto": {
            "nombre": producto["nombre"],
            "descripcion": producto["descripcion"],
        },
        "ttl_minutos": settings.pago_pending_ttl_min,
    }


# ── Conciliación: webhook r4-notifica ────────────────────────────────────────

# Tolerancia de comparación de montos: 1% (cubre redondeo del banco)
TOLERANCIA_MONTO = Decimal("0.01")


async def conciliar_pago(session: AsyncSession, notif: dict) -> dict:
    """
    Procesa una notificación de pago entrante de R4.

    notif esperado:
      { IdComercio, TelefonoComercio, TelefonoEmisor, Concepto, BancoEmisor,
        Monto, FechaHora, Referencia, CodigoRed }

    Retorna {abono: True/False} según se haya aprobado el pago.
    """
    concepto = (notif.get("Concepto") or "").strip()
    codigo_red = str(notif.get("CodigoRed") or "")
    monto_recibido = Decimal(str(notif.get("Monto") or 0))

    if not concepto:
        logger.warning("r4-notifica sin concepto — ignorado")
        return {"abono": False}

    # Buscar pago pending con ese concepto
    r = await session.execute(text("""
        SELECT id_pago, id_usuario, tipo_producto, cantidad,
               monto_bs, monto_usd, tasa_bcv
        FROM pagos_bolivares
        WHERE concepto = :c AND status = 'pending'
        LIMIT 1
    """), {"c": concepto})
    pago = r.fetchone()

    if not pago:
        logger.warning(f"r4-notifica: no encontré pago pending con concepto={concepto}")
        return {"abono": False}

    # Validar codigo_red: 00 = aprobado
    if codigo_red != "00":
        logger.warning(f"r4-notifica: concepto={concepto} codigo_red={codigo_red} — rechazado")
        await session.execute(text("""
            UPDATE pagos_bolivares
            SET status = 'rejected',
                motivo_rechazo = :m,
                codigo_red = :cr,
                actualizado_en = NOW()
            WHERE id_pago = :id
        """), {
            "m": f"Banco rechazó: codigo_red={codigo_red}",
            "cr": codigo_red,
            "id": pago.id_pago,
        })
        await session.commit()
        return {"abono": False}

    # Validar monto (tolerancia 1%)
    monto_esperado = Decimal(str(pago.monto_bs))
    if monto_esperado > 0:
        diff = abs(monto_recibido - monto_esperado) / monto_esperado
        if diff > TOLERANCIA_MONTO:
            logger.warning(
                f"r4-notifica: concepto={concepto} monto no coincide. "
                f"esperado={monto_esperado} recibido={monto_recibido} diff={diff:.4f}"
            )
            await session.execute(text("""
                UPDATE pagos_bolivares
                SET status = 'rejected',
                    motivo_rechazo = :m,
                    actualizado_en = NOW()
                WHERE id_pago = :id
            """), {
                "m": f"Monto no coincide: esperado={monto_esperado} recibido={monto_recibido}",
                "id": pago.id_pago,
            })
            await session.commit()
            return {"abono": False}

    # Aprobado: marcar y activar producto
    await session.execute(text("""
        UPDATE pagos_bolivares
        SET status = 'approved',
            telefono_emisor = :te,
            banco_emisor = :be,
            codigo_red = :cr,
            referencia_banco = :ref,
            fecha_pago_banco = :fh,
            aprobado_en = NOW(),
            actualizado_en = NOW()
        WHERE id_pago = :id
    """), {
        "te": notif.get("TelefonoEmisor"),
        "be": notif.get("BancoEmisor"),
        "cr": codigo_red,
        "ref": notif.get("Referencia"),
        "fh": notif.get("FechaHora"),
        "id": pago.id_pago,
    })

    # Activar el producto comprado
    await _activar_producto(
        session,
        id_usuario=pago.id_usuario,
        tipo_producto=pago.tipo_producto,
        cantidad=pago.cantidad,
    )

    await session.commit()
    logger.info(f"✅ Pago APROBADO: {concepto} usuario={pago.id_usuario} producto={pago.tipo_producto}")
    return {"abono": True}


async def _activar_producto(
    session: AsyncSession,
    id_usuario: UUID,
    tipo_producto: str,
    cantidad: int,
):
    """Aplica el producto comprado a la cuenta del usuario.

    IMPORTANTE: el límite mensual se controla en REDIS (rl:monthly:*), no en
    la tabla quota_consultas. Por eso aquí escribimos en AMBOS:
      - Redis  → para que el rate-limiter (web + WhatsApp) vea las consultas
                 al instante. Esto es lo que realmente desbloquea al usuario.
      - quota_consultas (Postgres) → registro persistente de auditoría.
    """
    # 1) Registro persistente en Postgres (auditoría)
    await session.execute(text("""
        INSERT INTO quota_consultas (id_usuario)
        VALUES (:uid)
        ON CONFLICT (id_usuario) DO NOTHING
    """), {"uid": str(id_usuario)})

    if tipo_producto == "consultas_pack_30":
        await session.execute(text("""
            UPDATE quota_consultas
            SET consultas_extra = COALESCE(consultas_extra, 0) + :c,
                actualizado_en = NOW()
            WHERE id_usuario = :uid
        """), {"c": cantidad or 30, "uid": str(id_usuario)})

    elif tipo_producto == "plan_ilimitado_mensual":
        await session.execute(text("""
            UPDATE quota_consultas
            SET plan_ilimitado_hasta = CASE
                WHEN plan_ilimitado_hasta IS NULL OR plan_ilimitado_hasta < NOW()
                THEN NOW() + INTERVAL '30 days'
                ELSE plan_ilimitado_hasta + INTERVAL '30 days'
            END,
            actualizado_en = NOW()
            WHERE id_usuario = :uid
        """), {"uid": str(id_usuario)})

    else:
        logger.error(f"_activar_producto: tipo_producto desconocido: {tipo_producto}")
        return

    # 2) Aplicar en Redis (lo que realmente controla el límite)
    await _aplicar_en_redis(str(id_usuario), tipo_producto, cantidad or 30)


async def _aplicar_en_redis(id_usuario: str, tipo_producto: str, cantidad: int):
    """Escribe el beneficio comprado en Redis para que el rate-limiter lo vea.

    Claves:
      rl:monthly:bonus:{uid}:{mes}  → consultas extra del mes (pack)
      rl:monthly:unlimited:{uid}    → si existe y no expiró → ilimitado
    """
    import redis.asyncio as aioredis
    from datetime import date

    try:
        redis = aioredis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=2
        )
    except Exception as exc:
        logger.error(f"_aplicar_en_redis: no pude conectar a Redis: {exc}")
        return

    try:
        if tipo_producto == "consultas_pack_30":
            mes = date.today().strftime("%Y-%m")
            key_bonus = f"rl:monthly:bonus:{id_usuario}:{mes}"
            nuevo = await redis.incrby(key_bonus, cantidad)
            await redis.expire(key_bonus, 35 * 86400)
            logger.info(
                f"💳 Redis bonus actualizado uid={id_usuario} +{cantidad} → {nuevo} ({mes})"
            )

        elif tipo_producto == "plan_ilimitado_mensual":
            key_unlim = f"rl:monthly:unlimited:{id_usuario}"
            ttl_actual = await redis.ttl(key_unlim)  # -2 no existe, -1 sin TTL
            base = ttl_actual if ttl_actual and ttl_actual > 0 else 0
            nuevo_ttl = base + 30 * 86400
            vence = (datetime.utcnow() + timedelta(seconds=nuevo_ttl)).isoformat()
            await redis.set(key_unlim, vence, ex=nuevo_ttl)
            logger.info(
                f"♾️ Redis plan ilimitado uid={id_usuario} vence={vence} ttl={nuevo_ttl}s"
            )
    except Exception as exc:
        logger.error(f"_aplicar_en_redis: error aplicando {tipo_producto}: {exc}")
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass
