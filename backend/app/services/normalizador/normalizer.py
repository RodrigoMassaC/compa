"""
Normalizador IA para Compa
==========================
Toma productos_crudos con estado_mapeo='PENDIENTE' y los mapea a productos_maestros
usando Claude (claude-haiku-4-5) para extraer nombre estandar, marca, presentacion,
unidad de medida y categoria.

Uso:
    python -m app.services.normalizador.normalizer
    python -m app.services.normalizador.normalizer --limit 100
    python -m app.services.normalizador.normalizer --dry-run
"""

import asyncio
import json
import logging
import argparse
from decimal import Decimal
from typing import Optional
from uuid import UUID

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("Normalizador")

# ---------------------------------------------------------------------------
# Categorías disponibles en la DB (nivel 1)
# ---------------------------------------------------------------------------
CATEGORIAS = {
    "alimentos":     "bc60dedd-82c3-43bd-ba3c-8e26548965fb",
    "bebidas":       "4bcc6340-a330-4218-baac-63475f5e2461",
    "higiene":       "8b658f8a-945c-4a79-9525-7068f6d7780d",
    "medicamentos":  "79793cc8-0ee2-45d0-a325-4677b2b199bb",
}

# ---------------------------------------------------------------------------
# Prompt para Claude
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un experto en normalización de productos de supermercados y farmacias venezolanas.
Tu tarea es analizar nombres de productos crudos (tal como aparecen en tiendas online venezolanas)
y extraer información estructurada.

Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni backticks.

El JSON debe tener exactamente estos campos:
{
  "nombre_estandar": "Nombre limpio y estandarizado del producto (marca + nombre + presentación)",
  "marca": "Marca del producto o null si no se puede determinar",
  "presentacion": "Cantidad y unidad de presentación (ej: '1 kg', '500 ml', '12 un') o null",
  "unidad_medida": "Unidad base: 'kg', 'g', 'l', 'ml', 'un', 'sob', 'caja' u otra unidad apropiada, o null",
  "categoria": "Una de: alimentos, bebidas, higiene, medicamentos",
  "terminos_busqueda": "Lista de términos separados por coma para búsqueda (marca, nombre genérico, sinónimos)"
}

Reglas:
- nombre_estandar: Capitalizar correctamente (ej: "Leche Entera Parmalat 1 L"), sin mayúsculas completas
- marca: Solo la marca, sin el nombre del producto
- presentacion: Normalizar unidades (ML→ml, KG→kg, GR→g, UN→un, SOB→sob)
- categoria: Clasificar según el tipo de producto
- terminos_busqueda: Incluir marca, nombre genérico del producto, posibles búsquedas del usuario"""

USER_PROMPT_TEMPLATE = """Normaliza este producto venezolano:

Nombre crudo: {nombre}

Responde SOLO con el JSON, sin texto adicional."""


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class NormalizadorIA:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.engine = create_async_engine(settings.database_url, echo=False)
        self.AsyncSession = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.stats = {"procesados": 0, "mapeados": 0, "nuevos_maestros": 0, "errores": 0, "requieren_humano": 0}

    async def run(self, limit: Optional[int] = None, batch_size: int = 20):
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Iniciando Normalizador IA")

        async with self.AsyncSession() as session:
            # Contar pendientes
            result = await session.execute(text(
                "SELECT COUNT(*) FROM productos_crudos WHERE estado_mapeo = 'PENDIENTE'"
            ))
            total_pendientes = result.scalar()
            logger.info(f"Productos PENDIENTE en DB: {total_pendientes}")

            if limit:
                logger.info(f"Procesando máximo {limit} productos")

        procesados_total = 0

        while True:
            lote_limit = batch_size
            if limit:
                restante = limit - procesados_total
                if restante <= 0:
                    break
                lote_limit = min(batch_size, restante)

            async with self.AsyncSession() as session:
                result = await session.execute(text("""
                    SELECT id_producto_crudo, nombre_original, sku_comercio, id_establecimiento
                    FROM productos_crudos
                    WHERE estado_mapeo = 'PENDIENTE'
                    ORDER BY creado_en ASC
                    LIMIT :lim
                """), {"lim": lote_limit})
                lote = result.fetchall()

            if not lote:
                logger.info("No hay más productos PENDIENTE.")
                break

            logger.info(f"Procesando lote de {len(lote)} productos...")

            for row in lote:
                await self._procesar_producto(
                    id_producto_crudo=row.id_producto_crudo,
                    nombre_original=row.nombre_original,
                )
                procesados_total += 1

            await asyncio.sleep(0.5)  # pausa entre lotes para no saturar la API

        logger.info(f"Normalizador finalizado. Stats: {self.stats}")
        await self.engine.dispose()

    async def _procesar_producto(self, id_producto_crudo: UUID, nombre_original: str):
        self.stats["procesados"] += 1
        try:
            # 1. Llamar a Claude para extraer datos
            datos = await self._extraer_datos_claude(nombre_original)
            if not datos:
                await self._marcar_estado(id_producto_crudo, "REQUIERE_HUMANO")
                self.stats["requieren_humano"] += 1
                return

            # 2. Buscar o crear producto maestro
            id_maestro = await self._buscar_o_crear_maestro(datos, nombre_original)

            # 3. Vincular producto crudo con maestro
            if not self.dry_run:
                await self._vincular(id_producto_crudo, id_maestro)

            self.stats["mapeados"] += 1
            logger.info(f"✅ '{nombre_original[:60]}' → '{datos['nombre_estandar']}'")

        except Exception as e:
            logger.error(f"❌ Error procesando '{nombre_original[:60]}': {e}")
            await self._marcar_estado(id_producto_crudo, "REQUIERE_HUMANO")
            self.stats["errores"] += 1

    async def _extraer_datos_claude(self, nombre: str) -> Optional[dict]:
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(nombre=nombre)
                }]
            )
            raw = response.content[0].text.strip()
            # Limpiar backticks si Claude los incluyó por error
            raw = raw.replace("```json", "").replace("```", "").strip()
            datos = json.loads(raw)

            # Validar campos requeridos
            required = ["nombre_estandar", "marca", "presentacion", "unidad_medida", "categoria", "terminos_busqueda"]
            for field in required:
                if field not in datos:
                    logger.warning(f"Campo faltante '{field}' en respuesta Claude para: {nombre}")
                    return None

            # Validar categoría
            if datos["categoria"] not in CATEGORIAS:
                datos["categoria"] = "alimentos"  # fallback

            return datos

        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido de Claude para '{nombre}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Error llamando a Claude para '{nombre}': {e}")
            return None

    async def _buscar_o_crear_maestro(self, datos: dict, nombre_original: str) -> UUID:
        id_categoria = CATEGORIAS[datos["categoria"]]
        nombre_estandar = datos["nombre_estandar"]

        async with self.AsyncSession() as session:
            # Buscar por similitud usando índice GIN (trigrams)
            result = await session.execute(text("""
                SELECT id_producto_maestro, nombre_estandar
                FROM productos_maestros
                WHERE nombre_estandar % :nombre
                  AND id_categoria = :id_cat
                ORDER BY similarity(nombre_estandar, :nombre) DESC
                LIMIT 1
            """), {"nombre": nombre_estandar, "id_cat": id_categoria})
            existente = result.fetchone()

            if existente:
                sim_result = await session.execute(text("""
                    SELECT similarity(:a, :b) as sim
                """), {"a": nombre_estandar, "b": existente.nombre_estandar})
                sim = sim_result.scalar()

                if sim >= 0.6:
                    logger.debug(f"Match encontrado (sim={sim:.2f}): '{existente.nombre_estandar}'")
                    return existente.id_producto_maestro

            # No existe — crear nuevo producto maestro
            if self.dry_run:
                logger.info(f"[DRY RUN] Crearía maestro: '{nombre_estandar}'")
                return UUID("00000000-0000-0000-0000-000000000000")

            result = await session.execute(text("""
                INSERT INTO productos_maestros (
                    id_categoria, nombre_estandar, marca, presentacion,
                    unidad_medida, terminos_busqueda, activo
                ) VALUES (
                    :id_cat, :nombre, :marca, :presentacion,
                    :unidad, :terminos, true
                )
                RETURNING id_producto_maestro
            """), {
                "id_cat":      id_categoria,
                "nombre":      nombre_estandar,
                "marca":       datos.get("marca"),
                "presentacion": datos.get("presentacion"),
                "unidad":      datos.get("unidad_medida"),
                "terminos":    datos.get("terminos_busqueda"),
            })
            await session.commit()
            nuevo_id = result.scalar()
            self.stats["nuevos_maestros"] += 1
            logger.debug(f"Nuevo maestro creado: '{nombre_estandar}'")
            return nuevo_id

    async def _vincular(self, id_producto_crudo: UUID, id_producto_maestro: UUID):
        async with self.AsyncSession() as session:
            await session.execute(text("""
                UPDATE productos_crudos
                SET id_producto_maestro = :id_maestro,
                    estado_mapeo = 'MAPEA_OK'
                WHERE id_producto_crudo = :id_crudo
            """), {"id_maestro": id_producto_maestro, "id_crudo": id_producto_crudo})
            await session.commit()

    async def _marcar_estado(self, id_producto_crudo: UUID, estado: str):
        if self.dry_run:
            return
        async with self.AsyncSession() as session:
            await session.execute(text("""
                UPDATE productos_crudos
                SET estado_mapeo = :estado
                WHERE id_producto_crudo = :id
            """), {"estado": estado, "id": id_producto_crudo})
            await session.commit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Normalizador IA de productos Compa")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de productos a procesar")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la DB")
    parser.add_argument("--batch-size", type=int, default=20, help="Tamaño del lote (default: 20)")
    args = parser.parse_args()

    normalizador = NormalizadorIA(dry_run=args.dry_run)
    await normalizador.run(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    asyncio.run(main())
