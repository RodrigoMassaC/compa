import asyncio
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

from anthropic import AsyncAnthropic
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Modelo requerido por el usuario
CLAUDE_MODEL = "claude-sonnet-4-5"

class ProductNormalizer:
    def __init__(self, batch_size: int = 20):
        self.batch_size = batch_size
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY no encontrada en las variables de entorno.")
        self.client = AsyncAnthropic(api_key=self.api_key)
        
    async def get_pending_products(self) -> List[Dict[str, Any]]:
        """Obtiene un lote de productos PENDIENTES de la base de datos."""
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT 
                    pc.id_producto_crudo, 
                    pc.nombre_original, 
                    c.nombre_cadena
                FROM productos_crudos pc
                JOIN establecimientos e ON pc.id_establecimiento = e.id_establecimiento
                JOIN cadenas_comerciales c ON e.id_cadena = c.id_cadena
                WHERE pc.estado_mapeo = 'PENDIENTE'
                LIMIT :batch_size
            """)
            result = await session.execute(query, {"batch_size": self.batch_size})
            return [dict(row._mapping) for row in result]

    def _build_prompt(self, products: List[Dict[str, Any]]) -> str:
        """Construye el prompt para Claude con la lista de productos crudos."""
        prompt = "Eres un experto en catalogación de productos de farmacia y supermercado.\n"
        prompt += "Tu tarea es normalizar y estructurar la siguiente lista de productos crudos extraídos de varias tiendas.\n"
        prompt += "Para cada producto, extrae la siguiente información estructurada y devuélvela EXACTAMENTE como un array JSON válido sin texto adicional:\n"
        prompt += """
        [
          {
            "id_crudo": "uuid-del-producto-crudo",
            "exito": true o false (si pudiste identificarlo),
            "nombre_estandar": "Nombre genérico o estandarizado del producto",
            "marca": "Marca del producto",
            "presentacion": "Ej: 500 mg, 1 Litro, 10 Tabletas",
            "unidad_medida": "Ej: mg, ml, lt, und, tabletas",
            "categoria": "Categoría principal (Ej: Analgésicos, Cuidado Cabello)"
          }
        ]
        """
        prompt += "\n\nIMPORTANTE:\n"
        prompt += "- Si un producto no es identificable o faltan datos críticos, pon 'exito': false.\n"
        prompt += "- Responde SOLAMENTE con el JSON array. NADA DE MARKDOWN ni texto explicativo.\n\n"
        
        prompt += "LISTA DE PRODUCTOS A NORMALIZAR:\n"
        for p in products:
            prompt += f"- ID: {p['id_producto_crudo']} | Cadena: {p['nombre_cadena']} | Nombre Crudo: {p['nombre_original']}\n"
            
        return prompt

    async def _call_claude(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Llama a la API de Anthropic Claude para normalizar los productos."""
        if not products:
            return []
            
        prompt = self._build_prompt(products)
        
        try:
            response = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                temperature=0.1,  # Baja temperatura para respuestas consistentes JSON
                system="Eres una API de datos puros que responde estrictamente en JSON array. Nunca produces texto markdown.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            # Limpiar posible markdown wrapper por si acaso Claude ignora las instrucciones
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            return json.loads(response_text)
            
        except Exception as e:
            logger.error(f"Error llamando a Claude API: {e}")
            return []

    async def _process_normalized_results(self, normalized_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Toma los resultados de Claude y crea/vincula en productos_maestros."""
        stats = {
            "procesados": len(normalized_data),
            "nuevos_maestros": 0,
            "vinculados": 0,
            "requiere_humano": 0,
            "errores": 0
        }
        
        async with AsyncSessionLocal() as session:
            try:
                for data in normalized_data:
                    id_crudo = data.get("id_crudo")
                    if not id_crudo:
                        continue
                        
                    # Si la IA no pudo normalizar, marcar para revisión humana
                    if not data.get("exito"):
                        await session.execute(
                            text("UPDATE productos_crudos SET estado_mapeo = 'REQUIERE_HUMANO' WHERE id_producto_crudo = :id"),
                            {"id": id_crudo}
                        )
                        stats["requiere_humano"] += 1
                        continue

                    # Buscar si ya existe el maestro
                    maestro_query = text("""
                        SELECT id_producto_maestro 
                        FROM productos_maestros 
                        WHERE nombre_estandar = :nombre AND marca = :marca AND presentacion = :presentacion
                    """)
                    
                    result = await session.execute(maestro_query, {
                        "nombre": data["nombre_estandar"],
                        "marca": data["marca"],
                        "presentacion": data["presentacion"]
                    })
                    
                    maestro = result.fetchone()
                    
                    if maestro:
                        id_maestro = maestro[0]
                        stats["vinculados"] += 1
                    else:
                        # Crear nuevo producto maestro
                        insert_maestro = text("""
                            INSERT INTO productos_maestros (nombre_estandar, marca, presentacion, unidad_medida)
                            VALUES (:nombre, :marca, :presentacion, :unidad)
                            RETURNING id_producto_maestro
                        """)
                        result_insert = await session.execute(insert_maestro, {
                            "nombre": data["nombre_estandar"],
                            "marca": data["marca"],
                            "presentacion": data["presentacion"],
                            "unidad": data.get("unidad_medida")
                        })
                        id_maestro = result_insert.fetchone()[0]
                        stats["nuevos_maestros"] += 1

                    # Vincular crudo con maestro y actualizar estado
                    update_crudo = text("""
                        UPDATE productos_crudos 
                        SET id_producto_maestro = :id_maestro, estado_mapeo = 'MAPEA_OK'
                        WHERE id_producto_crudo = :id_crudo
                    """)
                    await session.execute(update_crudo, {
                        "id_maestro": id_maestro,
                        "id_crudo": id_crudo
                    })
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error procesando resultados en DB: {e}")
                stats["errores"] += 1
                
        return stats

    async def run(self):
        """Metodo principal del worker para ejecutar un lote de normalización."""
        logger.info(f"=== INICIANDO LOTE DE NORMALIZACIÓN IA (Max: {self.batch_size}) ===")
        
        products = await self.get_pending_products()
        if not products:
            logger.info("No hay productos PENDIENTES para normalizar. Terminando.")
            return {"status": "ok", "msg": "No hay productos pendientes"}
            
        logger.info(f"Se encontraron {len(products)} productos PENDIENTES. Llamando a Claude {CLAUDE_MODEL}...")
        
        normalized_results = await self._call_claude(products)
        
        if not normalized_results:
            logger.error("Claude no devolvió resultados válidos o hubo un error de API.")
            return {"status": "error", "msg": "Error en API Claude"}
            
        logger.info(f"Claude devolvió {len(normalized_results)} resultados. Procesando en Base de Datos...")
        
        stats = await self._process_normalized_results(normalized_results)
        
        logger.info(f"=== RESULTADOS DEL LOTE ===")
        logger.info(f"Procesados por IA: {stats['procesados']}")
        logger.info(f"Nuevos Maestros:   {stats['nuevos_maestros']}")
        logger.info(f"Vinculados Exist:  {stats['vinculados']}")
        logger.info(f"Req Humano/Fallos: {stats['requiere_humano']}")
        logger.info(f"Errores DB:        {stats['errores']}")
        
        return stats

if __name__ == "__main__":
    # Permite correr manualmente python normalizer.py
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ProductNormalizer().run())
