"""
Cliente HTTP para R4 Conecta (Mibanco).

Helpers:
  - hmac_sha256(message, secret) → string hex (formato del banco)
  - call_bcv() → consulta tasa BCV oficial vía R4 (opcional)
  - call_c2p(...) → cobro C2P (alternativa al pago móvil conciliado)
  - call_vuelto(...) → enviar vuelto en bolívares

Validación de webhooks entrantes:
  - is_allowed_ip(req) → True si la IP origen está en la whitelist de R4
  - is_valid_token(req) → True si el header Authorization coincide con
    nuestro webhook UUID
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── HMAC ──────────────────────────────────────────────────────────────────────

def hmac_sha256(message: str, secret: str) -> str:
    """Firma con HMAC-SHA256 y devuelve hex lowercase, como exige el banco."""
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Validación de webhooks entrantes ─────────────────────────────────────────

def get_client_ip(req: Request) -> str:
    """Extrae la IP real del cliente (respeta X-Forwarded-For por estar tras Caddy/Traefik)."""
    fwd = req.headers.get("x-forwarded-for", "")
    if fwd:
        # Tomamos el primer IP (el cliente original)
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else ""


def is_allowed_ip(req: Request) -> bool:
    """Verifica que la IP del request esté en la whitelist de R4."""
    allowed = {ip.strip() for ip in settings.r4_allowed_ips.split(",") if ip.strip()}
    ip = get_client_ip(req)
    if ip not in allowed:
        logger.warning(f"IP no autorizada para webhook R4: {ip} (whitelist: {allowed})")
        return False
    return True


def is_valid_token(req: Request) -> bool:
    """Verifica que el header Authorization coincida con nuestro webhook token (UUID)."""
    auth = req.headers.get("authorization", "").strip()
    expected = settings.r4_webhook_token.strip()
    if not expected:
        logger.error("R4_WEBHOOK_TOKEN no configurado")
        return False
    if auth != expected:
        logger.warning("Authorization inválido en webhook R4")
        return False
    return True


# ── Llamadas salientes a R4 (opcional, para C2P o tasa BCV) ──────────────────

async def call_bcv(fecha: str, moneda: str = "USD") -> Optional[dict]:
    """Consulta tasa BCV vía R4. Retorna {code, fechavalor, tipocambio} o None.

    fecha: 'YYYY-MM-DD'
    moneda: ISO 4217 (USD, EUR, etc.)
    """
    if not settings.r4_commerce_id or not settings.r4_commerce_token:
        logger.warning("R4 no configurado, skip call_bcv")
        return None

    message = f"{fecha}{moneda}"
    token_auth = hmac_sha256(message, settings.r4_commerce_token)
    headers = {
        "Content-Type": "application/json",
        "Authorization": token_auth,
        "Commerce": settings.r4_commerce_id,
    }
    payload = {"Moneda": moneda, "Fechavalor": fecha}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{settings.r4_api_base}/MBbcv",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"R4 BCV falló: {e}")
            return None


async def call_c2p(
    telefono_destino: str,
    cedula: str,
    banco: str,
    monto: Decimal,
    otp: str,
    concepto: str = "Compa",
    ip: str = "0.0.0.0",
) -> Optional[dict]:
    """Cobro C2P (pago móvil con OTP). Retorna {code, message, reference} o None."""
    if not settings.r4_commerce_id or not settings.r4_commerce_token:
        return None

    monto_str = f"{monto:.2f}"
    message = f"{telefono_destino}{monto_str}{banco}{cedula}"
    token_auth = hmac_sha256(message, settings.r4_commerce_token)

    headers = {
        "Content-Type": "application/json",
        "Authorization": token_auth,
        "Commerce": settings.r4_commerce_id,
    }
    payload = {
        "TelefonoDestino": telefono_destino,
        "Cedula": cedula,
        "Banco": banco,
        "Monto": monto_str,
        "Concepto": concepto[:30],
        "Otp": otp,
        "Ip": ip,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(
                f"{settings.r4_api_base}/MBc2p",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"R4 C2P falló: {e}")
            return None
