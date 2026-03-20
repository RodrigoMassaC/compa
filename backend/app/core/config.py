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
