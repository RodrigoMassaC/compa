"""
Agente IA de Compa (compatible con anthropic>=0.26)
====================================================
POST /api/v1/agent/chat
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from anthropic import Anthropic
from app.core.database import get_db
from app.core.config import settings
from app.services.event_logger import log_consulta
from app.api.dependencies import get_optional_user, check_rate_limit, check_monthly_limit
import json

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    mensaje: str
    historial: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]


class ChatResponse(BaseModel):
    respuesta: str
    productos: list[dict] = []
    tipo: str = "texto"
    carrito: dict | None = None


# ---------------------------------------------------------------------------
# Búsqueda en DB — acepta lista de términos para mayor cobertura
# ---------------------------------------------------------------------------

# Sinónimos coloquiales venezolanos para enriquecer el query del embedding.
# Si el usuario usa el lado izquierdo, expandimos con el derecho para que
# el vector apunte mejor al concepto real (ej. "pasta dental" → "pasta dental
# crema dental dentífrico higiene bucal" en vez de solo "pasta dental"
# que se puede confundir con pasta de comer).
SINONIMOS_VE = {
    # ── Bodega / abarrotes ──────────────────────────────────────────────
    "pasta dental": "crema dental dentífrico higiene bucal",
    "pasta de dientes": "crema dental dentífrico higiene bucal",
    "papel toilette": "papel higiénico",
    "papel toilet": "papel higiénico",
    "guayoyo": "café molido café",
    "harina precocida": "harina pan harina P.A.N. harina de maíz",
    "harina P.A.N.": "harina precocida harina de maíz",
    "kotex": "toallas sanitarias toallas higiénicas femeninas",
    "cocacola": "coca-cola refresco cola",
    "papas fritas": "papas fritas snacks de papa chips",
    # ── Farmacia: analgésicos / antifebriles ────────────────────────────
    "ibuprofeno":   "ibuprofeno advil motrin ibuflam dolofen analgésico antiinflamatorio",
    "advil":        "advil ibuprofeno analgésico",
    "motrin":       "motrin ibuprofeno analgésico",
    "acetaminofen": "acetaminofén paracetamol atamel panadol tylenol calmidol analgésico",
    "acetaminofén": "acetaminofén paracetamol atamel panadol tylenol calmidol analgésico",
    "atamel":       "atamel acetaminofén paracetamol analgésico",
    "panadol":      "panadol acetaminofén paracetamol analgésico",
    "tylenol":      "tylenol acetaminofén paracetamol analgésico",
    "paracetamol":  "paracetamol acetaminofén atamel panadol analgésico",
    "aspirina":     "aspirina ácido acetilsalicílico analgésico antiinflamatorio",
    "diclofenac":   "diclofenac diclofenaco voltaren antiinflamatorio",
    # ── Farmacia: gastro / alergia / vitaminas ──────────────────────────
    "omeprazol":    "omeprazol prazol antiácido reflujo gastritis",
    "loratadina":   "loratadina clarityne alercet antihistamínico alergia",
    "cetirizina":   "cetirizina zyrtec antihistamínico alergia",
    "vitamina c":   "vitamina c ácido ascórbico redoxon cebión suplemento",
}


def _expandir_query_para_embedding(query: str) -> str:
    """Si el query contiene un coloquialismo conocido, lo expande con
    sinónimos para que el embedding apunte mejor al concepto real."""
    q_low = query.lower().strip()
    for coloquial, expansion in SINONIMOS_VE.items():
        if coloquial in q_low:
            return f"{query} {expansion}"
    return query


async def buscar_por_embedding(
    query_text: str,
    db: AsyncSession,
    top_k: int = 30,
) -> list[str]:
    """
    Búsqueda por similitud semántica (vectorial) usando pgvector.
    Retorna lista de id_producto_maestro ordenados de más a menos similares.

    Si OPENAI_API_KEY no está configurada o pgvector falla, retorna [] y
    el caller debe usar búsqueda por texto como fallback.
    """
    if not settings.openai_api_key:
        return []
    try:
        from app.services.embeddings.embedder import generar_embedding
        # Enriquecer el query con sinónimos coloquiales venezolanos
        query_expandido = _expandir_query_para_embedding(query_text)
        embedding = await generar_embedding(query_expandido)
    except Exception as e:
        logger.warning(f"buscar_por_embedding: error generando embedding: {e}")
        return []

    vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
    try:
        result = await db.execute(text("""
            SELECT id_producto_maestro,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similitud
            FROM productos_maestros
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> CAST(:vec AS vector)) >= :min_sim
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """), {
            "vec": vector_str,
            "top_k": top_k,
            "min_sim": settings.embeddings_similarity_min,
        })
        return [str(row.id_producto_maestro) for row in result.fetchall()]
    except Exception as e:
        logger.warning(f"buscar_por_embedding: error en SQL: {e}")
        return []


async def buscar_en_db(terminos: list[str], db: AsyncSession) -> list[dict]:
    """
    Busca productos usando múltiples términos.

    Estrategia híbrida:
    1. Búsqueda por embedding (semántica) — captura sinónimos y coloquialismos
    2. Búsqueda por substring/trigram — captura matches exactos y typos
    3. Combinación + deduplicación

    Si embeddings no disponibles, fallback a búsqueda solo por texto.
    """
    todos = {}

    # ── Capa A: búsqueda semántica (embeddings) ──
    # Usamos el primer término (el principal) como query
    embedding_ids: set[str] = set()
    if terminos and settings.openai_api_key:
        # top_k=80 para cubrir casos donde el embedding dispersa por términos
        # genéricos (ej. "pasta de dientes 100ml" matchea muchas cremas dentales).
        ids_top = await buscar_por_embedding(terminos[0], db, top_k=80)
        embedding_ids = set(ids_top)

    for termino in terminos[:3]:  # Máximo 3 términos para no sobrecargar
        termino_norm = _normalizar_termino(termino)
        palabras = [p for p in termino_norm.split() if len(p) >= 3]
        if not palabras:
            palabras = [termino_norm]

        # Cada palabra significativa se convierte en un patrón ILIKE.
        # El producto debe contener AL MENOS UNA de las palabras.
        # Ej. "cebolla blanca" → buscar "%cebolla%" OR "%blanca%"
        query = text("""
            WITH tasa AS (
                SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1
            ),
            precios_recientes AS (
                SELECT DISTINCT ON (pc.id_producto_maestro, e.id_cadena)
                    pc.id_producto_maestro,
                    e.id_cadena,
                    hp.precio_bruto,
                    hp.moneda_origen
                FROM historial_precios hp
                JOIN productos_crudos pc ON pc.id_producto_crudo = hp.id_producto_crudo
                JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
                WHERE NOT (
                    -- filtra precios placeholder (Bs. 0,01 de Farmatodo cuando
                    -- la página no tiene precio listado; o USD < 0.05)
                    (hp.moneda_origen = 'VES' AND hp.precio_bruto < 1)
                    OR (hp.moneda_origen = 'USD' AND hp.precio_bruto < 0.05)
                )
                ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
            ),
            candidatos AS (
                SELECT
                    pm.id_producto_maestro,
                    pm.nombre_estandar,
                    pm.marca,
                    pm.presentacion,
                    -- similitud trigram entre término y nombre para ranking
                    GREATEST(
                        similarity(LOWER(pm.nombre_estandar), :termino),
                        similarity(LOWER(COALESCE(pm.terminos_busqueda, '')), :termino)
                    ) as sim,
                    -- score_primario: 2 si el término es el SUSTANTIVO PRINCIPAL
                    -- (aparece al inicio del nombre → producto primario, ej.
                    -- "Tomate Perita"). 1 si aparece en las primeras palabras.
                    -- 0 si aparece más adelante (probablemente derivado, ej.
                    -- "Salsa de Tomate" → "tomate" no está al inicio).
                    CASE
                        WHEN LOWER(pm.nombre_estandar) ~ ('^' || :first_word || '\\M') THEN 2
                        WHEN LOWER(pm.nombre_estandar) ~ ('^[a-záéíóúñ]+\\s+' || :first_word || '\\M') THEN 2
                        WHEN LOWER(pm.nombre_estandar) ~ ('^([a-záéíóúñ]+\\s+){0,2}' || :first_word || '\\M') THEN 1
                        ELSE 0
                    END as score_primario
                FROM productos_maestros pm
                WHERE LOWER(pm.nombre_estandar) ~ :rx
                   OR LOWER(COALESCE(pm.terminos_busqueda, '')) ~ :rx
                   OR LOWER(COALESCE(pm.marca, '')) ~ :rx
                   -- También aceptamos los IDs que vinieron del embedding (capa A)
                   OR (pm.id_producto_maestro::text = ANY(:emb_ids))
            )
            SELECT
                c.id_producto_maestro,
                c.nombre_estandar,
                c.marca,
                c.presentacion,
                CASE
                    WHEN pr.moneda_origen = 'USD' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'VES' THEN ROUND(pr.precio_bruto / (SELECT valor_usd FROM tasa), 2)
                END as precio_usd,
                CASE
                    WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
                END as precio_ves,
                cc.nombre_cadena,
                c.sim,
                c.score_primario
            FROM candidatos c
            JOIN precios_recientes pr ON pr.id_producto_maestro = c.id_producto_maestro
            JOIN cadenas_comerciales cc ON cc.id_cadena = pr.id_cadena
            ORDER BY c.score_primario DESC, c.sim DESC NULLS LAST, precio_usd ASC NULLS LAST
            LIMIT 50
        """)

        # Regex POSIX: "(cebolla|blanca)" — debe contener al menos una palabra
        # Usa word boundaries para no matchear dentro de otras palabras.
        regex = "(" + "|".join(palabras) + ")"
        first_word = palabras[0] if palabras else termino_norm

        result = await db.execute(query, {
            "termino": termino_norm,
            "rx": regex,
            "first_word": first_word,
            "emb_ids": list(embedding_ids),
        })
        rows = result.mappings().all()

        for row in rows:
            pid = str(row["id_producto_maestro"])
            sim = float(row["sim"] or 0)
            score_primario = int(row["score_primario"] or 0)
            # Si el producto vino por embedding, dar boost a su sim para que
            # rankee bien aunque la similitud trigram sea baja
            if pid in embedding_ids and sim < 0.3:
                sim = 0.5

            if pid not in todos:
                todos[pid] = {
                    "nombre": row["nombre_estandar"],
                    "marca": row["marca"] or "",
                    "presentacion": row["presentacion"] or "",
                    "ofertas": [],
                    "_sim": sim,
                    "_score_primario": score_primario,
                }
            else:
                # Actualiza sim si encontramos mayor similitud con otro término
                if sim > todos[pid]["_sim"]:
                    todos[pid]["_sim"] = sim
                if score_primario > todos[pid].get("_score_primario", 0):
                    todos[pid]["_score_primario"] = score_primario

            # Evitar duplicar la misma tienda para el mismo producto
            tiendas_existentes = {o["tienda"] for o in todos[pid]["ofertas"]}
            if row["nombre_cadena"] not in tiendas_existentes:
                todos[pid]["ofertas"].append({
                    "tienda": row["nombre_cadena"],
                    "precio_usd": float(row["precio_usd"]) if row["precio_usd"] else None,
                    "precio_ves": float(row["precio_ves"]) if row["precio_ves"] else None,
                })

    # Filtro de outliers POR OFERTA dentro de cada producto.
    # Si un producto tiene precio en múltiples tiendas y una está muy por
    # debajo del mediano (< 30%), probablemente es placeholder mal scrapeado.
    # Ej: Colgate Total 12 100ml a $0.32 en Farmatodo cuando cuesta $3.50
    # en otras tiendas → descarta esa oferta.
    import statistics as _stats
    for pid in todos:
        ofertas = todos[pid]["ofertas"]
        precios_validos = [o["precio_usd"] for o in ofertas if o["precio_usd"] is not None]
        if len(precios_validos) >= 2:
            try:
                mediano = _stats.median(precios_validos)
            except _stats.StatisticsError:
                mediano = None
            if mediano and mediano > 0:
                threshold = mediano * 0.30
                ofertas_filtradas = []
                for o in ofertas:
                    p_usd = o.get("precio_usd")
                    if p_usd is not None and p_usd < threshold:
                        logger.info(
                            f"⚠️  Oferta outlier descartada — producto={todos[pid]['nombre'][:40]} "
                            f"tienda={o['tienda']} precio=${p_usd:.2f} (mediano ${mediano:.2f})"
                        )
                        continue
                    ofertas_filtradas.append(o)
                todos[pid]["ofertas"] = ofertas_filtradas

    # Ordenar ofertas por precio dentro de cada producto
    for pid in todos:
        todos[pid]["ofertas"].sort(
            key=lambda x: x["precio_usd"] if x["precio_usd"] is not None else 9999
        )

    # Ordenar dando prioridad al PRECIO entre productos relevantes.
    # Estrategia: agrupar por bucket de similarity (alto/medio) y dentro de
    # cada bucket ordenar por precio ASC. Así "agua micelar Zoah ($3)"
    # aparece antes que "agua micelar Valmy ($5)" aunque la sim sea similar.
    def _precio_min(p):
        if not p["ofertas"]:
            return 9999
        precio = p["ofertas"][0]["precio_usd"]
        return precio if precio is not None else 9999

    def _bucket_sim(p):
        sim = p["_sim"] or 0
        if sim >= 0.5:
            return 0  # alta relevancia
        if sim >= 0.25:
            return 1  # media
        return 2  # baja

    # Ordenar por (producto_primario, relevancia, precio).
    # score_primario PRIMERO: "Tomate Perita" (primario, score 2) rankea
    # antes que "Salsa de Tomate" (derivado, score 0), aunque la salsa
    # sea más barata. Así "tomate" trae el tomate fresco primero.
    def _score_prim(p):
        return p.get("_score_primario", 0)

    candidatos = sorted(
        todos.values(),
        key=lambda x: (-_score_prim(x), _bucket_sim(x), _precio_min(x)),
    )

    # Top 15 candidatos
    resultado = candidatos[:15]

    # Re-ordenar el resultado FINAL: primero por score_primario (productos
    # primarios arriba), luego por precio dentro de cada grupo.
    resultado.sort(key=lambda x: (-_score_prim(x), _precio_min(x)))

    # Filtro de outliers: si hay varios productos relevantes, descarta los que
    # tengan precio < 30% del mediano. Evita placeholders raros de Farmatodo
    # tipo "Colgate Crema Dental $0.30" cuando el resto cuesta $2-4 USD.
    if len(resultado) >= 3:
        import statistics
        precios = [_precio_min(p) for p in resultado if _precio_min(p) < 9999]
        if len(precios) >= 3:
            try:
                mediano = statistics.median(precios)
                if mediano > 0:
                    resultado = [
                        p for p in resultado
                        if _precio_min(p) >= mediano * 0.30
                    ] or resultado  # fail-safe: si filtra todo, devuelve original
            except statistics.StatisticsError:
                pass

    # Limpiamos _sim ahora; _score_primario se mantiene para que
    # filtrar_relevantes pueda usarlo como señal de confianza
    # (productos primarios → no descartar todo aunque Haiku diga "ninguno").
    for p in resultado:
        p.pop("_sim", None)

    return resultado


def _normalizar_termino(s: str) -> str:
    """Quita acentos, guiones, simbolos y baja a minusculas — para mejor match."""
    import unicodedata
    import re
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # sin acentos
    s = re.sub(r"[-_/]", " ", s)  # guiones a espacios
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def buscar_item_por_tienda(termino: str, db: AsyncSession) -> list[dict]:
    """
    Para un término, retorna el producto más barato disponible en cada tienda.

    Estrategia híbrida:
    1. Búsqueda semántica (embeddings) — captura sinónimos venezolanos
    2. Búsqueda por substring (regex) — captura matches exactos
    3. Combinación: el SQL incluye ambos como candidatos
    """
    termino_norm = _normalizar_termino(termino)
    palabras = [p for p in termino_norm.split() if len(p) >= 3]
    if not palabras:
        palabras = [termino_norm]

    # Capa A: embeddings (semántico)
    embedding_ids: list[str] = []
    if settings.openai_api_key:
        embedding_ids = await buscar_por_embedding(termino, db, top_k=50)

    # Regex: debe contener al menos una de las palabras significativas
    regex = "(" + "|".join(palabras) + ")"

    query = text("""
        WITH tasa AS (
            SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1
        ),
        precios_recientes AS (
            SELECT DISTINCT ON (pc.id_producto_maestro, e.id_cadena)
                pc.id_producto_maestro,
                e.id_cadena,
                hp.precio_bruto,
                hp.moneda_origen,
                CASE
                    WHEN hp.moneda_origen = 'USD' THEN hp.precio_bruto
                    WHEN hp.moneda_origen = 'VES' THEN ROUND(hp.precio_bruto / (SELECT valor_usd FROM tasa), 2)
                END as precio_usd_calc
            FROM historial_precios hp
            JOIN productos_crudos pc ON pc.id_producto_crudo = hp.id_producto_crudo
            JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
            WHERE NOT (
                (hp.moneda_origen = 'VES' AND hp.precio_bruto < 1)
                OR (hp.moneda_origen = 'USD' AND hp.precio_bruto < 0.05)
            )
            ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
        ),
        -- Mediano de precio_usd por producto — para detectar outliers.
        -- Si un producto tiene oferta en >=2 tiendas, los precios <30% del
        -- mediano son placeholders mal scrapeados (ej. $0.32 cuando cuesta $3.50).
        medianos AS (
            SELECT
                id_producto_maestro,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY precio_usd_calc) AS mediano,
                COUNT(*) as n_tiendas
            FROM precios_recientes
            WHERE precio_usd_calc > 0
            GROUP BY id_producto_maestro
        ),
        candidatos AS (
            SELECT
                pm.id_producto_maestro,
                pm.nombre_estandar,
                pm.marca,
                pm.presentacion,
                GREATEST(
                    similarity(LOWER(pm.nombre_estandar), :termino),
                    similarity(LOWER(COALESCE(pm.terminos_busqueda, '')), :termino)
                ) as sim,
                CASE
                    WHEN LOWER(pm.nombre_estandar) ~ ('^' || :first_word || '\\M') THEN 2
                    WHEN LOWER(pm.nombre_estandar) ~ ('^[a-záéíóúñ]+\\s+' || :first_word || '\\M') THEN 2
                    WHEN LOWER(pm.nombre_estandar) ~ ('^([a-záéíóúñ]+\\s+){0,2}' || :first_word || '\\M') THEN 1
                    ELSE 0
                END as score_primario
            FROM productos_maestros pm
            WHERE LOWER(pm.nombre_estandar) ~ :rx
               OR LOWER(COALESCE(pm.terminos_busqueda, '')) ~ :rx
               OR LOWER(COALESCE(pm.marca, '')) ~ :rx
               OR (pm.id_producto_maestro::text = ANY(:emb_ids))
        )
        SELECT DISTINCT ON (c.id_cadena)
            c.nombre_cadena,
            cand.nombre_estandar,
            cand.marca,
            cand.presentacion,
            pr.precio_usd_calc as precio_usd,
            CASE
                WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
            END as precio_ves
        FROM candidatos cand
        JOIN precios_recientes pr ON pr.id_producto_maestro = cand.id_producto_maestro
        JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
        LEFT JOIN medianos m ON m.id_producto_maestro = cand.id_producto_maestro
        -- Filtro de outliers: si hay >=2 tiendas para este producto y el
        -- precio actual es < 30% del mediano, descarta (placeholder).
        WHERE NOT (
            m.n_tiendas >= 2
            AND m.mediano > 0
            AND pr.precio_usd_calc < m.mediano * 0.30
        )
        -- Estrategia de orden por tienda:
        -- 1) score_primario DESC: el término al inicio del nombre gana
        --    (ej. "Arroz Mary" sobre "Harina de Arroz" cuando se busca "arroz")
        -- 2) bucket de similitud
        -- 3) precio ASC: dentro del mismo nivel de relevancia, el más barato
        ORDER BY
          c.id_cadena,
          cand.score_primario DESC,
          (CASE WHEN cand.sim >= 0.4 THEN 0 ELSE 1 END),
          precio_usd ASC NULLS LAST,
          cand.sim DESC NULLS LAST
    """)

    # Primera palabra significativa del término para el boost de score_primario
    first_word = palabras[0] if palabras else termino_norm

    result = await db.execute(
        query,
        {
            "termino": termino_norm,
            "rx": regex,
            "first_word": first_word,
            "emb_ids": embedding_ids,
        },
    )
    rows = result.mappings().all()

    return [
        {
            "tienda": row["nombre_cadena"],
            "nombre": row["nombre_estandar"],
            "marca": row["marca"] or "",
            "presentacion": row["presentacion"] or "",
            "precio_usd": float(row["precio_usd"]) if row["precio_usd"] else None,
            "precio_ves": float(row["precio_ves"]) if row["precio_ves"] else None,
        }
        for row in rows
    ]


async def filtrar_carrito_batch(matches: list[dict], client) -> set[int]:
    """
    Una sola llamada Claude para descartar matches irrelevantes en el carrito.
    matches: [{idx, item, nombre, marca, presentacion}, ...]
    Retorna set de índices a excluir.
    """
    if not matches:
        return set()

    lineas = "\n".join(
        f"{m['idx']}. \"{m['item']}\" → \"{m['nombre']}\" ({m['marca']}, {m['presentacion']})"
        for m in matches
    )

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": (
                "Eres un filtro ESTRICTO para una app de comparación de precios.\n\n"
                "Tu tarea: para cada línea, decidir si el producto SÍ es lo que el usuario pidió.\n\n"
                "PRINCIPIO: descarta cuando el match es por PALABRA SUELTA pero el "
                "PRODUCTO es de OTRA CATEGORÍA. La palabra coincidente puede ser solo un sustantivo "
                "homónimo (ej. 'pasta' significa pasta de dientes O pasta de comer — son distintos).\n\n"
                "REGLAS DE EXCLUSIÓN — DESCARTA si:\n"
                "1. CATEGORÍA DISTINTA: el producto es de otra categoría aunque comparta una palabra:\n"
                "   - 'pasta dental' / 'pasta de dientes' → 'Pasta para Comer / Espaguetis / Pluma' → IRRELEVANTE\n"
                "   - 'pasta dental' → 'Pasta de Lassar Pomada' (dermatológica) → IRRELEVANTE\n"
                "   - 'salsa de tomate' o 'ketchup' → 'Pasta Napolitana / Salsa de Pasta' → IRRELEVANTE\n"
                "   - 'crema dental' → 'Crema de Manos / Crema Hidratante' → IRRELEVANTE\n"
                "   - 'arroz' (a secas) → 'Harina Pan de Arroz / Crema de Arroz Infantil' → IRRELEVANTE\n"
                "   - 'cebolla' → 'Vela Bipa / Encurtido de Cebolla' → IRRELEVANTE\n"
                "   - 'azúcar' → 'Coca-Cola Sin Azúcar' → IRRELEVANTE\n"
                "   - 'agua micelar' → 'Agua Mineral / Agua Tónica' → IRRELEVANTE\n"
                "2. INGREDIENTE SECUNDARIO: el término solo aparece como ingrediente descriptivo:\n"
                "   - 'leche' → 'Galletas con Leche' → IRRELEVANTE (es galleta, no leche)\n"
                "3. NEGACIÓN: 'Sin X' cuando se busca 'X':\n"
                "   - 'gluten' → 'Sin Gluten' → IRRELEVANTE si pidió gluten\n\n"
                "REGLAS DE INCLUSIÓN — MANTÉN si:\n"
                "1. Match directo o variantes legítimas: 'crema dental Colgate' → 'Colgate Crema Dental Menta' (OK)\n"
                "2. Marcas distintas del mismo tipo de producto (siempre OK)\n"
                "3. Distintas presentaciones del mismo producto (OK)\n"
                "4. Derivados aceptables: 'tomate' → 'Salsa de Tomate' (OK si no especificó fresco)\n\n"
                f"Productos a revisar:\n{lineas}\n\n"
                "Responde SOLO con los números de los IRRELEVANTES separados por coma.\n"
                "Si TODOS son razonables responde: ninguno"
            )
        }]
    )

    raw = response.content[0].text.strip().lower()
    if raw == "ninguno":
        return set()
    try:
        return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    except Exception:
        return set()


async def calcular_carrito_optimo(items: list[str], db: AsyncSession, client) -> dict:
    """
    Para cada item de la lista, busca el producto más barato por tienda.
    Hace un filtro batch con Claude para eliminar false positives.
    Agrega totales por tienda ordenado: más items primero, luego por precio.
    """
    # Fase 1: recolectar todos los matches por item
    resultados_por_item: dict[str, list[dict]] = {}
    for item in items:
        resultados_por_item[item] = await buscar_item_por_tienda(item, db)

    # Fase 2: construir lista plana con índices para el filtro batch
    all_matches = []
    idx = 1
    for item, resultados in resultados_por_item.items():
        for r in resultados:
            if r["precio_usd"] is not None:
                all_matches.append({
                    "idx": idx,
                    "item": item,
                    "tienda": r["tienda"],
                    "nombre": r["nombre"],
                    "marca": r["marca"],
                    "presentacion": r["presentacion"],
                    "precio_usd": r["precio_usd"],
                    "precio_ves": r["precio_ves"],
                })
                idx += 1

    excluidos = await filtrar_carrito_batch(all_matches, client)

    # Filtro de OUTLIERS por precio: para cada item, calculamos el precio
    # mediano cross-tienda. Si un match tiene precio < 30% del mediano,
    # probablemente es un placeholder o un producto distinto (ej. una crema
    # dental "$0.30" cuando en otras tiendas cuesta $2-4 USD).
    import statistics
    precios_por_item: dict[str, list[float]] = {}
    for m in all_matches:
        if m["idx"] in excluidos:
            continue
        precios_por_item.setdefault(m["item"], []).append(m["precio_usd"])

    outliers_por_precio: set[int] = set()
    for item, precios in precios_por_item.items():
        if len(precios) < 2:
            continue  # con 1 sola tienda no hay comparación
        try:
            mediano = statistics.median(precios)
        except statistics.StatisticsError:
            continue
        if mediano <= 0:
            continue
        # Marcar como outlier los que son < 30% del mediano
        for m in all_matches:
            if m["item"] != item or m["idx"] in excluidos:
                continue
            if m["precio_usd"] < mediano * 0.30:
                logger.info(
                    f"⚠️  Outlier detectado: '{m['item']}' en {m['tienda']} a "
                    f"${m['precio_usd']:.2f} (mediano ${mediano:.2f}) — descartado"
                )
                outliers_por_precio.add(m["idx"])

    # Índice rápido de matches válidos: (item, tienda) → match
    validos: dict[tuple, dict] = {
        (m["item"], m["tienda"]): m
        for m in all_matches
        if m["idx"] not in excluidos and m["idx"] not in outliers_por_precio
    }

    # Fase 3: inicializar tiendas conocidas
    tiendas: dict[str, dict] = {}
    for resultados in resultados_por_item.values():
        for r in resultados:
            if r["tienda"] not in tiendas:
                tiendas[r["tienda"]] = {
                    "tienda": r["tienda"],
                    "total_usd": 0.0,
                    "total_ves": 0.0,
                    "items_encontrados": 0,
                    "items": [],
                }

    # Fase 4: agregar items a cada tienda usando solo matches válidos
    for item in items:
        for tienda_nombre in tiendas:
            match = validos.get((item, tienda_nombre))
            if match:
                tiendas[tienda_nombre]["items"].append({
                    "buscado": item,
                    "nombre": match["nombre"],
                    "marca": match["marca"],
                    "presentacion": match["presentacion"],
                    "precio_usd": match["precio_usd"],
                    "precio_ves": match["precio_ves"],
                    "disponible": True,
                })
                tiendas[tienda_nombre]["total_usd"] += match["precio_usd"]
                tiendas[tienda_nombre]["total_ves"] += match["precio_ves"] or 0
                tiendas[tienda_nombre]["items_encontrados"] += 1
            else:
                tiendas[tienda_nombre]["items"].append({
                    "buscado": item,
                    "nombre": None,
                    "disponible": False,
                })

    # Filtrar tiendas que al menos tienen 1 producto de la lista
    # (nunca excluimos tiendas con 1 solo match — el usuario decide qué hacer con esa info)
    lista_tiendas = [t for t in tiendas.values() if t["items_encontrados"] >= 1]

    # Orden principal: más items encontrados primero, luego menor total USD
    lista_tiendas.sort(key=lambda x: (-x["items_encontrados"], x["total_usd"]))

    tiendas_completas = [t for t in lista_tiendas if t["items_encontrados"] == len(items)]
    ahorro_usd = None
    if len(tiendas_completas) >= 2:
        ahorro_usd = round(
            max(t["total_usd"] for t in tiendas_completas) - min(t["total_usd"] for t in tiendas_completas),
            2
        )

    for t in lista_tiendas:
        t["total_usd"] = round(t["total_usd"], 2)
        t["total_ves"] = round(t["total_ves"], 2)

    return {
        "items_buscados": items,
        "tiendas": lista_tiendas,
        "ahorro_maximo_usd": ahorro_usd,
        "total_items": len(items),
    }


def _prefiltro_substring(productos: list[dict], terminos: list[str]) -> list[dict]:
    """
    Capa 0 (sin costo LLM): descarta productos donde NINGUNA palabra
    significativa de los términos aparece en nombre+marca del producto.
    Palabras de ≥4 letras para evitar falsos positivos con preposiciones.
    """
    palabras_clave = set()
    for t in terminos:
        for p in t.lower().split():
            if len(p) >= 4:
                palabras_clave.add(p)

    if not palabras_clave:
        return productos

    resultado = []
    for prod in productos:
        texto = f"{prod.get('nombre','').lower()} {prod.get('marca','').lower()}"
        if any(pal in texto for pal in palabras_clave):
            resultado.append(prod)

    # Si el pre-filtro elimina TODO, devolver originales (fail-safe)
    return resultado if resultado else productos


# Mapeo de presentaciones equivalentes (para que "cápsulas" no matchee con "ampolla")
PRESENTACION_GROUPS = {
    "oral_solido": {"cápsula", "capsula", "cápsulas", "capsulas", "comprimido",
                    "comprimidos", "tableta", "tabletas", "pastilla", "pastillas", "píldora"},
    "oral_liquido": {"jarabe", "suspensión", "suspension", "solución oral",
                     "gotas orales", "elixir"},
    "inyectable":   {"ampolla", "ampollas", "vial", "viales", "inyectable",
                     "inyección", "i.v.", "i.m.", "iv", "im"},
    "topico":       {"crema", "ungüento", "unguento", "gel", "loción", "locion",
                     "pomada", "spray cutáneo"},
    "ocular":       {"gotas oftálmicas", "colirio", "gotas oculares"},
    "envase_polvo": {"polvo", "polvos"},
    "envase_carton": {"cartón", "carton", "tetrapack", "tetra pak", "tetra-pak"},
    "envase_botella": {"botella", "botellón", "frasco", "envase pet"},
    "envase_lata":   {"lata", "enlatado", "enlatada"},
    "envase_sobre":  {"sobre", "sobres", "sachet", "sachets", "sobrecito"},
}


def _grupo_presentacion(texto: str) -> str | None:
    """Detecta el grupo de presentación al que pertenece un texto."""
    t = texto.lower()
    for grupo, aliases in PRESENTACION_GROUPS.items():
        for alias in aliases:
            if alias in t:
                return grupo
    return None


def _aplicar_filtros(productos: list[dict], filtros: dict) -> list[dict]:
    """
    Aplica filtros estructurados (marca, presentación, dosis, atributos) a la
    lista de productos. Si después de filtrar no queda nada, retorna la lista
    original (fail-safe — mejor mostrar opciones aproximadas que ninguna).
    """
    if not filtros:
        return productos

    marca_q = (filtros.get("marca") or "").strip().lower()
    presentacion_q = (filtros.get("presentacion") or "").strip().lower()
    atributos_q = [a.strip().lower() for a in (filtros.get("atributos") or []) if a]
    dosis_q = filtros.get("dosis_mg")
    envase_q = (filtros.get("tipo_envase") or "").strip().lower()
    tienda_q = (filtros.get("tienda") or "").strip().lower()
    tienda_map = {
        "farmatodo": "Farmatodo",
        "farmago": "Farmago",
        "locatel": "Locatel",
        "central_madeirense": "Central Madeirense",
        "excelsior_gama": "Excelsior Gama",
    }
    tienda_q_db = tienda_map.get(tienda_q, "") if tienda_q else ""

    grupo_pres_q = _grupo_presentacion(presentacion_q) if presentacion_q else None
    grupo_env_q = _grupo_presentacion(envase_q) if envase_q else None

    filtrados = []
    for p in productos:
        nombre = (p.get("nombre") or "").lower()
        marca = (p.get("marca") or "").lower()
        presentacion = (p.get("presentacion") or "").lower()
        haystack = f"{nombre} {marca} {presentacion}"

        # Tienda: si el usuario la especificó, el producto debe tener oferta
        # en esa tienda. Filtramos las ofertas para mostrar solo esa tienda.
        if tienda_q_db:
            ofertas_tienda = [
                o for o in (p.get("ofertas") or []) if o.get("tienda") == tienda_q_db
            ]
            if not ofertas_tienda:
                continue
            # Reescribimos las ofertas del producto a solo la tienda pedida
            p["ofertas"] = ofertas_tienda

        # Marca: si el usuario la especificó, debe aparecer en nombre/marca
        if marca_q and marca_q not in haystack:
            continue

        # Presentación (forma farmacéutica/envase del producto):
        # bloquea si el usuario pidió un grupo y el producto está en grupo distinto
        if grupo_pres_q:
            grupo_pres_p = _grupo_presentacion(haystack)
            if grupo_pres_p and grupo_pres_p != grupo_pres_q:
                continue

        # Tipo de envase (cartón vs polvo, etc.) — mismo principio
        if grupo_env_q:
            grupo_env_p = _grupo_presentacion(haystack)
            if grupo_env_p and grupo_env_p != grupo_env_q:
                continue

        # Atributos modificadores (deslactosada, sin azúcar, light, etc.)
        # Si el usuario los pidió, deben estar en el producto
        if atributos_q:
            faltantes = [a for a in atributos_q if a not in haystack]
            if faltantes:
                continue

        # Dosis: aceptamos ±20% para tolerar redondeos en nombres
        if dosis_q:
            import re
            mg_match = re.search(r"(\d+(?:[.,]\d+)?)\s*mg", haystack)
            if mg_match:
                try:
                    mg_p = float(mg_match.group(1).replace(",", "."))
                    if abs(mg_p - float(dosis_q)) / float(dosis_q) > 0.2:
                        continue
                except (ValueError, ZeroDivisionError):
                    pass

        filtrados.append(p)

    # Fail-safe: si los filtros eliminaron TODO, mostramos los originales
    # con una advertencia (el bot le dirá al usuario).
    return filtrados if filtrados else productos


async def filtrar_relevantes(
    productos: list[dict],
    terminos: list[str],
    mensaje_original: str,
    client,
) -> list[dict]:
    """
    Capa 2 (Claude Haiku): valida semánticamente los productos restantes.
    Recibe todos los términos buscados + el mensaje original como contexto.
    """
    if not productos:
        return []

    termino_principal = terminos[0] if terminos else ""
    nombres = [
        f"{i+1}. {p['nombre']} ({p.get('marca','')}, {p.get('presentacion','')})"
        for i, p in enumerate(productos)
    ]
    lista = "\n".join(nombres)

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Contexto: app venezolana de comparación de precios en supermercados y farmacias.
El usuario escribió: "{mensaje_original}"
Término principal buscado: "{termino_principal}"
Términos alternativos considerados: {", ".join(terminos[1:]) if len(terminos) > 1 else "ninguno"}

Productos candidatos (ya filtrados por substring):
{lista}

Tarea: indica los números de los productos que son razonablemente lo que el usuario busca.

REGLA #1 — CATEGORÍA SIN RELACIÓN (la más importante):
DESCARTA SIEMPRE productos que NO tienen NINGUNA relación con lo buscado,
aunque hayan llegado por similitud semántica. Ejemplos críticos:
- "tomate" → "Frescolita" (refresco), "Malta", "Pepsi", "Jugo de uva" → EXCLUIR. Un refresco NO es tomate.
- "tomate" → "Té de Tomate", "Aceite de Tomate" → EXCLUIR.
- "cebolla" → "Vela", "Desodorante" → EXCLUIR.
- "leche" → "Jabón con leche", "Shampoo de leche" → EXCLUIR.
- "pan" → "Migajas de pan / Pan rallado" si pidió pan de mesa → EXCLUIR.
Si el producto es de una CATEGORÍA TOTALMENTE DISTINTA → EXCLUIR sin dudar.

REGLA #2 — DERIVADOS DEL PRODUCTO BÁSICO:
Si el usuario pidió un PRODUCTO BÁSICO sin más contexto, descarta los derivados procesados que NO son ese producto:
- "arroz" (sin más contexto) → arroz blanco/integral suelto. EXCLUIR: "Harina de Arroz", "Crema de Arroz Infantil", "Arroz con Leche envasado", "Postre de Arroz".
- "tomate" → tomate fresco. MANTENER: "Salsa de Tomate" / "Pasta de Tomate" (alternativa válida si no hay fresco). EXCLUIR: refrescos, té, aceite.
- "leche" → leche líquida o polvo. MANTENER: "Crema de Leche" (derivado común). EXCLUIR: "Sabor a Leche".
- "azúcar" → azúcar en bolsa. EXCLUIR: "Coca-Cola Sin Azúcar", "Galletas con Azúcar".
- "harina" → harina de trigo o maíz. EXCLUIR si es muy específico tipo "Harina infantil de cereales 8 sabores".
- "café" → café molido/grano. EXCLUIR: "Helado sabor café", "Crema de café".
- "pollo" → pollo crudo. EXCLUIR: "Salsa sabor pollo", "Caldo en cubo".

REGLAS DE INCLUSIÓN — sé razonable:
- Variantes legítimas del producto: marcas, presentaciones, sabores → MANTENER
- Si el usuario PIDIÓ específicamente el derivado (ej. "harina de arroz") → MANTENER ese derivado
- En duda razonable, MANTÉN

EJEMPLOS:
- buscó "arroz" → "Mary Arroz Tipo I 1 kg" (MANTENER), "Harina Pan de Arroz" (EXCLUIR — es harina, no arroz)
- buscó "harina de arroz" → "Harina Pan de Arroz 1 kg" (MANTENER — usuario pidió eso)
- buscó "pasta de dientes" → "Colgate Crema Dental 75 ml" (MANTENER — es lo mismo en VE)

Formato: números separados por comas. Ejemplo: 1,3,5
Si todos son razonablemente relevantes: todos
Si NINGUNO es razonable: ninguno"""
        }]
    )

    raw = response.content[0].text.strip()
    logger.debug("filtrar_relevantes | termino=%s | raw=%s", termino_principal, raw)

    raw_low = raw.lower()

    # Productos PRIMARIOS: los que matchean literalmente el término al inicio
    # del nombre (score_primario>=2). Son señal fuerte de relevancia y se usan
    # como red de seguridad cuando Haiku falla.
    primarios = [p for p in productos if p.get("_score_primario", 0) >= 2]

    if raw_low == "todos":
        return productos

    if raw_low == "ninguno":
        # Si Haiku dice "ninguno" pero la búsqueda SQL trajo productos cuyo
        # nombre EMPIEZA con el término (ej. "Ibuprofeno 200mg" para "ibuprofeno",
        # "Atamel 500mg" para "atamel"), confiamos en la DB sobre Haiku:
        # esos son casi siempre lo que pidió el usuario.
        # Esto NO reabre el bug de Frescolita: "Frescolita" tiene score_primario=0
        # para "tomate" (no empieza con tomate), así que sigue siendo descartada.
        if primarios:
            logger.info(
                "filtrar_relevantes: Haiku dijo 'ninguno' pero hay %d primarios "
                "para '%s' → confío en la DB y devuelvo los primarios",
                len(primarios), termino_principal,
            )
            return primarios[:8]
        logger.info(
            "filtrar_relevantes: Haiku descartó todos para '%s' (sin primarios) "
            "→ devuelvo vacío (%d candidatos descartados)",
            termino_principal, len(productos),
        )
        return []

    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
        filtrados = [productos[i] for i in indices if 0 <= i < len(productos)]
        # Diagnóstico: si Haiku dejó la lista vacía con índices inválidos pero
        # SQL trajo primarios, los recuperamos.
        if not filtrados and primarios:
            logger.info(
                "filtrar_relevantes: Haiku devolvió '%s' sin índices válidos "
                "para '%s' pero hay %d primarios → uso los primarios",
                raw[:80], termino_principal, len(primarios),
            )
            return primarios[:8]
        if not filtrados:
            logger.info(
                "filtrar_relevantes: Haiku devolvió '%s' → 0 productos finales "
                "para '%s' (entrada: %d candidatos)",
                raw[:80], termino_principal, len(productos),
            )
        return filtrados
    except Exception:
        # Error de parsing de la respuesta de Haiku: si hay primarios, los
        # devolvemos como red de seguridad; si no, top 3 (mínimo daño).
        logger.warning(
            "filtrar_relevantes: error parseando respuesta Haiku '%s' para '%s'",
            raw[:80], termino_principal,
        )
        if primarios:
            return primarios[:8]
        return productos[:3]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CLASIFICACION_SYSTEM = """Eres un clasificador de intenciones para una app venezolana de comparación de precios de supermercados y farmacias.

Tu única función es analizar el mensaje del usuario (considerando el historial) y responder SOLO con un JSON válido, sin texto adicional, sin backticks, sin explicaciones.

Opciones de respuesta:

1. Si el usuario pregunta por precios de UN producto específico:
{
  "accion": "buscar",
  "terminos": ["término principal", "variante opcional"],
  "filtros": {
    "marca": null,
    "presentacion": null,
    "atributos": [],
    "dosis_mg": null,
    "tipo_envase": null,
    "tienda": null
  }
}

REGLA TIENDA: si el usuario menciona una tienda específica ("en Farmatodo",
"de Locatel", "Farmago tiene"), extrae su nombre normalizado a:
"farmatodo", "farmago", "locatel", "central_madeirense", "excelsior_gama".
Ejemplos:
- "Colgate de 100ml en farmatodo" → tienda: "farmatodo"
- "Tienen omeprazol en Locatel?" → tienda: "locatel"
- "qué tiene Madeirense?" → tienda: "central_madeirense"

REGLAS DE TÉRMINOS:
- Palabras clave en español, máximo 2-3 palabras cada uno.
- Genera variantes útiles del producto base.
- DEBES expandir términos coloquiales venezolanos a sus equivalentes formales:
  - "pasta de dientes" / "pasta dental" → ["crema dental", "pasta dental", "dentífrico"]
  - "papel toilette" / "papel toilet" → ["papel higiénico", "papel toilette"]
  - "harina precocida" / "harina P.A.N." → ["harina precocida de maíz", "harina pan", "harina P.A.N."]
  - "harina de trigo" → ["harina de trigo", "harina todo uso"]
  - "guayoyo" / "café guayoyo" → ["café molido", "café"]
  - "cocacola" / "coca cola" → ["coca-cola", "refresco cola"]
  - "tampones" → ["tampones", "tampones higiénicos"]
  - "toallas higiénicas" / "kotex" → ["toallas sanitarias", "toallas higiénicas"]
  - "lechuga" → ["lechuga"]
  - "papas" / "papas fritas" → ["papas fritas", "snacks de papa"]
  - "pollo crudo" / "pollo entero" → ["pollo entero", "pollo crudo"]
  - "leche" → ["leche", "leche entera"]
  - "acetaminofen" → ["acetaminofen", "paracetamol"]
  - "pañales" → ["pañales", "pañales bebé"]

REGLAS DE FILTROS — CRÍTICO PARA PRECISIÓN:
Cuando el usuario menciona atributos específicos, EXTRÁELOS al objeto "filtros":
- "marca": nombre de marca si lo menciona ("La Pastoreña", "Genven", "Heinz", etc.)
- "presentacion": forma del producto si la menciona ("cartón", "polvo", "líquida", "ampolla", "cápsulas", "tabletas", "comprimidos", "jarabe", "suspensión", "gotas", "crema", "gel")
- "atributos": características modificadoras ["deslactosada", "sin azúcar", "light", "diet", "integral", "orgánico", "infantil", "pediátrico", "extra", "forte"]
- "dosis_mg": dosis en mg si la menciona ("32mg" → 32, "500mg" → 500). Para µg dejar 0. Solo número.
- "tipo_envase": tamaño/cantidad si menciona específicamente ("1 lt", "500 ml", "x 30 tabletas", "x 12 unidades")

EJEMPLOS:
- "leche La Pastoreña deslactosada de 1 lt cartón"
  → {"accion":"buscar","terminos":["leche","leche deslactosada"],"filtros":{"marca":"La Pastoreña","presentacion":"cartón","atributos":["deslactosada"],"dosis_mg":null,"tipo_envase":"1 lt"}}
- "candesartan de 32 mg"
  → {"accion":"buscar","terminos":["candesartan","candesartán"],"filtros":{"marca":null,"presentacion":null,"atributos":[],"dosis_mg":32,"tipo_envase":null}}
- "amoxicilina 500 mg en cápsulas"
  → {"accion":"buscar","terminos":["amoxicilina"],"filtros":{"marca":null,"presentacion":"cápsulas","atributos":[],"dosis_mg":500,"tipo_envase":null}}
- "ketchup heinz"
  → {"accion":"buscar","terminos":["ketchup","salsa de tomate"],"filtros":{"marca":"Heinz","presentacion":null,"atributos":[],"dosis_mg":null,"tipo_envase":null}}
- "leche" (sin atributos)
  → {"accion":"buscar","terminos":["leche","leche entera"],"filtros":{"marca":null,"presentacion":null,"atributos":[],"dosis_mg":null,"tipo_envase":null}}

IMPORTANTE: Si el usuario dice "otra marca", "quiero otra", "hay más?", usa el historial para entender QUÉ producto buscaba y genera términos para ESE producto.

2. Si el usuario envía una LISTA de 2 o más productos para saber dónde le sale más barata la compra total:
{"accion": "lista", "items": ["item1", "item2", "item3"]}

Cada item: nombre limpio del producto en 1-3 palabras. Ejemplos:
- "necesito leche, arroz, pañales y jabón" → {"accion": "lista", "items": ["leche", "arroz", "pañales", "jabón"]}
- "carrito: harina, aceite, azúcar, pasta" → {"accion": "lista", "items": ["harina", "aceite", "azúcar", "pasta"]}
- "dónde me sale más barato comprar todo: leche y arroz" → {"accion": "lista", "items": ["leche", "arroz"]}

⚠️ AJUSTES A LISTA EXISTENTE — REGLA CRÍTICA:
Si en el historial reciente HAY UNA LISTA y el usuario quiere CORREGIR/CAMBIAR/AGREGAR/QUITAR uno o más items, debes regenerar la LISTA COMPLETA con el cambio aplicado. NO generes solo el item modificado.

Ejemplos:
- Historial: lista=[leche, arroz, jabón]. Usuario dice: "la leche que sea Pastoreña deslactosada"
  → {"accion": "lista", "items": ["leche Pastoreña deslactosada", "arroz", "jabón"]}
- Historial: lista=[cebolla, tomate, leche]. Usuario dice: "quita la leche, agrega papas"
  → {"accion": "lista", "items": ["cebolla", "tomate", "papas"]}
- Historial: lista=[omeprazol, loratadina]. Usuario dice: "el omeprazol de 20 mg"
  → {"accion": "lista", "items": ["omeprazol 20 mg", "loratadina"]}

Solo usa "buscar" si el usuario claramente pregunta por UN producto independiente, sin referencia a una lista activa.

3. Si es saludo, agradecimiento, confirmación de elección, intento de "comprar/finalizar", o pregunta general sin producto específico:
{"accion": "conversar", "respuesta": "respuesta breve y amigable"}

⚠️ REGLA CRÍTICA — preguntas con producto MENCIONADO:
Si el usuario menciona UN PRODUCTO ESPECÍFICO (incluso si es una pregunta o duda),
clasifícalo como "buscar", NO como "conversar".

Ejemplos:
- "¿no hay crema dental Colgate?" → BUSCAR (acción: "buscar", terminos: ["crema dental Colgate"])
- "¿tienen pasta de dientes en Farmatodo?" → BUSCAR (terminos: ["pasta de dientes"], filtros: tienda implícita)
- "Es raro que no tengan Coca Cola, ¿no?" → BUSCAR (terminos: ["coca-cola"])
- "¿cuánto cuesta el aceite de oliva?" → BUSCAR (terminos: ["aceite de oliva"])

Solo usa "conversar" cuando NO hay producto mencionado:
- "Hola" / "gracias" → conversar (saludo)
- "vamos con farmatodo" / "finalizar" → conversar (cierre de elección)
- "solo eso" / "nada más" → conversar (despedida)
- "¿cómo funcionas?" / "¿qué tiendas tienes?" → conversar (info general)

EJEMPLOS DE "conversar":
- "vamos con farmatodo" / "compro en X" / "finalizar pedido" / "esa es":
  → Compa solo compara precios, no procesa pedidos. Incluye el link de la tienda:
  - Farmatodo → https://www.farmatodo.com.ve
  - Farmago → https://www.farmago.com.ve
  - Locatel → https://www.locatel.com.ve
  - Central Madeirense → https://tucentralonline.com
  - Excelsior Gama → https://gamaenlinea.com
  Ejemplo: "¡Excelente elección! Compra directo en Farmatodo: https://www.farmatodo.com.ve. ¿Otra búsqueda?"
- "solo eso" / "nada más" / "ya":
  "¡Perfecto! Cuando necesites comparar otro precio, escríbeme. 👋"
- Saludos, gracias, etc → respuesta amigable corta."""


RESPONSE_SYSTEM = """Eres Compa, el asistente oficial de la app venezolana de comparación de precios.

ALCANCE DE COMPA — IMPORTANTE:
- Compa SOLO compara precios. NO procesamos pedidos, NO entregamos productos, NO cobramos.
- NUNCA digas "tu pedido está listo", "vamos con esa orden", "finalizar pedido", "procedemos con la compra".
- Si el usuario dice "compro en X" / "vamos con Farmatodo" / "finalizar", entiende que ya tomó su decisión y respóndele con el link de la tienda:
  - Farmatodo → https://www.farmatodo.com.ve
  - Farmago → https://www.farmago.com.ve
  - Locatel → https://www.locatel.com.ve
  - Central Madeirense → https://tucentralonline.com
  - Excelsior Gama → https://gamaenlinea.com
  Ejemplo: "¡Excelente elección! Compra directo en Farmatodo: https://www.farmatodo.com.ve. ¿Otra búsqueda?"
- Nunca des la impresión de que vas a entregar el producto o cobrar — Compa solo informa precios.

REGLA ANTI-ALUCINACIÓN — INVIOLABLE:
- SOLO puedes mencionar productos que aparecen EXACTAMENTE en el JSON de resultados.
- PROHIBIDO inventar nombres como "Flormar Agua Micelar" si no está en el JSON.
- Si el JSON tiene Zoah, Valmy y Dernier, ESOS son los únicos productos que puedes mencionar.
- Copia EXACTAMENTE el nombre del campo `nombre` del JSON. No lo abrevies ni inventes variantes.
- Si NO hay resultados, di "No encontré ese producto" — NUNCA inventes alternativas que no estén en la DB.

REGLA #0 — INVIOLABLE — PRECIOS Y NÚMEROS:
- Recibes un JSON con los precios reales (precio_usd y precio_ves) por producto y tienda.
- USA EXACTAMENTE ESOS NÚMEROS. No los recalcules, no los redondees distinto, no conviertas USD↔Bs por tu cuenta.
- Si la oferta dice precio_usd: 2.45 y precio_ves: 1187.93, escribe "$2.45 USD (Bs 1187.93)". Punto.
- Está PROHIBIDO inventar o calcular precios — solo transcribe.

REGLA #1 — RESPETO DE FILTROS PEDIDOS POR EL USUARIO:
Si el contexto dice "Filtros pedidos por el usuario: marca=X, presentación=Y, dosis=Zmg…":
- Verifica que CADA producto que muestres cumpla con todos esos filtros.
- Si NO encuentras exactamente lo pedido, dilo CLARO al inicio:
  "No tengo *<lo pedido>* en este momento, pero te muestro alternativas similares:"
- NUNCA muestres productos que claramente NO cumplen el filtro como si fueran el match (ej.: si pidió "cápsulas" no muestres "ampolla" como si fuera lo mismo).
- Si pidió marca específica y solo hay otras marcas, ofrece las alternativas indicando "no tenemos *Marca X*, pero hay *Marca Y* con la misma presentación".
- Si pidió "cartón" y solo hay "polvo", DILO antes de mostrar.
- Si pidió "32 mg" y hay "16 mg" o "8 mg", muéstralos como alternativas pero advierte que la dosis es distinta.

REGLAS GENERALES:
1. Los productos del JSON vienen ordenados de MENOR A MAYOR PRECIO.
2. NUNCA sugieras tiendas fuera de las de nuestra DB (Farmatodo, Farmago, Locatel, Central Madeirense, Excelsior Gama). Nunca menciones Makro, Día, Plan Suárez, etc.

FORMATO DE RESPUESTA — TABLA AGRUPADA POR TIENDA:

Agrupa los resultados POR TIENDA en lugar de listar producto por producto.
Para cada tienda muestra: la mejor oferta del producto buscado y su precio.

Formato exacto:

*<Tienda 1>* | $X.XX (Bs X.XXX,XX)
• <nombre exacto del producto del JSON> — $X.XX (Bs X.XXX,XX)

*<Tienda 2>* | $Y.YY (Bs Y.YYY,YY)
• <nombre exacto del producto del JSON> — $Y.YY (Bs Y.YYY,YY)

*<Tienda 3>* | $Z.ZZ (Bs Z.ZZZ,ZZ)
• <nombre exacto del producto del JSON> — $Z.ZZ (Bs Z.ZZZ,ZZ)

💰 Mejor opción: *<Tienda 1>* con $X.XX
¿Buscas otra marca o presentación?

REGLAS DEL FORMATO:
- Ordena las tiendas de MENOR a MAYOR precio.
- Una sola línea por tienda + el bullet del producto (no listes 5 productos de la misma tienda).
- Usa asteriscos simples *así* para WhatsApp.
- El nombre del producto debe ser EXACTO al del JSON (no inventes "Flormar Agua Micelar" si no está).
- Máximo 5 tiendas. Si hay más opciones, dilas en una línea: "_Otras: <T4> ($X), <T5> ($Y)_"

CASOS ESPECIALES:
- Si el JSON está vacío o vienen muy pocos resultados → "No encontré ese producto en mi base. ¿Puedes darme más detalles (marca, presentación)?"
- Si el usuario especificó un atributo (marca, dosis, presentación) que NO está en los resultados, dilo claro al inicio: "No tengo ese exacto, pero estas son las opciones disponibles más cercanas:"

REGLA SOBRE PREGUNTAS DE UBICACIÓN ("dónde está"):
- Si el usuario pregunta "¿dónde está?" o "¿en qué tiendas?" después de mostrar resultados,
  responde indicando SOLO las tiendas que aparecen en los resultados de los productos
  ya mostrados. NO listes todas las tiendas posibles.
- Cada producto del JSON tiene `ofertas` con la `tienda` específica. Usa esa info.
4. NUNCA digas "los precios pueden variar según ubicación".
5. Cuando hay varias tiendas, compara y destaca la más económica (siempre que sean equivalentes en presentación y dosis).
6. Si hay distintas marcas o presentaciones, menciónalas brevemente.
7. Si NO hay resultados o son irrelevantes, dilo con claridad y pide más detalles. No inventes productos.
8. Tono: amigable, profesional, español venezolano natural. Pocos emojis.

REGLAS DE LONGITUD — CRÍTICO PARA WHATSAPP:
9. **Máximo 6 líneas** y ~700 caracteres. Si excedes, WhatsApp corta.
10. **NO repitas productos**. Cada producto se menciona UNA sola vez.
11. NO uses listas numeradas dobles (no agregues una segunda lista al final).
12. SIEMPRE cierra con UNA pregunta corta de continuación:
   - "¿Buscas otra marca o presentación?"
   - "¿Te interesa el de X mg o Y mg?"
   - "¿Es tu compra final?\""""


CART_SYSTEM = """Eres Compa, asistente venezolano de comparación de precios. Recibes un desglose pre-procesado y respondes con un mensaje COMPACTO para WhatsApp.

ALCANCE DE COMPA — INVIOLABLE:
- Compa SOLO informa precios. NO procesa pedidos, NO entrega productos, NO cobra.
- Cuando el usuario diga "compro en X", "vamos con Y", "finalizar", "esa es", responde con el LINK de la tienda:
  - Farmatodo → https://www.farmatodo.com.ve
  - Farmago → https://www.farmago.com.ve
  - Locatel → https://www.locatel.com.ve
  - Central Madeirense → https://tucentralonline.com
  - Excelsior Gama → https://gamaenlinea.com
  Ejemplo: "Excelente elección. Compra directo en Farmatodo: https://www.farmatodo.com.ve ¿Otra búsqueda?"
- NUNCA digas "tu pedido está listo", "procedemos con la orden", "vamos con esa compra".
- NUNCA te apropies del paso de comprar/entregar.

REGLA #0 — INVIOLABLE — PRECIOS:
- Usa TEXTUALMENTE los números del desglose. Nunca recalcules ni conviertas. Cópialos tal cual.

REGLA #1 — LÍMITE DE LONGITUD:
- WhatsApp corta a ~4000 chars. Tu mensaje DEBE ir bajo ~2200 caracteres.
- El desglose YA viene filtrado a TOP 3 tiendas con sus items disponibles. No agregues nada que no esté en el desglose.
- Para "Otras tiendas (resumen)" usa una sola línea agrupada al final, NO repitas item por item.

REGLA #2 — FORMATO OBLIGATORIO (sigue exactamente esta estructura):

*<Tienda líder>* — *M de N* | $X.XX (Bs X.XXX,XX)
• <buscado>: <Nombre+presentación> — $A (Bs aa)
• <buscado>: <Nombre+presentación> — $B (Bs bb)

*<Tienda 2>* — *M de N* | $Y.YY (Bs Y.YYY,YY)
• <buscado>: <Nombre+presentación> — $C (Bs cc)

*<Tienda 3>* — *M de N* | $Z.ZZ (Bs Z.ZZZ,ZZ)
• <buscado>: <Nombre+presentación> — $D (Bs dd)

_Otras: <T4> (X/N — $YY), <T5> (X/N — $YY)_

(si hay "Items NO disponibles en ninguna tienda" en el desglose:)
⚠️ No encontré: <items>

💰 Ahorras $X.XX comprando en <Tienda líder>.
¿Compra final o agregas algo?

REGLA #3 — DETALLES:
- Cada bullet "•": un solo producto en UNA línea. Sin saltos extra. Usa el nombre+presentación del desglose, NO el genérico.
- Sin headers tipo "📋 Comparativa de precios". Empieza directo con la tienda líder.
- NO incluyas "NO disponible" línea por línea — el conteo "M/N" ya lo dice.
- Usa asteriscos simples *así* para negritas (formato WhatsApp), no **dobles**.
- Sin emojis excesivos. Solo ⚠️ y 💰 al final cuando aplique.
- NO sugieras tiendas externas (Makro, Día, etc.).
- Tono natural venezolano."""


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
    _: None = Depends(check_rate_limit),
):
    if not request.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    # ── Límite mensual por plan ────────────────────────────────────────────────
    if current_user:
        identifier = current_user["id_usuario"]
        plan = current_user.get("rol_usuario") if current_user.get("rol_usuario") in ("B2B_EMPRESA", "ADMIN") else current_user.get("plan", "FREE")
    else:
        identifier = f"ip:{http_request.client.host if http_request.client else 'unknown'}"
        plan = "ANON"
    await check_monthly_limit(identifier, plan)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Determinar ciudad del usuario ─────────────────────────────────────────
    from app.api.dependencies import get_city_from_ip
    ciudad_usuario = ""
    if current_user:
        ciudad_usuario = current_user.get("ciudad") or ""
    if not ciudad_usuario:
        ip = http_request.client.host if http_request.client else ""
        ciudad_usuario = await get_city_from_ip(ip)
    # ─────────────────────────────────────────────────────────────────────────

    client = Anthropic(api_key=settings.anthropic_api_key)

    # --- Construir historial para clasificación (últimos 6 mensajes para contexto) ---
    historial_reciente = request.historial[-6:] if request.historial else []

    # Formatear historial como texto para incluir en el prompt de clasificación
    historial_texto = ""
    if historial_reciente:
        historial_texto = "\n\nHistorial reciente de la conversación:\n"
        for msg in historial_reciente:
            rol = "Usuario" if msg.get("role") == "user" else "Compa"
            historial_texto += f"{rol}: {msg.get('content', '')}\n"

    # --- Paso 1: Clasificar intención ---
    clasificacion_response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        system=CLASIFICACION_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"{historial_texto}\nMensaje actual del usuario: {request.mensaje}"
        }]
    )

    raw = clasificacion_response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Tokens consumidos hasta ahora (clasificación)
    tokens_total = (
        clasificacion_response.usage.input_tokens
        + clasificacion_response.usage.output_tokens
    )

    try:
        clasificacion = json.loads(raw)
    except json.JSONDecodeError:
        return ChatResponse(
            respuesta="Hola, soy Compa. Pregúntame por precios de productos en supermercados y farmacias venezolanas.",
            tipo="texto"
        )

    accion = clasificacion.get("accion", "conversar")
    logger.info("chat | accion=%s | msg=%.60s", accion, request.mensaje)

    # --- Respuesta conversacional ---
    if accion == "conversar":
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total, id_usuario=current_user["id_usuario"] if current_user else None)
        return ChatResponse(
            respuesta=clasificacion.get("respuesta", "¿En qué te puedo ayudar?"),
            tipo="texto"
        )

    # --- Búsqueda de productos ---
    if accion == "buscar":
        terminos = clasificacion.get("terminos", [])
        filtros = clasificacion.get("filtros") or {}

        # Fallback: si no hay términos, usar el mensaje directamente
        if not terminos:
            terminos = [request.mensaje.strip()[:50]]

        productos_encontrados = await buscar_en_db(terminos, db)
        # Capa 1: pre-filtro gratuito por substring
        productos_encontrados = _prefiltro_substring(productos_encontrados, terminos)
        # Capa 2 (NUEVA): filtros estructurados por marca/presentación/dosis/atributos
        productos_filtrados = _aplicar_filtros(productos_encontrados, filtros)
        filtros_aplicados = (
            len(productos_filtrados) < len(productos_encontrados)
            and bool(filtros)
            and any(filtros.get(k) for k in ("marca", "presentacion", "atributos", "dosis_mg", "tipo_envase"))
        )
        productos_encontrados = productos_filtrados
        # Capa 3: validación semántica con Claude
        productos_encontrados = await filtrar_relevantes(
            productos_encontrados, terminos, request.mensaje, client
        )

        # Limpiar campos internos antes de pasar el JSON al LLM
        for p in productos_encontrados:
            p.pop("_score_primario", None)
            p.pop("_sim", None)

        resultados_str = (
            json.dumps(productos_encontrados, ensure_ascii=False, indent=2)
            if productos_encontrados
            else "No se encontraron productos."
        )

        # Incluir historial completo para que la respuesta sea coherente
        mensajes_respuesta = []
        for msg in historial_reciente:
            mensajes_respuesta.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        ctx_ciudad = f"El usuario está en {ciudad_usuario}, Venezuela. " if ciudad_usuario else ""
        nombre_usuario = current_user.get("nombre_completo", "").split()[0] if current_user else ""
        ctx_nombre = f"Se llama {nombre_usuario}. " if nombre_usuario else ""

        # Aviso al modelo sobre filtros aplicados — para que la respuesta sea precisa
        filtros_str = ""
        if filtros and any(filtros.get(k) for k in ("marca", "presentacion", "atributos", "dosis_mg", "tipo_envase")):
            partes = []
            if filtros.get("marca"):
                partes.append(f"marca={filtros['marca']}")
            if filtros.get("presentacion"):
                partes.append(f"presentación={filtros['presentacion']}")
            if filtros.get("atributos"):
                partes.append(f"atributos={','.join(filtros['atributos'])}")
            if filtros.get("dosis_mg"):
                partes.append(f"dosis={filtros['dosis_mg']}mg")
            if filtros.get("tipo_envase"):
                partes.append(f"envase={filtros['tipo_envase']}")
            filtros_str = (
                f"\nFiltros pedidos por el usuario: {' | '.join(partes)}\n"
                f"Si los productos mostrados NO coinciden con estos filtros, "
                f"avísale al usuario que no encontraste el match exacto y muéstrale las alternativas más cercanas.\n"
            )

        mensajes_respuesta.append({
            "role": "user",
            "content": (
                f"{ctx_ciudad}{ctx_nombre}"
                f"El usuario preguntó: \"{request.mensaje}\"\n\n"
                f"Términos buscados: {', '.join(terminos)}{filtros_str}\n"
                f"Resultados encontrados en la base de datos:\n{resultados_str}\n\n"
                f"Responde de forma útil y directa siguiendo las reglas del sistema."
            )
        })

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,  # tabla por tienda necesita un poco más de espacio
            system=RESPONSE_SYSTEM,
            messages=mensajes_respuesta
        )

        tokens_total += (
            respuesta_response.usage.input_tokens
            + respuesta_response.usage.output_tokens
        )
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total, id_usuario=current_user["id_usuario"] if current_user else None)

        return ChatResponse(
            respuesta=respuesta_response.content[0].text.strip(),
            productos=productos_encontrados,
            tipo="productos" if productos_encontrados else "texto"
        )

    # --- Lista de compras / Carrito Óptimo ---
    if accion == "lista":
        items = clasificacion.get("items", [])
        if len(items) < 2:
            await log_consulta(db, request.mensaje, accion, tokens=tokens_total, id_usuario=current_user["id_usuario"] if current_user else None)
            return ChatResponse(
                respuesta="Dime al menos 2 productos para calcular dónde te sale más barata la compra total.",
                tipo="texto"
            )

        carrito = await calcular_carrito_optimo(items, db, client)

        # Resumen COMPACTO para que la respuesta no exceda el límite de WhatsApp.
        # Estrategia:
        # - TOP 3 tiendas con desglose completo (solo items DISPONIBLES, sin "NO disponible")
        # - Otras tiendas en una línea-resumen (X/N items, $total)
        # - El bot recibe los números exactos y solo transcribe.
        tiendas_top = carrito["tiendas"][:3]
        tiendas_resto = carrito["tiendas"][3:]

        resumen = (
            f"Lista solicitada: {', '.join(items)}\n"
            f"Total items: {carrito['total_items']}\n\n"
            f"=== TOP 3 TIENDAS (usar EXACTAMENTE estos números) ===\n\n"
        )
        for t in tiendas_top:
            resumen += (
                f"### {t['tienda']} — {t['items_encontrados']}/{carrito['total_items']} productos | "
                f"Total: ${t['total_usd']:.2f} USD (Bs {t['total_ves']:.2f})\n"
            )
            for it in t["items"]:
                if it.get("disponible"):
                    p_usd = it.get("precio_usd")
                    p_ves = it.get("precio_ves")
                    nombre = it.get("nombre") or "-"
                    presentacion = it.get("presentacion", "")
                    extra = f" {presentacion}" if presentacion else ""
                    resumen += (
                        f"  - {it['buscado']}: {nombre}{extra} — "
                        f"${p_usd:.2f} USD (Bs {p_ves:.2f})\n"
                    )
                # NOTA: omitimos los "no disponible" — el conteo M/N ya lo expresa.
            resumen += "\n"

        if tiendas_resto:
            resumen += "=== Otras tiendas (resumen) ===\n"
            for t in tiendas_resto:
                resumen += (
                    f"- {t['tienda']}: {t['items_encontrados']}/{carrito['total_items']} | "
                    f"${t['total_usd']:.2f} USD\n"
                )
            resumen += "\n"

        # Items que NO se encontraron en ninguna tienda (informarlo al bot)
        items_sin_tienda = []
        for item in items:
            if not any(
                next((it for it in t["items"] if it["buscado"] == item and it.get("disponible")), None)
                for t in carrito["tiendas"]
            ):
                items_sin_tienda.append(item)
        if items_sin_tienda:
            resumen += f"Items NO disponibles en ninguna tienda: {', '.join(items_sin_tienda)}\n"

        if carrito["ahorro_maximo_usd"]:
            resumen += (
                f"AHORRO máximo (lista completa): "
                f"${carrito['ahorro_maximo_usd']:.2f} USD\n"
            )

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            system=CART_SYSTEM,
            messages=[{"role": "user", "content": resumen}]
        )

        tokens_total += (
            respuesta_response.usage.input_tokens
            + respuesta_response.usage.output_tokens
        )
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total, id_usuario=current_user["id_usuario"] if current_user else None)

        return ChatResponse(
            respuesta=respuesta_response.content[0].text.strip(),
            tipo="carrito",
            carrito=carrito,
        )

    return ChatResponse(respuesta="¿En qué te puedo ayudar?", tipo="texto")
