from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter()

@router.get("/productos/buscar")
async def buscar_productos(
    q: str = Query(..., min_length=2, description="Nombre del producto a buscar"),
    db: AsyncSession = Depends(get_db)
):
    """
    Busca productos en el catálogo maestro y devuelve sus precios actuales
    en las distintas cadenas comerciales, usando la vista_precios_actuales.
    """
    try:
        query = text("""
            SELECT 
                pm.id_producto_maestro,
                pm.nombre_estandar,
                pm.marca,
                pm.presentacion,
                MAX(CASE WHEN hp.moneda_origen = 'VES' THEN hp.precio_bruto END) as precio_ves,
                ROUND(MAX(CASE WHEN hp.moneda_origen = 'VES' THEN hp.precio_bruto END) / 
                    (SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1), 2
                ) as precio_usd,
                c.nombre_cadena
            FROM productos_maestros pm
            JOIN productos_crudos pc ON pc.id_producto_maestro = pm.id_producto_maestro
            JOIN historial_precios hp ON hp.id_producto_crudo = pc.id_producto_crudo
            JOIN establecimientos e ON pc.id_establecimiento = e.id_establecimiento
            JOIN cadenas_comerciales c ON e.id_cadena = c.id_cadena
            WHERE (pm.nombre_estandar ILIKE :search OR pm.marca ILIKE :search)
            GROUP BY pm.id_producto_maestro, pm.nombre_estandar, pm.marca, pm.presentacion, c.nombre_cadena
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
            
        return {"resultados": list(productos.values())}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al buscar productos: {str(e)}")
