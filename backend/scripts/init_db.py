"""
Script de inicialización del schema de base de datos.
Lee schema_completo.sql y lo ejecuta contra compa_dev.
Uso: docker compose exec compa-api python scripts/init_db.py
"""
import asyncio
import os
from pathlib import Path

import asyncpg
from app.core.config import settings


# Primera búsqueda: montado en /app/schema_completo.sql (docker-compose mount)
SQL_FILE = Path("/app/schema_completo.sql")

# Segunda búsqueda: relativo al script (ejecución local fuera de Docker)
FALLBACK_SQL = Path(__file__).parent.parent.parent / "schema_completo.sql"


async def init_schema() -> None:
    """
    Conecta a PostgreSQL con asyncpg y ejecuta el schema SQL completo.
    Usa la URL de DATABASE_URL pero extrayendo los parámetros de conexión.
    """
    # Convertir URL asyncpg → asyncpg nativo (sin el prefijo postgresql+asyncpg://)
    raw_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # Leer el archivo SQL
    sql_path = SQL_FILE if SQL_FILE.exists() else FALLBACK_SQL
    if not sql_path.exists():
        raise FileNotFoundError(
            f"No se encontró schema_completo.sql en {sql_path}. "
            "Asegúrate de montarlo o copiarlo al contenedor."
        )

    sql_content = sql_path.read_text(encoding="utf-8")
    print(f"📄 Ejecutando schema desde: {sql_path}")

    # Conectar y ejecutar
    conn = await asyncpg.connect(raw_url)
    try:
        await conn.execute(sql_content)
        print("✅ Schema creado exitosamente")
        print("   Tablas y extensiones en compa_dev listas para usar.")
    except Exception as e:
        print(f"❌ Error al ejecutar el schema: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_schema())
