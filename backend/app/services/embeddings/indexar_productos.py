"""
Script de indexación masiva de embeddings.

Genera el embedding de TODOS los productos_maestros que no lo tengan
o tengan un hash de texto distinto al actual (lo que indica que fueron
modificados desde la última indexación).

Uso:
    python -m app.services.embeddings.indexar_productos
    python -m app.services.embeddings.indexar_productos --batch-size 50

Costos: ~$0.02 USD por cada 32k productos (text-embedding-3-small).
Tiempo: ~15 min para 30k productos con batch-size=100.
"""
import argparse
import asyncio
import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.embeddings.embedder import (
    texto_para_embedding,
    hash_texto,
    generar_embeddings_batch,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("IndexarEmbeddings")


async def main(batch_size: int = 100, only_missing: bool = False):
    engine = create_async_engine(settings.database_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        # Contar pendientes
        result = await session.execute(text("""
            SELECT COUNT(*) FROM productos_maestros
            WHERE embedding IS NULL
               OR embedding_texto_hash IS NULL
        """))
        total_pendientes = result.scalar() or 0
        logger.info(f"Productos sin embedding o con hash desactualizado: {total_pendientes}")

        if total_pendientes == 0:
            logger.info("Nada que hacer. Todos los productos ya tienen embedding.")
            await engine.dispose()
            return

    procesados = 0
    while True:
        async with Session() as session:
            # Tomar el siguiente lote
            query = """
                SELECT id_producto_maestro, nombre_estandar, marca, presentacion, terminos_busqueda
                FROM productos_maestros
                WHERE embedding IS NULL OR embedding_texto_hash IS NULL
                ORDER BY id_producto_maestro
                LIMIT :lim
            """
            result = await session.execute(text(query), {"lim": batch_size})
            lote = result.fetchall()

        if not lote:
            logger.info("Indexación completa.")
            break

        # Construir textos
        textos = [
            texto_para_embedding(
                row.nombre_estandar,
                row.marca,
                row.presentacion,
                row.terminos_busqueda,
            )
            for row in lote
        ]

        logger.info(f"Generando embeddings de {len(textos)} productos (procesados: {procesados})...")
        embeddings = await generar_embeddings_batch(textos, batch_size=batch_size)

        # Guardar en DB
        async with Session() as session:
            for row, texto, emb in zip(lote, textos, embeddings):
                if emb is None:
                    logger.warning(f"  ⚠️  Falló embedding para: {row.nombre_estandar[:60]}")
                    continue
                vector_str = "[" + ",".join(str(x) for x in emb) + "]"
                h = hash_texto(texto)
                await session.execute(text("""
                    UPDATE productos_maestros
                    SET embedding = :emb,
                        embedding_texto_hash = :hash,
                        embedding_actualizado_en = NOW()
                    WHERE id_producto_maestro = :id
                """), {
                    "emb": vector_str,
                    "hash": h,
                    "id": str(row.id_producto_maestro),
                })
            await session.commit()

        procesados += len(lote)
        logger.info(f"  ✅ Lote guardado. Total procesados: {procesados}")

    logger.info(f"🏁 Indexación finalizada. Total: {procesados}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Productos por batch (default: 100)")
    args = parser.parse_args()
    asyncio.run(main(batch_size=args.batch_size))
