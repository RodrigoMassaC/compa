"""
Embedder — generación de embeddings para búsqueda semántica.

Provider: OpenAI text-embedding-3-small (1536 dimensiones).
Costo: $0.02 / 1M tokens input. Para Compa (~32k productos × 25 tokens) ≈ $0.02.

Uso:
    from app.services.embeddings.embedder import generar_embedding, generar_embeddings_batch
    vec = await generar_embedding("Colgate Crema Dental Menta 100 ml")
    vecs = await generar_embeddings_batch(["leche", "arroz", ...])
"""
import asyncio
import hashlib
import logging
from typing import List, Optional

from openai import OpenAI, AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cliente sync (para llamadas dentro de threads, ej. desde código sync)
_client_sync: Optional[OpenAI] = None
# Cliente async (para llamadas desde funciones async)
_client_async: Optional[AsyncOpenAI] = None


def _get_sync_client() -> OpenAI:
    global _client_sync
    if _client_sync is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY no configurada. Sin ella no se pueden generar embeddings."
            )
        _client_sync = OpenAI(api_key=settings.openai_api_key)
    return _client_sync


def _get_async_client() -> AsyncOpenAI:
    global _client_async
    if _client_async is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY no configurada. Sin ella no se pueden generar embeddings."
            )
        _client_async = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client_async


def texto_para_embedding(
    nombre_estandar: str,
    marca: Optional[str] = None,
    presentacion: Optional[str] = None,
    terminos_busqueda: Optional[str] = None,
) -> str:
    """
    Construye el texto que se va a vectorizar para un producto.
    Incluye nombre + marca + presentación + términos extra.

    El orden importa: lo más distintivo primero (nombre y marca), luego
    presentación. Términos van al final para no diluir la señal principal.
    """
    partes = [nombre_estandar.strip() if nombre_estandar else ""]
    if marca and marca.lower() not in (nombre_estandar or "").lower():
        partes.append(marca.strip())
    if presentacion and presentacion.lower() not in (nombre_estandar or "").lower():
        partes.append(presentacion.strip())
    if terminos_busqueda:
        partes.append(terminos_busqueda.strip())
    texto = " — ".join(p for p in partes if p)
    # Truncar a 2000 caracteres por seguridad (text-embedding-3-small acepta 8191 tokens)
    return texto[:2000]


def hash_texto(texto: str) -> str:
    """Hash SHA1 del texto — para detectar cambios y marcar embeddings stale."""
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


async def generar_embedding(texto: str) -> List[float]:
    """Genera un embedding de UN texto. Async para no bloquear."""
    client = _get_async_client()
    resp = await client.embeddings.create(
        model=settings.embeddings_model,
        input=texto,
    )
    return resp.data[0].embedding


async def generar_embeddings_batch(textos: List[str], batch_size: int = 100) -> List[List[float]]:
    """
    Genera embeddings de varios textos. OpenAI acepta hasta 2048 textos por
    request, pero usamos 100 para no agotar el rate limit con peticiones gigantes.
    """
    client = _get_async_client()
    todos: List[List[float]] = []
    for i in range(0, len(textos), batch_size):
        chunk = textos[i:i + batch_size]
        try:
            resp = await client.embeddings.create(
                model=settings.embeddings_model,
                input=chunk,
            )
            todos.extend(d.embedding for d in resp.data)
        except Exception as e:
            logger.error(f"Error embedding batch {i}-{i+batch_size}: {e}")
            # En lugar de fallar todo, dejamos None para los del batch fallido
            todos.extend([None] * len(chunk))
        # Pequeña pausa entre batches grandes para no agotar rate limit
        if len(textos) > batch_size:
            await asyncio.sleep(0.1)
    return todos


def generar_embedding_sync(texto: str) -> List[float]:
    """Versión bloqueante de generar_embedding (para usar dentro de un thread)."""
    client = _get_sync_client()
    resp = client.embeddings.create(
        model=settings.embeddings_model,
        input=texto,
    )
    return resp.data[0].embedding
