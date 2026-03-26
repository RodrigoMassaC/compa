"""
WhatsApp message handler — registro conversacional + agente IA de Compa
========================================================================
Flujo:
  1. Llega mensaje → buscar teléfono en DB
  2. Si registrado  → agente directo (saludo personalizado)
  3. Si no registrado → máquina de estados de registro (4 preguntas)
     Pasos: inicio → confirmacion → nombre → email → ciudad → edad → sexo → cuenta creada
  4. Tras registro → contraseña temporal + aviso de cambio en web
"""
import json
import logging
import random
import string
import uuid
from datetime import datetime

import redis.asyncio as aioredis
from anthropic import Anthropic

from app.core.config import settings
from app.core.security import get_password_hash
from app.services.whatsapp.client import send_text_message

logger = logging.getLogger(__name__)

HISTORY_TTL   = 86400   # 24 h — historial de conversación
REGISTRO_TTL  = 1800    # 30 min — ventana para completar registro
HISTORY_PREFIX  = "wa_historial:"
REGISTRO_PREFIX = "wa_registro:"


# ── Helpers generales ──────────────────────────────────────────────────────────

def _generar_password_temporal() -> str:
    """Genera contraseña temporal tipo: Compa#Xk7mQ2"""
    chars = string.ascii_letters + string.digits
    parte = "".join(random.choices(chars, k=6))
    return f"Compa#{parte}"


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _get_historial(redis: aioredis.Redis, phone: str) -> list[dict]:
    raw = await redis.get(f"{HISTORY_PREFIX}{phone}")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return []


async def _save_historial(redis: aioredis.Redis, phone: str, historial: list[dict]) -> None:
    await redis.setex(f"{HISTORY_PREFIX}{phone}", HISTORY_TTL, json.dumps(historial[-12:]))


async def _get_usuario_by_phone(phone: str) -> dict | None:
    """Busca usuario en DB por telefono_wa. Retorna dict con id/nombre/email o None."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT id_usuario, nombre_completo, email "
                "FROM usuarios WHERE telefono_wa = :phone LIMIT 1"
            ),
            {"phone": phone},
        )
        row = result.fetchone()
        if row:
            return {
                "id": str(row.id_usuario),
                "nombre": row.nombre_completo or "",
                "email": row.email or "",
            }
    return None


async def _crear_usuario_whatsapp(datos: dict) -> str:
    """
    Inserta el usuario en DB con los datos recolectados por WhatsApp.
    Retorna la contraseña temporal generada.
    Lanza ValueError('email_duplicado') si el email ya existe.
    """
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    password_temp = _generar_password_temporal()
    password_hash = get_password_hash(password_temp)

    # Rango de edad → año de nacimiento aproximado
    año_actual = datetime.now().year
    rango_año = {"1": año_actual - 22, "2": año_actual - 30, "3": año_actual - 43, "4": año_actual - 55}
    año_nac = rango_año.get(datos.get("edad", "2"), año_actual - 30)
    fecha_nac = f"{año_nac}-06-15"

    sexo_map = {"1": "M", "2": "F", "3": "OTRO"}
    sexo = sexo_map.get(datos.get("sexo", "3"), "OTRO")

    async with AsyncSessionLocal() as db:
        # Verificar email único
        existing_email = await db.execute(
            text("SELECT 1 FROM usuarios WHERE email = :email LIMIT 1"),
            {"email": datos["email"]},
        )
        if existing_email.scalar():
            raise ValueError("email_duplicado")

        # Verificar teléfono único (por si acaso llegó duplicado antes del INSERT)
        existing_phone = await db.execute(
            text("SELECT 1 FROM usuarios WHERE telefono_wa = :phone LIMIT 1"),
            {"phone": datos["phone"]},
        )
        if existing_phone.scalar():
            raise ValueError("telefono_duplicado")

        # Plan FREE
        plan_result = await db.execute(
            text("SELECT id_plan FROM planes_membresia WHERE codigo_plan = 'FREE' LIMIT 1")
        )
        plan_id = plan_result.scalar()

        await db.execute(
            text("""
                INSERT INTO usuarios
                  (id_usuario, email, password_hash, nombre_completo,
                   telefono_wa, ciudad, fecha_nacimiento, sexo, id_plan_actual, rol_usuario)
                VALUES
                  (:id, :email, :pw_hash, :nombre,
                   :telefono, :ciudad, :fecha_nac::date, :sexo, :plan_id, 'CONSUMIDOR')
            """),
            {
                "id":       str(uuid.uuid4()),
                "email":    datos["email"],
                "pw_hash":  password_hash,
                "nombre":   datos["nombre"],
                "telefono": datos["phone"],
                "ciudad":   datos.get("ciudad", ""),
                "fecha_nac": fecha_nac,
                "sexo":     sexo,
                "plan_id":  str(plan_id) if plan_id else None,
            },
        )
        await db.commit()

    return password_temp


# ── Máquina de estados de registro ────────────────────────────────────────────

async def _manejar_registro(redis: aioredis.Redis, phone: str, mensaje: str) -> str | None:
    """
    Gestiona el flujo conversacional de registro.
    Retorna:
      - str  → texto a enviar al usuario (dentro del flujo de registro)
      - None → señal para pasar al agente IA directamente
    """
    key = f"{REGISTRO_PREFIX}{phone}"
    raw = await redis.get(key)
    estado: dict = json.loads(raw) if raw else {"paso": "inicio"}
    paso = estado.get("paso", "inicio")
    msg = mensaje.strip()

    # ── Inicio: primera vez que escribe ──────────────────────────────────────
    if paso == "inicio":
        estado = {"paso": "confirmacion"}
        await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
        return (
            "¡Hola! Soy *Compa* 🛒, tu asistente de precios en Venezuela.\n\n"
            "Crea tu cuenta gratuita para guardar tu historial y listas de compras.\n"
            "Son solo *4 preguntas rápidas* 😊\n\n"
            "¿Empezamos? Responde *SÍ* para registrarte o *NO* para consultar sin cuenta."
        )

    # ── Confirmación ─────────────────────────────────────────────────────────
    if paso == "confirmacion":
        if msg.upper() in ("SI", "SÍ", "S", "YES", "1", "DALE", "OK", "CLARO", "BUENO", "QUIERO"):
            estado = {"paso": "nombre"}
            await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
            return "¡Perfecto! 👍\n\n*¿Cuál es tu nombre completo?*"
        else:
            # Registro obligatorio — insistir amablemente
            return (
                "Para usar Compa necesitas una cuenta gratuita 😊\n"
                "Solo son 4 preguntas rápidas y listo.\n\n"
                "¿Empezamos? Responde *SÍ*"
            )

    # ── Completado → agente directo ───────────────────────────────────────────
    if paso == "completado":
        return None

    # ── Nombre ───────────────────────────────────────────────────────────────
    if paso == "nombre":
        if len(msg) < 3:
            return "Por favor escribe tu nombre completo. Ej: *María González*"
        estado["nombre"] = msg.title()
        estado["paso"] = "email"
        await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
        return f"Mucho gusto, *{estado['nombre']}* 👋\n\n*¿Cuál es tu correo electrónico?*"

    # ── Email ─────────────────────────────────────────────────────────────────
    if paso == "email":
        if "@" not in msg or "." not in msg.split("@")[-1]:
            return "Ese correo no parece válido. Escríbelo así: *tucorreo@gmail.com*"
        estado["email"] = msg.lower()
        estado["paso"] = "ciudad"
        await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
        return (
            "Perfecto 📧\n\n"
            "*¿En qué ciudad de Venezuela estás?*\n"
            "_Ej: Caracas, Maracaibo, Valencia, Barquisimeto, Mérida..._"
        )

    # ── Ciudad ────────────────────────────────────────────────────────────────
    if paso == "ciudad":
        if len(msg) < 3:
            return "Por favor escribe el nombre de tu ciudad."
        estado["ciudad"] = msg.title()
        estado["paso"] = "edad"
        await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
        return (
            f"¡{estado['ciudad']}! 📍\n\n"
            "*¿Cuál es tu rango de edad?*\n\n"
            "1️⃣  18 – 25 años\n"
            "2️⃣  26 – 35 años\n"
            "3️⃣  36 – 50 años\n"
            "4️⃣  50+ años\n\n"
            "_Responde con el número (1, 2, 3 ó 4)_"
        )

    # ── Edad ──────────────────────────────────────────────────────────────────
    if paso == "edad":
        if msg not in ("1", "2", "3", "4"):
            return "Responde solo con 1, 2, 3 ó 4 según tu rango."
        estado["edad"] = msg
        estado["paso"] = "sexo"
        await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
        return (
            "*¿Cuál es tu género?*\n\n"
            "1️⃣  Masculino\n"
            "2️⃣  Femenino\n"
            "3️⃣  Prefiero no decir\n\n"
            "_Responde con el número_"
        )

    # ── Género → crear cuenta ─────────────────────────────────────────────────
    if paso == "sexo":
        if msg not in ("1", "2", "3"):
            return "Responde solo con 1, 2 ó 3."
        estado["sexo"] = msg
        estado["phone"] = phone

        try:
            password_temp = await _crear_usuario_whatsapp(estado)
        except ValueError as exc:
            if "email_duplicado" in str(exc):
                estado["paso"] = "email"
                await redis.setex(key, REGISTRO_TTL, json.dumps(estado))
                return (
                    "⚠️ Ese correo ya tiene una cuenta en Compa.\n"
                    "Por favor escribe otro correo electrónico:"
                )
            if "telefono_duplicado" in str(exc):
                # Ya existe — cargarlo como usuario registrado
                await redis.setex(key, HISTORY_TTL, json.dumps({"paso": "completado"}))
                return (
                    "ℹ️ Este número ya tiene una cuenta en Compa.\n"
                    "Ingresa a *compa.com.ve* con tu email y contraseña.\n\n"
                    "¿Qué precio estás buscando? 🛒"
                )
            raise

        nombre = estado.get("nombre", "")
        await redis.setex(key, HISTORY_TTL, json.dumps({"paso": "completado", "nombre": nombre}))

        return (
            f"✅ *¡Listo, {nombre}! Tu cuenta está creada.*\n\n"
            f"📧 *Email:* {estado['email']}\n"
            f"🔑 *Contraseña temporal:* `{password_temp}`\n\n"
            f"⚠️ Por seguridad, entra a *compa.com.ve*, inicia sesión y cambia tu contraseña.\n\n"
            f"---\n"
            f"Ahora sí, ¿qué precio estás buscando? 🛒"
        )

    return None


# ── Agente IA ──────────────────────────────────────────────────────────────────

async def _call_agent(mensaje: str, historial: list[dict], nombre_usuario: str = "") -> dict:
    """Llama al agente IA de Compa con contexto del usuario."""
    from app.api.v1.routers.agent import (
        buscar_en_db,
        _prefiltro_substring,
        filtrar_relevantes,
        CLASIFICACION_SYSTEM,
        RESPONSE_SYSTEM,
    )
    from app.core.database import AsyncSessionLocal

    client = Anthropic(api_key=settings.anthropic_api_key)

    historial_reciente = historial[-6:]
    historial_texto = ""
    if historial_reciente:
        historial_texto = "\n\nHistorial reciente:\n"
        for m in historial_reciente:
            rol = "Usuario" if m.get("role") == "user" else "Compa"
            historial_texto += f"{rol}: {m.get('content', '')}\n"

    clasificacion_response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        system=CLASIFICACION_SYSTEM,
        messages=[{"role": "user", "content": f"{historial_texto}\nMensaje actual: {mensaje}"}],
    )

    raw = clasificacion_response.content[0].text.strip().replace("```json", "").replace("```", "").strip()

    try:
        clasificacion = json.loads(raw)
    except json.JSONDecodeError:
        saludo = f", {nombre_usuario}" if nombre_usuario else ""
        return {
            "respuesta": f"Hola{saludo}, soy Compa 🛒 Pregúntame por precios de productos en Venezuela.",
            "productos": [],
        }

    accion = clasificacion.get("accion", "conversar")
    logger.info("WA agent | accion=%s | user=%s | msg=%.60s", accion, nombre_usuario or "anon", mensaje)

    if accion == "conversar":
        return {"respuesta": clasificacion.get("respuesta", "¿En qué te puedo ayudar?"), "productos": []}

    if accion == "buscar":
        terminos = clasificacion.get("terminos", []) or [mensaje.strip()[:50]]

        async with AsyncSessionLocal() as db:
            productos = await buscar_en_db(terminos, db)

        productos = _prefiltro_substring(productos, terminos)
        productos = await filtrar_relevantes(productos, terminos, mensaje, client)

        resultados_str = (
            json.dumps(productos, ensure_ascii=False, indent=2) if productos else "No se encontraron productos."
        )

        mensajes_api = [
            {"role": m.get("role", "user"), "content": m.get("content", "")} for m in historial_reciente
        ]
        ctx_usuario = f"El usuario se llama {nombre_usuario}. " if nombre_usuario else ""
        mensajes_api.append({
            "role": "user",
            "content": (
                f"{ctx_usuario}El usuario preguntó: \"{mensaje}\"\n\n"
                f"Términos buscados: {', '.join(terminos)}\n\n"
                f"Resultados:\n{resultados_str}\n\n"
                f"Responde de forma útil y directa."
            ),
        })

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            system=RESPONSE_SYSTEM,
            messages=mensajes_api,
        )

        return {"respuesta": respuesta_response.content[0].text.strip(), "productos": productos}

    return {"respuesta": clasificacion.get("respuesta", "¿En qué te puedo ayudar?"), "productos": []}


def _format_for_whatsapp(data: dict) -> str:
    """Formatea la respuesta del agente como texto plano para WhatsApp."""
    lines = [data.get("respuesta", ""), ""]
    for i, prod in enumerate(data.get("productos", [])[:5]):
        ofertas = prod.get("ofertas", [])
        if not ofertas:
            continue
        mejor = ofertas[0]
        nombre = f"{prod.get('nombre', '')} {prod.get('presentacion', '')}".strip()
        precio = f"${mejor.get('precio_usd', 0):.2f}"
        tienda = mejor.get("tienda", "")
        prefix = "🏆" if i == 0 else f"{i + 1}."
        lines.append(f"{prefix} *{nombre}* — {precio} en {tienda}")
    return "\n".join(lines).strip()


# ── Punto de entrada ───────────────────────────────────────────────────────────

_MONTHLY_LIMITS_WA = {"FREE": 20, "BASIC": 100, "PRO": 500, "ANON": 10, "B2B_EMPRESA": 9999, "ADMIN": 9999}


async def _verificar_limite_mensual(redis: aioredis.Redis, identifier: str, plan: str) -> bool:
    """Retorna True si puede consultar, False si alcanzó el límite mensual."""
    from datetime import date
    limit = _MONTHLY_LIMITS_WA.get(plan, 20)
    key   = f"rl:monthly:{identifier}:{date.today().strftime('%Y-%m')}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 35 * 86400)
        return count <= limit
    except Exception as exc:
        logger.warning("WA monthly_limit error: %s", exc)
        return True  # fail-open


async def handle_incoming_message(phone: str, mensaje: str) -> None:
    """
    Punto de entrada para un mensaje entrante de WhatsApp.
    phone  : número normalizado (ej: '584141234567')
    mensaje: texto del mensaje recibido
    """
    logger.info("WA message | from=%s msg='%s'", phone, mensaje[:80])
    redis = await _get_redis()

    try:
        usuario = await _get_usuario_by_phone(phone)

        if usuario:
            # ── Verificar límite mensual ───────────────────────────────────────
            plan = usuario.get("plan", "FREE")
            if not await _verificar_limite_mensual(redis, usuario["id"], plan):
                from datetime import date
                from calendar import monthrange
                hoy = date.today()
                dias_restantes = monthrange(hoy.year, hoy.month)[1] - hoy.day
                await send_text_message(phone, (
                    f"⚠️ Alcanzaste el límite de consultas de este mes.\n\n"
                    f"El contador se reinicia en {dias_restantes} días.\n"
                    f"Para consultas ilimitadas, mejora tu plan en *compa.com.ve* 🚀"
                ))
                return

            # ── Agente personalizado ──────────────────────────────────────────
            historial = await _get_historial(redis, phone)
            data = await _call_agent(mensaje, historial, nombre_usuario=usuario["nombre"])
            respuesta = _format_for_whatsapp(data)
            historial.append({"role": "user",      "content": mensaje})
            historial.append({"role": "assistant", "content": data.get("respuesta", respuesta)})
            await _save_historial(redis, phone, historial)
            await send_text_message(phone, respuesta)

        else:
            # ── Usuario no registrado → flujo de registro ─────────────────────
            respuesta_registro = await _manejar_registro(redis, phone, mensaje)

            if respuesta_registro is None:
                historial = await _get_historial(redis, phone)
                data = await _call_agent(mensaje, historial)
                respuesta = _format_for_whatsapp(data)
                historial.append({"role": "user",      "content": mensaje})
                historial.append({"role": "assistant", "content": data.get("respuesta", respuesta)})
                await _save_historial(redis, phone, historial)
                await send_text_message(phone, respuesta)
            else:
                await send_text_message(phone, respuesta_registro)

    except Exception as exc:
        logger.error("handle_incoming_message | error: %s", exc, exc_info=True)
        await send_text_message(phone, "Lo siento, tuve un problema. Intenta de nuevo en un momento. 🙏")
    finally:
        await redis.aclose()
