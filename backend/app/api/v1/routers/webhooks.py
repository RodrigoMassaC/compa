"""
Webhooks — Compa API
=====================
GET  /webhooks/whatsapp  → verificación del webhook por Meta
POST /webhooks/whatsapp  → mensajes entrantes de WhatsApp
"""
import logging
import hmac
import hashlib
from typing import Any

from fastapi import APIRouter, Request, Response, Query, HTTPException

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """
    Verifica la firma SHA-256 que Meta incluye en cada webhook POST.
    Meta firma con el App Secret (no con el access token).
    Previene que actores externos llamen al endpoint con datos falsos.
    Si META_APP_SECRET no está configurado, se omite la verificación
    (útil en entornos locales donde Meta no puede firmar).
    """
    if not settings.meta_app_secret:
        logger.warning("META_APP_SECRET no configurado — verificación de firma omitida")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.meta_app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


# ── GET /webhooks/whatsapp — verificación inicial de Meta ────────────────────

@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Meta envía un GET al configurar el webhook.
    Verifica el token y devuelve el challenge para confirmar propiedad.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("verify_webhook: token válido, respondiendo challenge")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("verify_webhook: token inválido recibido")
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


# ── POST /webhooks/whatsapp — mensajes entrantes ─────────────────────────────

@router.post("/whatsapp", status_code=200)
async def receive_whatsapp(request: Request):
    """
    Recibe eventos de WhatsApp Business API.
    Procesa mensajes de texto y los enruta al agente IA.
    Meta requiere respuesta 200 en menos de 20 segundos (procesamos en background).
    """
    body = await request.body()

    # Verificar firma (solo en producción — en dev puede estar vacía)
    if settings.env == "production":
        signature = request.headers.get("x-hub-signature-256", "")
        if not _verify_signature(body, signature):
            logger.warning("receive_whatsapp: firma inválida")
            raise HTTPException(status_code=403, detail="Firma inválida")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return {"status": "ok"}

    # Extraer mensajes del payload
    entry = payload.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                if msg.get("type") != "text":
                    continue  # solo texto por ahora
                phone = msg.get("from", "")
                texto = msg.get("text", {}).get("body", "").strip()
                if phone and texto:
                    # Procesar en background para responder 200 inmediatamente
                    import asyncio
                    from app.services.whatsapp.message_handler import handle_incoming_message
                    asyncio.create_task(handle_incoming_message(phone, texto))

    return {"status": "ok"}
