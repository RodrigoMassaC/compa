"""
Schemas Pydantic para el motor de scraping de Compa.
ScrapedProduct es el contrato que todos los spiders deben retornar.
"""
from pydantic import BaseModel, HttpUrl, field_validator
from decimal import Decimal
from typing import Optional


class ScrapedProduct(BaseModel):
    """
    Resultado de un spider — va directo a productos_crudos con estado_mapeo='PENDIENTE'.
    Regla de arquitectura: todos los spiders retornan List[ScrapedProduct].
    """
    nombre_original: str
    precio_bruto: Decimal
    moneda_origen: str                # 'VES' o 'USD'
    sku_comercio: str                 # ID único del producto en la tienda
    url_origen: str                   # URL completa del producto
    id_establecimiento: Optional[str] = None  # UUID del establecimiento (se llena al guardar)

    @field_validator("moneda_origen")
    @classmethod
    def validate_moneda(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in ("VES", "USD"):
            raise ValueError(f"moneda_origen debe ser 'VES' o 'USD', recibido: {v}")
        return v

    @field_validator("precio_bruto")
    @classmethod
    def validate_precio(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("precio_bruto debe ser mayor que 0")
        return v

    @field_validator("nombre_original", "sku_comercio")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El campo no puede estar vacío")
        return v.strip()
