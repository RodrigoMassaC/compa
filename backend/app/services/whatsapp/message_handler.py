"""
WhatsApp message handler — procesa los mensajes entrantes y los
enruta al agente IA de Compa, luego envía la respuesta de vuelta.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.whatsapp.client import send_text_message

logger = logging.getLogger(__name__)

# Historial por número de teléfono en Redis (TTL 24h)
HISTORY_TTL = 86400
HISTORY_PREFIX = "wa_historial:"


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _get_historial(redis: aioredis.Redis, phone: str) -> list[dict]:
    import json
    raw = await redis.get(f"{HISTORY_PREFIX}{phone}")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return []


async def _save_historial(redis: aioredis.Redis, phone: str, historial: list[dict]) -> None:
    import json
    await redis.setex(f"{HISTORY_PREFIX}{phone}", HISTORY_TTL, json.dumps(historial[-12:]))  # max 12 turnos


async def _call_agent(mensaje: str, historial: list[dict]) -> dict:
    """Llama al agente IA con el mismo flujo que /agent/chat."""
    from app.api.v1.routers.agent import _clasificar_mensaje, _buscar_productos, _generar_respuesta
    # Reutilizamos las funciones internas del agente
    clasificacion = await _clasificar_mensaje(mensaje, historial)
    if clasificacion.get("accion") == "buscar":
        productos = await _buscar_productos(clasificacion.get("terminos", []), mensaje)
        respuesta = await _generar_respuesta(mensaje, productos, historial)
        return {"respuesta": respuesta, "productos": productos}
    else:
        respuesta = await _generar_respuesta(mensaje, [], historial)
        return {"respuesta": respuesta}


def _format_for_whatsapp(data: dict) -> str:
    """
    Formatea la respuesta del agente como texto plano para WhatsApp.
    Elimina markdown que WhatsApp no renderiza igual que web.
    """
    respuesta = data.get("respuesta", "")
    productos = data.get("productos", [])

    lines = [respuesta, ""]

    for i, prod in enumerate(productos[:5]):
        ofertas = prod.get("ofertas", [])
        if not ofertas:
            continue
        mejor = ofertas[0]
        nombre = f"{prod.get('nombre', '')} {prod.get('presentacion', '')}".strip()
        precio = f"${mejor.get('precio_usd', 0):.2f}"
        tienda = mejor.get("tienda", "")
        prefix = "🏆" if i == 0 else f"{i+1}."
        lines.append(f"{prefix} *{nombre}* — {precio} en {tienda}")

    return "\n".join(lines).strip()


async def handle_incoming_message(phone: str, mensaje: str) -> None:
    """
    Punto de entrada para un mensaje entrante de WhatsApp.
    phone: número normalizado (ej: '584141234567')
    mensaje: texto del mensaje
    """
    logger.info("WA message | from=%s msg='%s'", phone, mensaje[:60])

    redis = await _get_redis()
    historial = await _get_historial(redis, phone)

    try:
        data = await _call_agent(mensaje, historial)
        respuesta_texto = _format_for_whatsapp(data)
    except Exception as exc:
        logger.error("handle_incoming_message | agente falló: %s", exc)
        respuesta_texto = "Lo siento, tuve un problema procesando tu consulta. Intenta de nuevo."

    # Guardar historial actualizado
    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": data.get("respuesta", respuesta_texto)})
    await _save_historial(redis, phone, historial)

    # Enviar respuesta por WhatsApp
    await send_text_message(phone, respuesta_texto)
    await redis.aclose()
