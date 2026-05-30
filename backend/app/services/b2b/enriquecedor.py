"""
Enriquecedor de consultas para Compi BI.

Cada query del usuario (ej. "precio del aceite en Farmatodo") se enriquece con:
  - rubro_detectado  → categoría normalizada del producto (ej. 'aceites_vinagres')
  - cadena_mencionada → cadena explícitamente nombrada por el usuario (ej. 'Farmatodo')

Es regex puro: rápido (<1ms) y gratis. Se llama al loguear cada consulta y/o
en batch para enriquecer históricas (`enriquecer_pendientes`).
"""
import logging
import re
import unicodedata
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Cadenas conocidas ────────────────────────────────────────────────────────
# Patterns regex case-insensitive contra el texto crudo (sin acentos).
# La clave es el `nombre_cadena` canónico en la DB.
CADENAS_PATTERNS: dict[str, list[str]] = {
    "Farmatodo":         [r"\bfarmatodo\b"],
    "Farmago":           [r"\bfarmago\b"],
    "Locatel":           [r"\blocatel\b"],
    "Central Madeirense": [r"\bcentral\s*madeirense\b", r"\bmadeirense\b", r"\bcentral\b(?=.*compra)"],
    "Excelsior Gama":    [r"\bexcelsior\s*gama\b", r"\bgama\b"],
}


# ── Rubros ──────────────────────────────────────────────────────────────────
# Mapeo manual de keywords → rubro normalizado. Cubre los más comunes en VE.
# Cuando el texto matchea varias categorías, gana la más específica (orden).
RUBROS_PATTERNS: list[tuple[str, list[str]]] = [
    ("farmacia_analgesicos", [r"\b(ibuprofeno|advil|motrin|acetaminofen|atamel|panadol|tylenol|paracetamol|aspirina|diclofenac)\b"]),
    ("farmacia_gastro",      [r"\b(omeprazol|prazol|antiacido|gastritis|reflujo)\b"]),
    ("farmacia_alergia",     [r"\b(loratadina|clarityne|alercet|cetirizina|zyrtec|antihistaminico|alergia)\b"]),
    ("farmacia_vitaminas",   [r"\b(vitamina|vitaminas|redoxon|cebion|suplemento|multivitaminico)\b"]),
    ("farmacia_otros",       [r"\b(medic|medicina|pastilla|tableta|jarabe|capsula|farmacia)\b"]),
    ("higiene_bucal",        [r"\b(pasta\s*dental|crema\s*dental|cepillo|colgate|sensodyne|enjuague|dentifrico)\b"]),
    ("cuidado_capilar",      [r"\b(shampoo|champu|acondicionador|crema\s*para\s*peinar|tratamiento\s*capilar)\b"]),
    ("cuidado_corporal",     [r"\b(jabon|gel\s*de\s*bano|desodorante|crema\s*corporal|hidratante)\b"]),
    ("higiene_femenina",     [r"\b(toalla\s*sanitaria|toalla\s*femenina|kotex|tampax|tampon|protector)\b"]),
    ("papel_higienico",      [r"\b(papel\s*higienico|papel\s*toilet|papel\s*toilette|rollo\s*de\s*papel)\b"]),
    ("limpieza_hogar",       [r"\b(detergente|jabon\s*en\s*polvo|cloro|desinfectante|lavaplatos|limpiavidrios|suavizante)\b"]),
    ("bebidas_gaseosas",     [r"\b(coca\s*cola|coca|pepsi|7up|fanta|chinotto|frescolita|malta|gaseosa|refresco)\b"]),
    ("agua",                 [r"\b(agua\s*mineral|agua\s*embotellada|botellon\s*de\s*agua|agua\s*natural)\b"]),
    ("jugos",                [r"\b(jugo|nectar|tampico|yukery)\b"]),
    ("licores",              [r"\b(ron|vodka|whisky|cerveza|vino|polar|regional|solera)\b"]),
    ("lacteos_leche",        [r"\b(leche|leche\s*en\s*polvo|leche\s*entera|leche\s*deslactosada|lechera)\b"]),
    ("lacteos_otros",        [r"\b(queso|yogurt|yogur|crema\s*de\s*leche|mantequilla|margarina)\b"]),
    ("huevos",               [r"\b(huevos?|carton\s*de\s*huevos?)\b"]),
    ("carniceria",           [r"\b(pollo|carne|res|cerdo|chuleta|costilla|pernil|hamburguesa|salchicha)\b"]),
    ("charcuteria",          [r"\b(jamon|mortadela|salami|chorizo|tocineta|tocino)\b"]),
    ("pescaderia",           [r"\b(atun|sardina|pescado|salmon|trucha|merluza)\b"]),
    ("frutas",               [r"\b(manzana|banana|cambur|naranja|pina|piña|patilla|lechosa|mango|fresa|limon|aguacate)\b"]),
    ("vegetales",            [r"\b(tomate|cebolla|papa|zanahoria|lechuga|pepino|pimenton|ajoporro|celery|aji|ajo|cilantro|perejil)\b"]),
    ("harinas",              [r"\b(harina|harina\s*pan|harina\s*precocida|p\.?a\.?n\.?)\b"]),
    ("arroz_granos",         [r"\b(arroz|caraota|frijol|lenteja|quinchoncho)\b"]),
    ("pasta",                [r"\b(pasta|spaghetti|fideo|macarron|tallarin|ravioli|lasaña)\b"]),
    ("aceites_vinagres",     [r"\b(aceite|oliva|vinagre|maiz|girasol|soya)\b"]),
    ("azucar_endulzantes",   [r"\b(azucar|stevia|edulcorante|panela|papelon)\b"]),
    ("cafe",                 [r"\b(cafe|guayoyo|fama\s*de\s*america|venezia|cafe\s*madrid|nespresso|expreso)\b"]),
    ("snacks_galletas",      [r"\b(galleta|chizito|doritos|cheetos|papas\s*fritas|chips|snack|gomitas|chocolate|chocolat)\b"]),
    ("panaderia",            [r"\b(pan|pan\s*canilla|pan\s*sobado|tortilla|arepa)\b"]),
    ("condimentos",          [r"\b(salsa|mayonesa|ketchup|mostaza|salsa\s*de\s*soya|salsa\s*ingles|sazon|adobo|comino|oregano)\b"]),
    ("enlatados",            [r"\b(enlatado|conserva|lata\s*de)\b"]),
    ("mascotas",             [r"\b(perro|gato|alimento\s*para\s*mascota|dog\s*chow|whiskas)\b"]),
]


def _normalizar(texto: str) -> str:
    """Lowercase + sin acentos para matching consistente."""
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t


def detectar_cadena(texto: str) -> Optional[str]:
    """Devuelve el nombre canónico de la cadena mencionada, o None."""
    t = _normalizar(texto)
    for canonico, patrones in CADENAS_PATTERNS.items():
        for p in patrones:
            if re.search(p, t):
                return canonico
    return None


def detectar_rubro(texto: str) -> Optional[str]:
    """Devuelve el código de rubro detectado, o None."""
    t = _normalizar(texto)
    for rubro, patrones in RUBROS_PATTERNS:
        for p in patrones:
            if re.search(p, t):
                return rubro
    return None


def enriquecer(texto: str) -> tuple[Optional[str], Optional[str]]:
    """Devuelve (rubro, cadena) detectados en el texto."""
    return detectar_rubro(texto), detectar_cadena(texto)


# ── Procesamiento batch para enriquecer históricas ──────────────────────────

async def enriquecer_pendientes(db: AsyncSession, limite: int = 5000) -> int:
    """
    Procesa consultas_usuarios que aún no tienen enriquecida_en y las clasifica.
    Llamable desde una tarea Celery (diaria) o on-demand.

    Retorna el número de filas enriquecidas.
    """
    result = await db.execute(text("""
        SELECT id_consulta::text, texto_consulta_original
        FROM consultas_usuarios
        WHERE enriquecida_en IS NULL
        ORDER BY fecha_consulta DESC
        LIMIT :lim
    """), {"lim": limite})
    rows = result.mappings().all()

    if not rows:
        return 0

    total = 0
    for row in rows:
        rubro, cadena = enriquecer(row["texto_consulta_original"])
        await db.execute(text("""
            UPDATE consultas_usuarios
            SET rubro_detectado = :rubro,
                cadena_mencionada = :cadena,
                enriquecida_en = NOW()
            WHERE id_consulta = CAST(:id AS uuid)
        """), {
            "rubro": rubro,
            "cadena": cadena,
            "id": row["id_consulta"],
        })
        total += 1

    await db.commit()
    logger.info("enriquecedor: %d consultas procesadas (de %d)", total, len(rows))
    return total
