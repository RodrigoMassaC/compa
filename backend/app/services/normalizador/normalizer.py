"""
Normalizador IA para Compa
==========================
Toma productos_crudos con estado_mapeo='PENDIENTE' y los mapea a productos_maestros
extrayendo nombre estandar, marca, presentacion (con gramaje EXPLÍCITO),
unidad de medida y categoria.

Provider configurable vía settings.normalizador_provider:
  - "deepseek"  → DeepSeek V4 Flash (default — más barato, ~$5-8 USD para 35k productos)
  - "anthropic" → Claude Haiku 4.5 (fallback)

Uso:
    python -m app.services.normalizador.normalizer
    python -m app.services.normalizador.normalizer --limit 100
    python -m app.services.normalizador.normalizer --dry-run
    python -m app.services.normalizador.normalizer --concurrency 3
"""

import asyncio
import json
import logging
import argparse
import re
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
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
# Prompt — más estricto: forzamos a que el gramaje y la marca aparezcan
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un experto en normalización de productos de supermercados y farmacias venezolanas.
Tu tarea es analizar nombres de productos crudos y extraer información estructurada.

Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni backticks.

Estructura del JSON:
{
  "nombre_estandar": "Marca + Producto + Atributo + Presentación EXACTA con gramaje/volumen",
  "marca": "Solo el nombre de la marca o null",
  "presentacion": "Cantidad y unidad EXACTA del nombre original (ej: '500 ml', '120 g', '30 tabletas') o null",
  "unidad_medida": "kg | g | l | ml | un | sob | caja | tabletas | cápsulas | comprimidos",
  "gramaje_valor": número (ej. 500, 120, 1.5) — solo el número de la presentación, sin unidad,
  "gramaje_unidad": "ml | g | kg | l | un | tabletas | cápsulas | comprimidos | sob",
  "categoria": "alimentos | bebidas | higiene | medicamentos",
  "terminos_busqueda": "Palabras separadas por coma para búsqueda (marca, nombre genérico, sinónimos)"
}

REGLAS CRÍTICAS:

1. PRESERVA EL GRAMAJE EXACTO del nombre original.
   - "Aceite Capri Oliva 500ml" → presentacion="500 ml", gramaje_valor=500, gramaje_unidad="ml"
   - "Aceite Capri Oliva 1L" → presentacion="1 L", gramaje_valor=1, gramaje_unidad="l"
   - Si el nombre tiene 120GR y otro 400GR, son productos DISTINTOS.

2. PRESERVA LA MARCA EXACTA.
   - "Aceite Capri Extra Virgen 500ml" → marca="Capri"
   - "Aceite Iberia Extra Virgen 500ml" → marca="Iberia"
   - NUNCA mezcles marcas. Si hay duda, marca=null mejor que asumir.

3. nombre_estandar DEBE incluir marca + presentación.
   - ✅ "Capri Aceite de Oliva Extra Virgen 500 ml"
   - ✅ "Iberia Aceite de Oliva Extra Virgen 500 ml"
   - ❌ "Aceite de Oliva Extra Virgen" (sin marca ni gramaje)

4. Capitaliza correctamente. Sin MAYÚSCULAS COMPLETAS.

5. Normaliza unidades:
   - GR/Gr → "g"
   - ML/Ml → "ml"
   - KG/Kg → "kg"
   - LT/Lt → "l"
   - UN/Und → "un"

6. Para medicamentos preserva DOSIS + cantidad de unidades:
   - "Omeprazol 20 mg x 14 cápsulas" → presentacion="20 mg x 14 cápsulas"
   - gramaje_valor=14, gramaje_unidad="cápsulas"

EJEMPLOS:

Entrada: "Cereal Flips Chocolate Bolsa 400 GR"
Salida:
{
  "nombre_estandar": "Flips Cereal Chocolate 400 g",
  "marca": "Flips",
  "presentacion": "400 g",
  "unidad_medida": "g",
  "gramaje_valor": 400,
  "gramaje_unidad": "g",
  "categoria": "alimentos",
  "terminos_busqueda": "cereal, flips, chocolate, desayuno"
}

Entrada: "Cereal Flips Chocolate Bolsa 120 GR"
Salida:
{
  "nombre_estandar": "Flips Cereal Chocolate 120 g",
  "marca": "Flips",
  "presentacion": "120 g",
  "unidad_medida": "g",
  "gramaje_valor": 120,
  "gramaje_unidad": "g",
  "categoria": "alimentos",
  "terminos_busqueda": "cereal, flips, chocolate, desayuno"
}

Entrada: "ACEITE OLIVA EXTRA VIRGEN IBERIA 500ML"
Salida:
{
  "nombre_estandar": "Iberia Aceite de Oliva Extra Virgen 500 ml",
  "marca": "Iberia",
  "presentacion": "500 ml",
  "unidad_medida": "ml",
  "gramaje_valor": 500,
  "gramaje_unidad": "ml",
  "categoria": "alimentos",
  "terminos_busqueda": "aceite, oliva, extra virgen, iberia"
}"""

USER_PROMPT_TEMPLATE = """Normaliza este producto venezolano:

Nombre crudo: {nombre}

Responde SOLO con el JSON, sin texto adicional."""


# ---------------------------------------------------------------------------
# Helpers de extracción de gramaje
# ---------------------------------------------------------------------------

GRAMAJE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ml|ML|Ml|gr|GR|Gr|kg|KG|Kg|lt|LT|Lt|l|L|g|G|un|Un|UN|"
    r"tabletas|tableta|cápsulas|cápsula|capsulas|capsula|comprimidos|comprimido|"
    r"sobres|sobre|ampollas|ampolla|óvulos|ovulos)",
    re.IGNORECASE,
)

UNIDAD_NORMALIZADA = {
    "ml": "ml", "gr": "g", "g": "g", "kg": "kg", "lt": "l", "l": "l", "un": "un",
    "tabletas": "tabletas", "tableta": "tabletas",
    "cápsulas": "cápsulas", "cápsula": "cápsulas",
    "capsulas": "cápsulas", "capsula": "cápsulas",
    "comprimidos": "comprimidos", "comprimido": "comprimidos",
    "sobres": "sob", "sobre": "sob",
    "ampollas": "ampollas", "ampolla": "ampollas",
    "óvulos": "óvulos", "ovulos": "óvulos",
}


def extraer_gramaje(texto: str) -> Optional[Tuple[float, str]]:
    """
    Extrae (valor, unidad_normalizada) del texto. None si no encuentra.

    Para nombres con varios gramajes (ej. "Omeprazol 20 mg x 14 cápsulas"),
    prioriza el ÚLTIMO match (suele ser el conteo de unidades).
    """
    matches = GRAMAJE_RE.findall(texto or "")
    if not matches:
        return None

    # Tomar el último (suele ser el contenido del envase, no la dosis individual)
    valor_str, unidad_raw = matches[-1]
    try:
        valor = float(valor_str.replace(",", "."))
    except ValueError:
        return None

    unidad = UNIDAD_NORMALIZADA.get(unidad_raw.lower(), unidad_raw.lower())
    return valor, unidad


# ---------------------------------------------------------------------------
# Cliente abstracto: DeepSeek o Anthropic
# ---------------------------------------------------------------------------

class _ClienteIA:
    """Wrapper unificado que usa DeepSeek (vía OpenAI SDK) o Anthropic."""

    def __init__(self, provider: str):
        self.provider = provider
        if provider == "deepseek":
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
            )
            self.model = settings.deepseek_model
        elif provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self.model = "claude-haiku-4-5"
        else:
            raise ValueError(f"Provider desconocido: {provider}")

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        """Llamada bloqueante. Retorna el texto de respuesta.

        Para DeepSeek usamos response_format=json_object para evitar que el
        modelo incluya texto fuera del JSON. max_tokens=800 da margen para
        productos con nombres largos (medicamentos compuestos, etc.).
        """
        if self.provider == "deepseek":
            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.0,  # Determinístico
                stream=False,
                response_format={"type": "json_object"},  # JSON puro
            )
            # Para deepseek-v4-* desactivamos thinking (no lo necesitamos)
            if "v4" in self.model:
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            resp = self.client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        # anthropic
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class NormalizadorIA:
    def __init__(self, dry_run: bool = False, provider: Optional[str] = None, concurrency: int = 3):
        self.dry_run = dry_run
        self.provider = provider or settings.normalizador_provider
        self.concurrency = max(1, concurrency)
        self.client = _ClienteIA(self.provider)
        self.engine = create_async_engine(settings.database_url, echo=False)
        self.AsyncSession = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.stats = {
            "procesados": 0,
            "mapeados": 0,
            "nuevos_maestros": 0,
            "errores": 0,
            "requieren_humano": 0,
        }
        # Lock para INSERT de productos_maestros (evita races con concurrency>1)
        self._maestro_lock = asyncio.Lock()

    async def run(self, limit: Optional[int] = None, batch_size: int = 20):
        logger.info(
            f"{'[DRY RUN] ' if self.dry_run else ''}Iniciando Normalizador "
            f"provider={self.provider} model={self.client.model} concurrency={self.concurrency}"
        )

        async with self.AsyncSession() as session:
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

            logger.info(f"Procesando lote de {len(lote)} productos (concurrency={self.concurrency})...")

            # Procesamiento concurrente con semáforo
            sem = asyncio.Semaphore(self.concurrency)

            async def bound(row):
                async with sem:
                    await self._procesar_producto(row.id_producto_crudo, row.nombre_original)

            await asyncio.gather(*(bound(row) for row in lote))
            procesados_total += len(lote)

            await asyncio.sleep(0.3)

        logger.info(f"Normalizador finalizado. Stats: {self.stats}")
        await self.engine.dispose()

    async def _procesar_producto(self, id_producto_crudo: UUID, nombre_original: str):
        self.stats["procesados"] += 1
        try:
            datos = await self._extraer_datos(nombre_original)
            if not datos:
                await self._marcar_estado(id_producto_crudo, "REQUIERE_HUMANO")
                self.stats["requieren_humano"] += 1
                return

            id_maestro = await self._buscar_o_crear_maestro(datos, nombre_original)

            if not self.dry_run:
                await self._vincular(id_producto_crudo, id_maestro)

            self.stats["mapeados"] += 1
            logger.info(f"✅ '{nombre_original[:60]}' → '{datos['nombre_estandar']}'")

        except Exception as e:
            logger.error(f"❌ Error procesando '{nombre_original[:60]}': {e}")
            await self._marcar_estado(id_producto_crudo, "REQUIERE_HUMANO")
            self.stats["errores"] += 1

    async def _extraer_datos(self, nombre: str) -> Optional[dict]:
        """Llama al modelo y parsea el JSON. Ejecuta en thread para no bloquear."""
        try:
            raw = await asyncio.to_thread(
                self.client.chat,
                SYSTEM_PROMPT,
                USER_PROMPT_TEMPLATE.format(nombre=nombre),
                800,
            )
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            datos = json.loads(raw)

            required = ["nombre_estandar", "marca", "presentacion", "unidad_medida", "categoria", "terminos_busqueda"]
            for field in required:
                if field not in datos:
                    logger.warning(f"Campo faltante '{field}' en respuesta para: {nombre}")
                    return None

            if datos["categoria"] not in CATEGORIAS:
                datos["categoria"] = "alimentos"

            # Si el modelo no devolvió gramaje_valor/unidad, los extraemos del original
            if not datos.get("gramaje_valor") or not datos.get("gramaje_unidad"):
                extracted = extraer_gramaje(nombre) or extraer_gramaje(datos.get("presentacion", ""))
                if extracted:
                    datos["gramaje_valor"] = extracted[0]
                    datos["gramaje_unidad"] = extracted[1]

            return datos

        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido para '{nombre}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Error llamando a {self.provider} para '{nombre}': {e}")
            return None

    async def _buscar_o_crear_maestro(self, datos: dict, nombre_original: str) -> UUID:
        """
        Busca un producto maestro EXISTENTE compatible. Si no existe, crea uno.

        Reglas de compatibilidad estrictas — dos productos solo se considera
        el mismo maestro si:
          - misma categoría
          - misma marca (case-insensitive, exacta)
          - mismo gramaje_valor (con tolerancia <5%)
          - misma gramaje_unidad
          - similarity de nombre >= 0.85
        """
        id_categoria = CATEGORIAS[datos["categoria"]]
        nombre_estandar = datos["nombre_estandar"]
        marca_nueva = (datos.get("marca") or "").strip().lower()
        presentacion_nueva = (datos.get("presentacion") or "").strip().lower()
        gramaje_valor = datos.get("gramaje_valor")
        gramaje_unidad = (datos.get("gramaje_unidad") or "").strip().lower()

        async with self.AsyncSession() as session:
            # Buscamos candidatos por similaridad de nombre + categoría
            result = await session.execute(text("""
                SELECT id_producto_maestro, nombre_estandar, marca, presentacion
                FROM productos_maestros
                WHERE nombre_estandar % :nombre
                  AND id_categoria = :id_cat
                ORDER BY similarity(nombre_estandar, :nombre) DESC
                LIMIT 10
            """), {"nombre": nombre_estandar, "id_cat": id_categoria})
            existentes = result.fetchall()

            for existente in existentes:
                marca_existe = (existente.marca or "").strip().lower()
                presentacion_existe = (existente.presentacion or "").strip().lower()

                # ── MARCA: si ambos tienen marca, deben ser iguales (exacto) ──
                if marca_nueva and marca_existe and marca_nueva != marca_existe:
                    continue

                # ── GRAMAJE: comparación por valor y unidad (no similarity) ──
                gramaje_existe = extraer_gramaje(existente.presentacion or "") or \
                                 extraer_gramaje(existente.nombre_estandar or "")

                if gramaje_valor and gramaje_existe:
                    valor_e, unidad_e = gramaje_existe
                    # Unidades distintas → producto distinto
                    if gramaje_unidad and unidad_e and gramaje_unidad != unidad_e:
                        continue
                    # Tolerancia 5% (cubre redondeos como 70 vs 70.5)
                    if abs(valor_e - gramaje_valor) / max(valor_e, gramaje_valor) > 0.05:
                        continue

                # ── SIMILARITY del nombre ≥ 0.85 ──
                sim_result = await session.execute(text("""
                    SELECT similarity(:a, :b) as sim
                """), {"a": nombre_estandar, "b": existente.nombre_estandar})
                sim = sim_result.scalar() or 0

                if sim < 0.85:
                    continue

                # Match
                logger.debug(
                    f"Match (sim={sim:.2f}, marca={marca_existe}): "
                    f"'{existente.nombre_estandar}'"
                )
                return existente.id_producto_maestro

            # No encontró match → crear nuevo
            if self.dry_run:
                logger.info(f"[DRY RUN] Crearía maestro: '{nombre_estandar}'")
                return UUID("00000000-0000-0000-0000-000000000000")

            # Lock para evitar que dos workers concurrentes creen el mismo maestro
            async with self._maestro_lock:
                # Re-check después del lock (otro worker pudo haberlo creado)
                result = await session.execute(text("""
                    SELECT id_producto_maestro FROM productos_maestros
                    WHERE nombre_estandar = :nombre AND id_categoria = :id_cat
                    LIMIT 1
                """), {"nombre": nombre_estandar, "id_cat": id_categoria})
                ya_existe = result.scalar()
                if ya_existe:
                    return ya_existe

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
    parser.add_argument("--batch-size", type=int, default=30, help="Tamaño del lote (default: 30)")
    parser.add_argument("--concurrency", type=int, default=3, help="Llamadas IA en paralelo (default: 3)")
    parser.add_argument(
        "--provider",
        choices=["deepseek", "anthropic"],
        default=None,
        help="Provider IA (default: lee de settings.normalizador_provider)",
    )
    args = parser.parse_args()

    normalizador = NormalizadorIA(
        dry_run=args.dry_run,
        provider=args.provider,
        concurrency=args.concurrency,
    )
    await normalizador.run(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    asyncio.run(main())
