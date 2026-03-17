from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from uuid import UUID

router = APIRouter()


# ── Reutilizable: CTE de tasa y precios recientes ──
PRECIO_CTE = """
    WITH tasa AS (
        SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1
    ),
    precios_recientes AS (
        SELECT DISTINCT ON (pc.id_producto_maestro, e.id_cadena)
            pc.id_producto_maestro,
            e.id_cadena,
            hp.precio_bruto,
            hp.moneda_origen,
            hp.fecha_lectura
        FROM historial_precios hp
        JOIN productos_crudos pc ON pc.id_producto_crudo = hp.id_producto_crudo
        JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
        ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
    )
"""


@router.get("/productos/buscar")
async def buscar_productos(
    q: str = Query(..., min_length=2, description="Nombre del producto a buscar"),
    db: AsyncSession = Depends(get_db)
):
    """Busca productos en el catálogo maestro y devuelve precios por cadena."""
    try:
        query = text(PRECIO_CTE + """
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
                c.nombre_cadena
            FROM productos_maestros pm
            JOIN precios_recientes pr ON pr.id_producto_maestro = pm.id_producto_maestro
            JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
            WHERE (pm.nombre_estandar ILIKE :search OR pm.marca ILIKE :search OR pm.terminos_busqueda ILIKE :search)
            ORDER BY precio_usd ASC NULLS LAST
            LIMIT 50
        """)

        result = await db.execute(query, {"search": f"%{q}%"})
        rows = result.mappings().all()

        productos = {}
        for row in rows:
            id_prod = str(row["id_producto_maestro"])
            if id_prod not in productos:
                productos[id_prod] = {
                    "id": id_prod,
                    "nombre": row["nombre_estandar"],
                    "marca": row["marca"],
                    "presentacion": row["presentacion"],
                    "ofertas": []
                }
            productos[id_prod]["ofertas"].append({
                "cadena": row["nombre_cadena"],
                "precio_usd": float(row["precio_usd"]) if row["precio_usd"] is not None else None,
                "precio_ves": float(row["precio_ves"]) if row["precio_ves"] is not None else None,
            })

        return {"resultados": list(productos.values()), "total": len(productos)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al buscar productos: {str(e)}")


@router.get("/productos/{id_producto}/precios")
async def precios_producto(
    id_producto: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Devuelve todos los precios actuales de un producto maestro en todas las cadenas."""
    try:
        query = text(PRECIO_CTE + """
            SELECT
                pm.id_producto_maestro,
                pm.nombre_estandar,
                pm.marca,
                pm.presentacion,
                pm.unidad_medida,
                c.nombre_cadena,
                c.id_cadena,
                CASE
                    WHEN pr.moneda_origen = 'USD' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'VES' THEN ROUND(pr.precio_bruto / (SELECT valor_usd FROM tasa), 2)
                END as precio_usd,
                CASE
                    WHEN pr.moneda_origen = 'VES' THEN pr.precio_bruto
                    WHEN pr.moneda_origen = 'USD' THEN ROUND(pr.precio_bruto * (SELECT valor_usd FROM tasa), 2)
                END as precio_ves,
                pr.fecha_lectura
            FROM productos_maestros pm
            JOIN precios_recientes pr ON pr.id_producto_maestro = pm.id_producto_maestro
            JOIN cadenas_comerciales c ON c.id_cadena = pr.id_cadena
            WHERE pm.id_producto_maestro = :id
            ORDER BY precio_usd ASC NULLS LAST
        """)

        result = await db.execute(query, {"id": str(id_producto)})
        rows = result.mappings().all()

        if not rows:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        primera = rows[0]
        precios = []
        for row in rows:
            precio_usd = float(row["precio_usd"]) if row["precio_usd"] is not None else None
            precio_ves = float(row["precio_ves"]) if row["precio_ves"] is not None else None
            precios.append({
                "cadena": row["nombre_cadena"],
                "precio_usd": precio_usd,
                "precio_ves": precio_ves,
                "actualizado": str(row["fecha_lectura"]) if row["fecha_lectura"] else None,
            })

        # Mejor precio
        precios_validos = [p for p in precios if p["precio_usd"] is not None]
        mejor = min(precios_validos, key=lambda x: x["precio_usd"]) if precios_validos else None

        return {
            "id": str(primera["id_producto_maestro"]),
            "nombre": primera["nombre_estandar"],
            "marca": primera["marca"],
            "presentacion": primera["presentacion"],
            "unidad_medida": primera["unidad_medida"],
            "mejor_precio": mejor,
            "precios": precios,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener precios: {str(e)}")


@router.get("/cadenas")
async def listar_cadenas(db: AsyncSession = Depends(get_db)):
    """Devuelve el listado de cadenas comerciales disponibles con conteo de productos."""
    try:
        query = text("""
            SELECT
                c.id_cadena,
                c.nombre_cadena,
                COUNT(DISTINCT pc.id_producto_crudo) as total_productos
            FROM cadenas_comerciales c
            JOIN establecimientos e ON e.id_cadena = c.id_cadena
            JOIN productos_crudos pc ON pc.id_establecimiento = e.id_establecimiento
            GROUP BY c.id_cadena, c.nombre_cadena
            ORDER BY total_productos DESC
        """)
        result = await db.execute(query)
        rows = result.mappings().all()

        return {
            "cadenas": [
                {
                    "id": str(row["id_cadena"]),
                    "nombre": row["nombre_cadena"],
                    "total_productos": row["total_productos"],
                }
                for row in rows
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar cadenas: {str(e)}")


@router.get("/tasa")
async def tasa_bcv(db: AsyncSession = Depends(get_db)):
    """Devuelve la tasa BCV más reciente."""
    try:
        result = await db.execute(text(
            "SELECT valor_usd, fecha FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1"
        ))
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="No hay tasa BCV disponible")
        return {"tasa_usd": float(row["valor_usd"]), "fecha": str(row["fecha"])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener tasa: {str(e)}")
