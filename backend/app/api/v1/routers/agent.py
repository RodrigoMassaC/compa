"""
Agente IA de Compa (compatible con anthropic>=0.26)
====================================================
POST /api/v1/agent/chat
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from anthropic import Anthropic
from app.core.database import get_db
from app.core.config import settings
from app.services.event_logger import log_consulta
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
    Usa threshold 0.25 para trigram (más permisivo en español)
    pero filtra por similitud >= 0.1 para evitar basura.
    Retorna hasta 8 productos maestros únicos con todas sus ofertas.
    """
    todos = {}

    for termino in terminos[:3]:  # Máximo 3 términos para no sobrecargar
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
            )
            SELECT
                pm.id_producto_maestro,
                pm.nombre_estandar,
                pm.marca,
                pm.presentacion,
                CASE
                    WHEN pr.moneda_origen = 'USD' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'VES' THEN ROUND(pr.precio_bruto / (SELECT valor_usd FROM tasa), 2)
                END as precio_usd,
                CASE
                    WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
                END as precio_ves,
                c.nombre_cadena,
                GREATEST(
                    similarity(pm.nombre_estandar, :termino),
                    similarity(COALESCE(pm.terminos_busqueda, ''), :termino)
                ) as sim
            FROM productos_maestros pm
            JOIN precios_recientes pr ON pr.id_producto_maestro = pm.id_producto_maestro
            JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
            WHERE (
                similarity(pm.nombre_estandar, :termino) > 0.30
                OR similarity(COALESCE(pm.terminos_busqueda, ''), :termino) > 0.30
            )
            ORDER BY sim DESC, precio_usd ASC NULLS LAST
            LIMIT 20
        """)

        result = await db.execute(query, {
            "termino": termino,
            "search": f"%{termino}%"
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


async def buscar_item_por_tienda(termino: str, db: AsyncSession) -> list[dict]:
    """
    Para un término, retorna el producto más barato disponible en cada tienda.
    Retorna lista de {tienda, nombre, marca, presentacion, precio_usd, precio_ves}.
    """
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
        )
        SELECT DISTINCT ON (c.id_cadena)
            c.nombre_cadena,
            pm.nombre_estandar,
            pm.marca,
            pm.presentacion,
            CASE
                WHEN pr.moneda_origen = 'USD' THEN pr.precio_bruto
                WHEN pr.moneda_origen = 'VES' THEN ROUND(pr.precio_bruto / (SELECT valor_usd FROM tasa), 2)
            END as precio_usd,
            CASE
                WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
            END as precio_ves
        FROM productos_maestros pm
        JOIN precios_recientes pr ON pr.id_producto_maestro = pm.id_producto_maestro
        JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
        WHERE (
            similarity(pm.nombre_estandar, :termino) > 0.30
            OR similarity(COALESCE(pm.terminos_busqueda, ''), :termino) > 0.30
        )
        ORDER BY c.id_cadena, precio_usd ASC NULLS LAST
    """)

    result = await db.execute(query, {"termino": termino})
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
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"Revisa si cada producto es realmente lo que el usuario buscó "
                f"(descarta si el término buscado es solo un ingrediente secundario).\n\n"
                f"{lineas}\n\n"
                f"Responde SOLO con los números de los IRRELEVANTES separados por coma. "
                f"Si todos son relevantes: ninguno"
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

    lista_tiendas = list(tiendas.values())
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


async def filtrar_relevantes(productos: list[dict], termino_busqueda: str, client) -> list[dict]:
    """Usa Claude para filtrar productos realmente relevantes al término buscado."""
    if not productos:
        return []

    nombres = [f"{i+1}. {p['nombre']} ({p.get('marca','')}, {p.get('presentacion','')})" 
               for i, p in enumerate(productos)]
    lista = "\n".join(nombres)

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""El usuario busca: "{termino_busqueda}"

Productos encontrados:
{lista}

Responde SOLO con los números de los productos que son realmente lo que busca el usuario (no productos que solo contienen el ingrediente de forma secundaria).
Formato: solo números separados por comas. Ejemplo: 1,3,5
Si ninguno es relevante responde: ninguno"""
        }]
    )

    raw = response.content[0].text.strip()
    if raw == "ninguno":
        return []

    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
        return [productos[i] for i in indices if 0 <= i < len(productos)]
    except:
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

REGLAS ESTRICTAS:
1. NUNCA sugieras "revisar en otros supermercados" — eso es exactamente lo que la app hace por el usuario
2. NUNCA digas "los precios pueden variar según ubicación" como consejo genérico
3. SIEMPRE muestra comparación entre tiendas cuando hay más de una opción
4. Destaca cuál tienda tiene el precio más bajo
5. Muestra precios en USD y Bs (bolívares)
6. Sé directo y útil — máximo 3-4 líneas de texto
7. Si hay múltiples marcas o presentaciones, menciónalas brevemente
8. Si NO hay resultados relevantes, di claramente qué buscaste y pide más detalles del producto
9. Tono: amigable pero profesional, en español venezolano natural (sin "hermano", sin emojis excesivos)"""


CART_SYSTEM = """Eres Compa, asistente venezolano de comparación de precios. El usuario quiere saber dónde comprar su lista completa al menor costo.

REGLAS:
1. Indica directamente cuál tienda tiene el total más bajo para la lista completa
2. Menciona el ahorro si hay diferencia significativa entre tiendas con lista completa
3. Si alguna tienda no tiene todos los productos, menciónalo en una línea
4. Muestra el total en USD y Bs de la mejor opción
5. Máximo 3-4 líneas — el frontend muestra el desglose detallado por tienda
6. Tono directo, español venezolano natural"""


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not request.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

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
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total)
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
        productos_encontrados = await filtrar_relevantes(
            productos_encontrados, terminos[0] if terminos else "", client
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
        mensajes_respuesta.append({
            "role": "user",
            "content": (
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
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total)

        return ChatResponse(
            respuesta=respuesta_response.content[0].text.strip(),
            productos=productos_encontrados,
            tipo="productos" if productos_encontrados else "texto"
        )

    # --- Lista de compras / Carrito Óptimo ---
    if accion == "lista":
        items = clasificacion.get("items", [])
        if len(items) < 2:
            await log_consulta(db, request.mensaje, accion, tokens=tokens_total)
            return ChatResponse(
                respuesta="Dime al menos 2 productos para calcular dónde te sale más barata la compra total.",
                tipo="texto"
            )

        carrito = await calcular_carrito_optimo(items, db, client)

        resumen = f"Lista del usuario: {', '.join(items)}\n\n"
        for t in carrito["tiendas"]:
            resumen += f"- {t['tienda']}: ${t['total_usd']:.2f} ({t['items_encontrados']}/{carrito['total_items']} productos)\n"
        if carrito["ahorro_maximo_usd"]:
            resumen += f"\nAhorro máximo entre tiendas con lista completa: ${carrito['ahorro_maximo_usd']:.2f}"

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
        await log_consulta(db, request.mensaje, accion, tokens=tokens_total)

        return ChatResponse(
            respuesta=respuesta_response.content[0].text.strip(),
            tipo="carrito",
            carrito=carrito,
        )

    return ChatResponse(respuesta="¿En qué te puedo ayudar?", tipo="texto")
