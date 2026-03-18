"""
Event Logger — registra cada consulta al agente en la tabla consultas_usuarios.

Diseño:
- Siempre best-effort: nunca interrumpe el flujo principal si falla
- Soporta usuarios anónimos (id_usuario=None)
- Mapea las acciones del agente al enum de la DB
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Mapeo accion del agente → tipo en DB
_TIPO_MAP: dict[str, str] = {
    "buscar":    "PRODUCTO_UNICO",
    "lista":     "CARRITO_MULTIPLE",
    "conversar": "PRODUCTO_UNICO",  # fallback
}


async def log_consulta(
    db: AsyncSession,
    texto: str,
    accion: str,
    tokens: int = 0,
    canal: str = "WEB_APP",
    id_usuario: str | None = None,
) -> None:
    """
    Inserta una fila en consultas_usuarios.

    Args:
        db:          Sesión async de SQLAlchemy.
        texto:       Texto original del mensaje del usuario.
        accion:      Acción clasificada por el agente ('buscar'|'lista'|'conversar').
        tokens:      Total de tokens IA consumidos en esta consulta.
        canal:       Canal de origen ('WEB_APP'|'WHATSAPP'|'API').
        id_usuario:  UUID del usuario autenticado (None si es anónimo).
    """
    tipo_db = _TIPO_MAP.get(accion, "PRODUCTO_UNICO")

    try:
        await db.execute(
            text("""
                INSERT INTO consultas_usuarios
                    (id_consulta, id_usuario, texto_consulta_original,
                     tipo_consulta, canal_origen, tokens_ia_consumidos)
                VALUES
                    (:id, :usuario, :texto, :tipo, :canal, :tokens)
            """),
            {
                "id":      str(uuid.uuid4()),
                "usuario": id_usuario,
                "texto":   texto[:1000],   # truncar para no reventar la columna
                "tipo":    tipo_db,
                "canal":   canal,
                "tokens":  tokens,
            },
        )
        await db.commit()
    except Exception as exc:
        # Logging sin interrumpir: el error de auditoría nunca debe romper el chat
        logger.warning("event_logger: no se pudo registrar consulta — %s", exc)
        await db.rollback()
