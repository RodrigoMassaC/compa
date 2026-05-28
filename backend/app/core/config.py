"""
Configuración central de la aplicación Compa.
Usa pydantic-settings para leer variables desde .env de forma tipada.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración completa del entorno de Compa."""

    # ── Base de datos ──
    database_url: str

    # ── Redis ──
    redis_url: str = "redis://compa-redis:6379"

    # ── Seguridad JWT ──
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ── OpenAI / Anthropic ──
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Embeddings (búsqueda semántica con pgvector) ──
    embeddings_provider: str = "openai"   # solo "openai" por ahora
    embeddings_model: str = "text-embedding-3-small"
    embeddings_dimensions: int = 1536     # text-embedding-3-small → 1536
    # Threshold de cercanía coseno (0-1). >= 0.5 es relevante; >= 0.65 muy relevante.
    embeddings_similarity_min: float = 0.30
    # Si el TOP match está por debajo de este threshold, devolvemos "no encontrado"
    embeddings_no_match_below: float = 0.25

    # ── DeepSeek (usado por el normalizador masivo) ──
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    # Provider del normalizador: "deepseek" o "anthropic"
    normalizador_provider: str = "deepseek"

    # ── R4 Conecta / Mibanco (Pago Móvil Conciliado) ──
    r4_api_base:           str = "https://r4conecta.mibanco.com.ve"
    r4_commerce_id:        str = ""   # RIF del comercio (ej. J507982904)
    r4_commerce_token:     str = ""   # HMAC secret entregado por Mibanco
    r4_commerce_phone:     str = ""   # Teléfono destino del pago móvil (04XXXXXXXXX)
    r4_commerce_bank:      str = "0169"   # Banco destino (Mibanco = 0169)
    r4_webhook_token:      str = ""   # UUID que enviamos a Mibanco para validar webhooks entrantes
    # IPs autorizadas de R4 (para validar webhooks entrantes) — comma-separated
    r4_allowed_ips:        str = "45.175.213.98,200.74.203.91,204.199.249.3"
    # Si False, NO se rechaza por IP (solo se loguea). Útil mientras Mibanco
    # confirma sus IPs de salida reales. La autenticación por token UUID sigue
    # activa. Poner True en producción una vez verificadas las IPs.
    r4_enforce_ip_whitelist: bool = True
    # Duración de un pago pending antes de marcarlo expired (minutos)
    pago_pending_ttl_min:  int = 30

    # ── Meta / WhatsApp ──
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""
    meta_waba_id: str = ""
    meta_verify_token: str = ""
    meta_app_secret: str = ""  # Para verificar firmas SHA-256 de webhooks

    # ── Stripe ──
    stripe_secret_key: str = ""

    # ── Resend (emails transaccionales) ──
    resend_api_key: str = ""
    resend_from_email: str = "Compa <noreply@compa.com.ve>"

    # ── CORS — orígenes permitidos (separados por coma en producción) ──
    allowed_origins: str = "http://localhost:3000"

    # ── Ambiente ──
    env: str = "development"
    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """Parsea allowed_origins en lista."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración."""
    return Settings()


# Instancia global para importación directa
settings = get_settings()
