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

    # ── Meta / WhatsApp ──
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""
    meta_verify_token: str = ""

    # ── Stripe ──
    stripe_secret_key: str = ""

    # ── Ambiente ──
    env: str = "development"
    log_level: str = "INFO"

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
