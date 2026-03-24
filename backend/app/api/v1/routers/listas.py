"""
Listas de compras — Compa API
==============================
GET    /listas              → listas del usuario autenticado
POST   /listas              → crear nueva lista
DELETE /listas/{id}         → eliminar lista
POST   /listas/{id}/items   → añadir ítem a lista
DELETE /listas/{id}/items/{item_id} → eliminar ítem
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.api.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ListaCreate(BaseModel):
    nombre: str = "Mi lista"

class ItemCreate(BaseModel):
    nombre_item: str
    cantidad: int = 1


# ── GET /listas ───────────────────────────────────────────────────────────────

@router.get("")
async def get_listas(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna todas las listas del usuario con sus ítems."""
    result = await db.execute(
        text("""
            SELECT
                l.id_lista::text,
                l.nombre,
                l.creado_en,
                l.actualizado_en,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id_item', i.id_item::text,
                            'nombre_item', i.nombre_item,
                            'cantidad', i.cantidad
                        ) ORDER BY i.creado_en
                    ) FILTER (WHERE i.id_item IS NOT NULL),
                    '[]'::json
                ) AS items
            FROM listas_compras l
            LEFT JOIN items_lista i ON i.id_lista = l.id_lista
            WHERE l.id_usuario = CAST(:uid AS uuid)
            GROUP BY l.id_lista
            ORDER BY l.actualizado_en DESC
        """),
        {"uid": current_user["id_usuario"]},
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


# ── POST /listas ──────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_lista(
    body: ListaCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva lista de compras vacía."""
    result = await db.execute(
        text("""
            INSERT INTO listas_compras (id_usuario, nombre)
            VALUES (CAST(:uid AS uuid), :nombre)
            RETURNING id_lista::text, nombre, creado_en, actualizado_en
        """),
        {"uid": current_user["id_usuario"], "nombre": body.nombre},
    )
    await db.commit()
    row = result.mappings().first()
    logger.info("create_lista | usuario=%s lista=%s", current_user["id_usuario"], row["id_lista"])
    return {**dict(row), "items": []}


# ── DELETE /listas/{id} ───────────────────────────────────────────────────────

@router.delete("/{lista_id}", status_code=204)
async def delete_lista(
    lista_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Elimina una lista y todos sus ítems (CASCADE en DB)."""
    result = await db.execute(
        text("""
            DELETE FROM listas_compras
            WHERE id_lista = CAST(:lid AS uuid)
              AND id_usuario = CAST(:uid AS uuid)
        """),
        {"lid": lista_id, "uid": current_user["id_usuario"]},
    )
    await db.commit()
    if result.rowcount == 0:
        raise NotFoundError("Lista no encontrada")


# ── POST /listas/{id}/items ───────────────────────────────────────────────────

@router.post("/{lista_id}/items", status_code=201)
async def add_item(
    lista_id: str,
    body: ItemCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Añade un ítem a la lista (verifica que la lista pertenezca al usuario)."""
    # Verificar propiedad de la lista
    check = await db.execute(
        text("SELECT 1 FROM listas_compras WHERE id_lista = CAST(:lid AS uuid) AND id_usuario = CAST(:uid AS uuid)"),
        {"lid": lista_id, "uid": current_user["id_usuario"]},
    )
    if not check.scalar():
        raise NotFoundError("Lista no encontrada")

    result = await db.execute(
        text("""
            INSERT INTO items_lista (id_lista, nombre_item, cantidad)
            VALUES (CAST(:lid AS uuid), :nombre, :cantidad)
            RETURNING id_item::text, nombre_item, cantidad, creado_en
        """),
        {"lid": lista_id, "nombre": body.nombre_item, "cantidad": body.cantidad},
    )
    await db.commit()
    row = result.mappings().first()
    return dict(row)


# ── DELETE /listas/{id}/items/{item_id} ───────────────────────────────────────

@router.delete("/{lista_id}/items/{item_id}", status_code=204)
async def delete_item(
    lista_id: str,
    item_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un ítem de la lista."""
    result = await db.execute(
        text("""
            DELETE FROM items_lista i
            USING listas_compras l
            WHERE i.id_item = CAST(:iid AS uuid)
              AND i.id_lista = l.id_lista
              AND l.id_lista = CAST(:lid AS uuid)
              AND l.id_usuario = CAST(:uid AS uuid)
        """),
        {"iid": item_id, "lid": lista_id, "uid": current_user["id_usuario"]},
    )
    await db.commit()
    if result.rowcount == 0:
        raise NotFoundError("Ítem no encontrado")
