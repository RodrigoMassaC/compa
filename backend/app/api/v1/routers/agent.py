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

async def buscar_en_db(terminos: list[str], db: AsyncSession) -> list[dict]:
    """
    Busca productos usando múltiples términos.

    Estrategia: requiere SUBSTRING match de al menos una palabra significativa
    del término en el nombre, terminos_busqueda o marca. Esto evita falsos
    positivos del trigram como "cebolla" → "Vela Bipa Blancas".

    Retorna hasta 8 productos maestros únicos con todas sus ofertas.
    """
    todos = {}

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
                    ) as sim
                FROM productos_maestros pm
                WHERE LOWER(pm.nombre_estandar) ~ :rx
                   OR LOWER(COALESCE(pm.terminos_busqueda, '')) ~ :rx
                   OR LOWER(COALESCE(pm.marca, '')) ~ :rx
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
                c.sim
            FROM candidatos c
            JOIN precios_recientes pr ON pr.id_producto_maestro = c.id_producto_maestro
            JOIN cadenas_comerciales cc ON cc.id_cadena = pr.id_cadena
            ORDER BY c.sim DESC NULLS LAST, precio_usd ASC NULLS LAST
            LIMIT 20
        """)

        # Regex POSIX: "(cebolla|blanca)" — debe contener al menos una palabra
        # Usa word boundaries para no matchear dentro de otras palabras.
        regex = "(" + "|".join(palabras) + ")"

        result = await db.execute(query, {
            "termino": termino_norm,
            "rx": regex,
        })
        rows = result.mappings().all()

        for row in rows:
            pid = str(row["id_producto_maestro"])
            sim = float(row["sim"] or 0)

            if pid not in todos:
                todos[pid] = {
                    "nombre": row["nombre_estandar"],
                    "marca": row["marca"] or "",
                    "presentacion": row["presentacion"] or "",
                    "ofertas": [],
                    "_sim": sim
                }
            else:
                # Actualiza sim si encontramos mayor similitud con otro término
                if sim > todos[pid]["_sim"]:
                    todos[pid]["_sim"] = sim

            # Evitar duplicar la misma tienda para el mismo producto
            tiendas_existentes = {o["tienda"] for o in todos[pid]["ofertas"]}
            if row["nombre_cadena"] not in tiendas_existentes:
                todos[pid]["ofertas"].append({
                    "tienda": row["nombre_cadena"],
                    "precio_usd": float(row["precio_usd"]) if row["precio_usd"] else None,
                    "precio_ves": float(row["precio_ves"]) if row["precio_ves"] else None,
                })

    # Ordenar ofertas por precio dentro de cada producto
    for pid in todos:
        todos[pid]["ofertas"].sort(
            key=lambda x: x["precio_usd"] if x["precio_usd"] is not None else 9999
        )

    # Ordenar productos por similitud y tomar los 8 más relevantes
    resultado = sorted(todos.values(), key=lambda x: (x["ofertas"][0]["precio_usd"] if x["ofertas"] and x["ofertas"][0]["precio_usd"] else 9999))
    for p in resultado:
        del p["_sim"]

    return resultado[:5]


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

    Estrategia: exige que alguna palabra significativa del término aparezca
    en nombre_estandar, terminos_busqueda o marca (substring match). Esto
    evita ruido del trigram (ej. "cebolla" → "Vela Bipa Blancas").

    El producto cuyo nombre contiene MÁS palabras del término se prefiere
    (relevancia), y en caso de empate se toma el más barato por tienda.
    """
    termino_norm = _normalizar_termino(termino)
    palabras = [p for p in termino_norm.split() if len(p) >= 3]
    if not palabras:
        palabras = [termino_norm]

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
                hp.moneda_origen
            FROM historial_precios hp
            JOIN productos_crudos pc ON pc.id_producto_crudo = hp.id_producto_crudo
            JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
            ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
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
                ) as sim
            FROM productos_maestros pm
            WHERE LOWER(pm.nombre_estandar) ~ :rx
               OR LOWER(COALESCE(pm.terminos_busqueda, '')) ~ :rx
               OR LOWER(COALESCE(pm.marca, '')) ~ :rx
        )
        SELECT DISTINCT ON (c.id_cadena)
            c.nombre_cadena,
            cand.nombre_estandar,
            cand.marca,
            cand.presentacion,
            CASE
                WHEN pr.moneda_origen = 'USD' THEN pr.precio_bruto
                WHEN pr.moneda_origen = 'VES' THEN ROUND(pr.precio_bruto / (SELECT valor_usd FROM tasa), 2)
            END as precio_usd,
            CASE
                WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
            END as precio_ves
        FROM candidatos cand
        JOIN precios_recientes pr ON pr.id_producto_maestro = cand.id_producto_maestro
        JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
        -- DISTINCT ON por tienda toma el primero → ordenamos por sim DESC
        -- y luego precio ASC, así cada tienda trae el match MÁS RELEVANTE
        -- (no el más barato ignorando relevancia).
        ORDER BY c.id_cadena, cand.sim DESC NULLS LAST, precio_usd ASC NULLS LAST
    """)

    result = await db.execute(query, {"termino": termino_norm, "rx": regex})
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
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                "Eres un filtro estricto para una app de comparación de precios. "
                "Para cada línea, decide si el producto SÍ es lo que el usuario quería.\n\n"
                "REGLAS DE EXCLUSIÓN (marcar como IRRELEVANTE):\n"
                "- El término buscado aparece como ingrediente secundario o descripción "
                "(ej. buscó 'azúcar' → producto es 'Coca-Cola Sin Azúcar' → IRRELEVANTE)\n"
                "- El producto es una categoría totalmente distinta "
                "(ej. buscó 'cebolla' → producto es 'Vela Bipa Blancas' → IRRELEVANTE)\n"
                "- El producto es un derivado/procesado cuando pidieron el básico "
                "(ej. buscó 'tomate' → producto es 'Salsa de Tomate' → IRRELEVANTE si pidió 'tomate' a secas)\n"
                "- El producto requiere preparación muy distinta "
                "(ej. buscó 'arroz' → producto es 'Crema de Arroz Infantil' → IRRELEVANTE salvo que pida infantil)\n\n"
                "REGLAS PARA MANTENER (relevante):\n"
                "- Match exacto de producto + marca + presentación\n"
                "- Variantes razonables del producto (ej. 'leche' → 'Leche Entera Parmalat' OK)\n\n"
                f"Productos a revisar:\n{lineas}\n\n"
                "Responde SOLO con los números de los IRRELEVANTES separados por coma. "
                "Si todos son relevantes responde: ninguno"
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

    # Índice rápido de matches válidos: (item, tienda) → match
    validos: dict[tuple, dict] = {
        (m["item"], m["tienda"]): m
        for m in all_matches
        if m["idx"] not in excluidos
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
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Contexto: app venezolana de comparación de precios en supermercados.
El usuario escribió: "{mensaje_original}"
Término principal buscado: "{termino_principal}"
Términos alternativos considerados: {", ".join(terminos[1:]) if len(terminos) > 1 else "ninguno"}

Productos encontrados en la base de datos:
{lista}

Tarea: indica los números de los productos que SÍ son lo que el usuario busca.
Regla clave: excluye productos donde el término buscado es solo un ingrediente secundario o parte del nombre de algo completamente distinto.
Formato: números separados por comas. Ejemplo: 1,3
Si ninguno es relevante: ninguno"""
        }]
    )

    raw = response.content[0].text.strip()
    logger.debug("filtrar_relevantes | termino=%s | raw=%s", termino_principal, raw)

    if raw.lower() == "ninguno":
        return []

    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
        filtrados = [productos[i] for i in indices if 0 <= i < len(productos)]
        return filtrados if filtrados else productos  # fail-safe
    except Exception:
        return productos


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CLASIFICACION_SYSTEM = """Eres un clasificador de intenciones para una app venezolana de comparación de precios de supermercados y farmacias.

Tu única función es analizar el mensaje del usuario (considerando el historial) y responder SOLO con un JSON válido, sin texto adicional, sin backticks, sin explicaciones.

Opciones de respuesta:

1. Si el usuario pregunta por precios de UN producto específico:
{"accion": "buscar", "terminos": ["término principal", "variante opcional"]}

Los términos deben ser palabras clave en español, máximo 2-3 palabras cada uno.
Genera variantes útiles. Ejemplos:
- "leche" → ["leche", "leche entera", "leche en polvo"]
- "acetaminofen" → ["acetaminofen", "paracetamol", "acetaminofén"]

IMPORTANTE: Si el usuario dice "otra marca", "quiero otra", "hay más?", usa el historial para entender QUÉ producto buscaba y genera términos para ESE producto.

2. Si el usuario envía una LISTA de 2 o más productos para saber dónde le sale más barata la compra total:
{"accion": "lista", "items": ["item1", "item2", "item3"]}

Cada item: nombre limpio del producto en 1-3 palabras. Ejemplos:
- "necesito leche, arroz, pañales y jabón" → {"accion": "lista", "items": ["leche", "arroz", "pañales", "jabón"]}
- "carrito: harina, aceite, azúcar, pasta" → {"accion": "lista", "items": ["harina", "aceite", "azúcar", "pasta"]}
- "dónde me sale más barato comprar todo: leche y arroz" → {"accion": "lista", "items": ["leche", "arroz"]}

3. Si es saludo, agradecimiento o pregunta general sin producto específico:
{"accion": "conversar", "respuesta": "respuesta breve y amigable"}"""


RESPONSE_SYSTEM = """Eres Compa, el asistente oficial de la app venezolana de comparación de precios.

REGLA #0 — INVIOLABLE — PRECIOS Y NÚMEROS:
- Recibes un JSON con los precios reales (precio_usd y precio_ves) por producto y tienda.
- USA EXACTAMENTE ESOS NÚMEROS. No los recalcules, no los redondees distinto, no conviertas USD↔Bs por tu cuenta.
- Si la oferta dice precio_usd: 2.45 y precio_ves: 1187.93, escribe "$2.45 USD (Bs 1187.93)". Punto.
- Está PROHIBIDO inventar o calcular precios — solo transcribe.

REGLAS DE PRESENTACIÓN:
1. NUNCA sugieras tiendas fuera de las de nuestra DB (Farmatodo, Farmago, Locatel, Central Madeirense, Excelsior Gama). Nunca menciones Makro, Día, Plan Suárez, etc.
2. NUNCA digas "los precios pueden variar según ubicación".
3. Cuando hay varias tiendas, compara y destaca la más económica.
4. Si hay distintas marcas o presentaciones, menciónalas brevemente.
5. Si NO hay resultados o son irrelevantes, dilo con claridad y pide más detalles. No inventes productos.
6. Tono: amigable, profesional, español venezolano natural. Pocos emojis.
7. Máximo 3–5 líneas.
8. SIEMPRE cierra con una pregunta de continuación, ejemplos:
   - "¿Buscas otra marca o presentación?"
   - "¿Quieres añadir algo más a tu lista?"
   - "¿Es tu compra final o seguimos comparando?\""""


CART_SYSTEM = """Eres Compa, asistente venezolano de comparación de precios. El usuario mandó una lista y quiere saber dónde le sale más barata.

REGLA #0 — INVIOLABLE — PRECIOS Y NÚMEROS:
- Vas a recibir un DESGLOSE con los precios reales en USD y Bs por cada producto y por cada tienda.
- USA TEXTUALMENTE ESOS NÚMEROS. No los redondees diferente, no calcules nada por tu cuenta, no conviertas USD↔Bs por tu cuenta.
- Si un producto dice "$2.45 USD (Bs 1187.93)" → cópialo así, no lo cambies a "Bs 8.17".
- Está ESTRICTAMENTE PROHIBIDO inventar o calcular precios. Solo transcribe lo que recibiste.

REGLAS DE FORMATO:

1. Agrupa por tienda (NO por producto). Plantilla:

   **<Tienda líder>** es tu mejor opción para *N de N productos*: $X.XX USD (Bs XX.XX)
   - <Producto 1>: $A USD (Bs aa)
   - <Producto 2>: $B USD (Bs bb)

   Si otras tiendas tienen parte de la lista (siempre que tengan ≥1 producto), lístalas debajo:

   **<Otra tienda>** *(M de N productos)* — $Y.YY USD (Bs YY)
   - <Producto>: $C USD (Bs cc)

2. Nunca digas que una tienda "no te sirve" por tener 1 solo producto.
3. Destaca el AHORRO en USD vs la tienda más cara (si aplica), copiando el dato del input.
4. NO sugieras tiendas externas (ni Makro, Día, etc.).
5. Cierre obligatorio con un CTA como:
   - "¿Te confirmamos si hay otra opción más económica?"
   - "¿Quieres que agregue algún producto más a la lista?"
   - "¿Esa es tu compra final?"
6. Tono: amable, profesional, español venezolano. Sin emojis excesivos.
7. Máximo ~12 líneas en total."""


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

        # Fallback: si no hay términos, usar el mensaje directamente
        if not terminos:
            terminos = [request.mensaje.strip()[:50]]

        productos_encontrados = await buscar_en_db(terminos, db)
        # Capa 1: pre-filtro gratuito por substring
        productos_encontrados = _prefiltro_substring(productos_encontrados, terminos)
        # Capa 2: validación semántica con Claude
        productos_encontrados = await filtrar_relevantes(
            productos_encontrados, terminos, request.mensaje, client
        )

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
        mensajes_respuesta.append({
            "role": "user",
            "content": (
                f"{ctx_ciudad}{ctx_nombre}"
                f"El usuario preguntó: \"{request.mensaje}\"\n\n"
                f"Términos buscados: {', '.join(terminos)}\n\n"
                f"Resultados encontrados en la base de datos:\n{resultados_str}\n\n"
                f"Responde de forma útil y directa siguiendo las reglas del sistema."
            )
        })

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
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

        # Construir el resumen DETALLADO con TODOS los precios reales por producto.
        # CRÍTICO: el bot debe usar exactamente estos números, NO inventarlos.
        # Si solo le pasamos totales, alucina los precios por producto.
        resumen = (
            f"Lista solicitada por el usuario: {', '.join(items)}\n"
            f"Total de items pedidos: {carrito['total_items']}\n\n"
            f"=== DESGLOSE DE PRECIOS REALES POR TIENDA ===\n"
            f"(USA EXACTAMENTE ESTOS NÚMEROS, NO LOS INVENTES NI REDONDEES MÁS)\n\n"
        )
        for t in carrito["tiendas"]:
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
                        f"  - {it['buscado']} → {nombre}{extra}: "
                        f"${p_usd:.2f} USD (Bs {p_ves:.2f})\n"
                    )
                else:
                    resumen += f"  - {it['buscado']} → NO DISPONIBLE en esta tienda\n"
            resumen += "\n"

        if carrito["ahorro_maximo_usd"]:
            resumen += (
                f"AHORRO entre tiendas con lista completa: "
                f"${carrito['ahorro_maximo_usd']:.2f} USD\n"
            )

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
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
