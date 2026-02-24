"""
Configuración de la conexión async a PostgreSQL usando SQLAlchemy 2.0.
Usamos AsyncSession en toda la aplicación (regla de arquitectura #7).
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# Motor async — pool_pre_ping verifica la conexión antes de usarla
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=(settings.env == "development"),  # Log SQL solo en desarrollo
)

# Fábrica de sesiones async
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Clase base para todos los modelos de SQLAlchemy."""
    pass


async def get_db() -> AsyncSession:
    """
    Dependency de FastAPI que provee una sesión async por request.
    Cierra la sesión automáticamente al terminar el bloque.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Verifica que la DB responde — usado en el endpoint /health."""
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
