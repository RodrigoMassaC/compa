"""
WhatsApp Business API — cliente HTTP.
Envía mensajes de texto y plantillas via Meta Cloud API.
"""
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

WA_API_URL = "https://graph.facebook.com/v19.0"


async def send_text_message(to: str, body: str) -> bool:
    """
    Envía un mensaje de texto plano al número de WhatsApp indicado.
    `to` debe incluir código de país sin el '+' (ej: '584141234567').
    Retorna True si el envío fue exitoso.
    """
    if not settings.meta_whatsapp_token or not settings.meta_phone_number_id:
        logger.warning("send_text_message: META_WHATSAPP_TOKEN o META_PHONE_NUMBER_ID no configurados")
        return False

    url = f"{WA_API_URL}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},  # Meta limita a 4096 chars
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info("send_text_message | to=%s OK", to)
                return True
            else:
                logger.error("send_text_message | to=%s status=%s body=%s", to, resp.status_code, resp.text)
                return False
    except Exception as exc:
        logger.error("send_text_message | excepción: %s", exc)
        return False
