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
    historial: list[dict] = []

class ChatResponse(BaseModel):
    respuesta: str
    productos: list[dict] = []
    tipo: str = "texto"


async def buscar_en_db(termino: str, db: AsyncSession) -> list[dict]:
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
            similarity(pm.nombre_estandar, :termino) as sim
        FROM productos_maestros pm
        JOIN precios_recientes pr ON pr.id_producto_maestro = pm.id_producto_maestro
        JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
        WHERE (
            pm.nombre_estandar % :termino
            OR pm.terminos_busqueda % :termino
            OR pm.nombre_estandar ILIKE :search
        )
        ORDER BY similarity(pm.nombre_estandar, :termino) DESC, precio_usd ASC NULLS LAST
        LIMIT 12
    """)
    result = await db.execute(query, {"termino": termino, "search": f"%{termino}%"})
    rows = result.mappings().all()

    productos = {}
    for row in rows:
        nombre = row["nombre_estandar"]
        if nombre not in productos:
            productos[nombre] = {
                "nombre": nombre,
                "marca": row["marca"],
                "presentacion": row["presentacion"],
                "ofertas": [],
                "_sim": float(row["sim"] or 0)
            }
        productos[nombre]["ofertas"].append({
            "tienda": row["nombre_cadena"],
            "precio_usd": float(row["precio_usd"]) if row["precio_usd"] else None,
            "precio_ves": float(row["precio_ves"]) if row["precio_ves"] else None,
        })

    resultado = sorted(productos.values(), key=lambda x: x["_sim"], reverse=True)
    for p in resultado:
        del p["_sim"]
    return resultado[:8]


CLASIFICACION_PROMPT = """Analiza este mensaje de usuario y responde SOLO con un JSON válido, sin texto adicional.

Mensaje: "{mensaje}"

Si el usuario pregunta por precios o productos, responde:
{{"accion": "buscar", "termino": "<término específico de búsqueda en español, máximo 3 palabras>"}}

Si es un saludo o pregunta general, responde:
{{"accion": "conversar", "respuesta": "<respuesta amigable y breve en español venezolano>"}}

Ejemplos:
- "hola" → {{"accion": "conversar", "respuesta": "¡Hola! ¿Qué vas a comprar hoy?"}}
- "¿cuánto cuesta la leche?" → {{"accion": "buscar", "termino": "leche entera"}}
- "busca acetaminofen" → {{"accion": "buscar", "termino": "acetaminofen"}}
- "¿qué tiendas tienen?" → {{"accion": "conversar", "respuesta": "Tenemos precios de Farmago, Central Madeirense, Locatel, Excelsior Gama y Farmatodo."}}"""

RESPONSE_PROMPT = """Eres Compa, asistente de compras venezolano. El usuario preguntó: "{pregunta}"

Encontraste estos productos en la base de datos (ordenados por relevancia):
{resultados}

Instrucciones:
1. Muestra SOLO los productos que realmente correspondan a lo buscado, ignora los que tengan la palabra como ingrediente secundario
2. Destaca el precio más bajo y en qué tienda está
3. Menciona precios en USD y Bs
4. Sé conciso y amigable en español venezolano
5. Si hay el mismo producto en varias tiendas, compara los precios
6. Si no hay productos relevantes, díselo honestamente"""


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not request.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    client = Anthropic(api_key=settings.anthropic_api_key)

    # Paso 1: Clasificar intención con JSON estructurado
    clasificacion_response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        messages=[{"role": "user", "content": CLASIFICACION_PROMPT.format(mensaje=request.mensaje)}]
    )

    raw = clasificacion_response.content[0].text.strip()
    # Limpiar backticks si los hay
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        clasificacion = json.loads(raw)
    except json.JSONDecodeError:
        # Si falla el JSON, respuesta de fallback
        return ChatResponse(respuesta="¡Hola! Soy Compa, tu asistente de compras. Pregúntame por precios de productos en Venezuela.", tipo="texto")

    if clasificacion.get("accion") == "conversar":
        return ChatResponse(respuesta=clasificacion.get("respuesta", "¿En qué te puedo ayudar?"), tipo="texto")

    if clasificacion.get("accion") == "buscar":
        termino = clasificacion.get("termino", "")
        productos_encontrados = await buscar_en_db(termino, db)

        resultados_str = json.dumps(productos_encontrados, ensure_ascii=False, indent=2) if productos_encontrados else "No se encontraron productos."

        respuesta_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": RESPONSE_PROMPT.format(
                pregunta=request.mensaje,
                resultados=resultados_str
            )}]
        )
        respuesta = respuesta_response.content[0].text.strip()

        return ChatResponse(
            respuesta=respuesta,
            productos=productos_encontrados,
            tipo="productos" if productos_encontrados else "texto"
        )

    return ChatResponse(respuesta="¿En qué te puedo ayudar?", tipo="texto")
