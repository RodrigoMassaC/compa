# ============================================================
# Compa API — Imagen Docker basada en Python 3.11 slim
# ============================================================

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Metadatos
LABEL maintainer="compa-team"
LABEL description="Compa API — FastAPI + Celery Worker"

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias para:
# - asyncpg (libpq), psycopg2
# - GeoAlchemy2 / GDAL (libgdal)
# - Playwright (chromium)
# - Pillow (libjpeg, zlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python primero (capa cacheada)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Instalar Playwright con Chromium para scraping
RUN playwright install chromium --with-deps 2>/dev/null || true

# Copiar el código fuente (el volumen en dev-mode sobreescribirá esto)
COPY . .

# Puerto expuesto por la API
EXPOSE 8000

# Comando por defecto (docker-compose lo sobreescribe por servicio)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
