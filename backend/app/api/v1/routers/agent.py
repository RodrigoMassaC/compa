"""
Agente IA de Compa (compatible con anthropic>=0.26)
====================================================
POST /api/v1/agent/chat
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from anthropic import Anthropic
from app.core.database import get_db
from app.core.config import settings
import json

router = APIRouter()


class ChatRequest(BaseModel):
    mensaje: str
    historial: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]


class ChatResponse(BaseModel):
    respuesta: str
    productos: list[dict] = []
    tipo: str = "texto"


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

1. Si el usuario pregunta por precios, productos, marcas, o dónde comprar algo:
{"accion": "buscar", "terminos": ["término principal", "variante opcional"]}

Los términos deben ser palabras clave en español, máximo 2-3 palabras cada uno.
Genera variantes útiles. Ejemplos:
- "leche" → ["leche", "leche entera", "leche en polvo"]
- "acetaminofen" → ["acetaminofen", "paracetamol", "acetaminofén"]
- "pañales" → ["pañales", "pañales bebe"]
- "arroz" → ["arroz", "arroz blanco"]

IMPORTANTE: Si el usuario dice "otra marca", "quiero otra", "hay más?", "muéstrame más" u otras variantes, 
usa el historial para entender QUÉ producto estaba buscando y genera términos para ESE producto.

2. Si es saludo, agradecimiento o pregunta general sin producto específico:
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

    try:
        clasificacion = json.loads(raw)
    except json.JSONDecodeError:
        return ChatResponse(
            respuesta="Hola, soy Compa. Pregúntame por precios de productos en supermercados y farmacias venezolanas.",
            tipo="texto"
        )

    # --- Respuesta conversacional ---
    if clasificacion.get("accion") == "conversar":
        return ChatResponse(
            respuesta=clasificacion.get("respuesta", "¿En qué te puedo ayudar?"),
            tipo="texto"
        )

    # --- Búsqueda de productos ---
    if clasificacion.get("accion") == "buscar":
        terminos = clasificacion.get("terminos", [])

        # Fallback: si no hay términos, usar el mensaje directamente
        if not terminos:
            terminos = [request.mensaje.strip()[:50]]

        productos_encontrados = await buscar_en_db(terminos, db)
        productos_encontrados = await filtrar_relevantes(productos_encontrados, terminos[0] if terminos else "", client)

        resultados_str = (
            json.dumps(productos_encontrados, ensure_ascii=False, indent=2)
            if productos_encontrados
            else "No se encontraron productos."
        )

        # --- Paso 2: Generar respuesta con contexto completo ---
        # Incluir historial completo para que la respuesta sea coherente
        mensajes_respuesta = []

        # Agregar historial previo
        for msg in historial_reciente:
            mensajes_respuesta.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Agregar la pregunta actual con los resultados
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

        respuesta = respuesta_response.content[0].text.strip()

        return ChatResponse(
            respuesta=respuesta,
            productos=productos_encontrados,
            tipo="productos" if productos_encontrados else "texto"
        )

    return ChatResponse(respuesta="¿En qué te puedo ayudar?", tipo="texto")
