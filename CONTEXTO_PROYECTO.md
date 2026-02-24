# CONTEXTO DEL PROYECTO — Compa
# Plataforma SaaS de Inteligencia y Comparación de Precios con IA

## ¿Qué es Compa?
Compa compara precios de productos básicos (alimentos y medicamentos) en Venezuela.
- B2C: Consumidores encuentran el "Carrito Óptimo" (máx 2 establecimientos)
- B2B: Empresas acceden a inteligencia de mercado y analíticas de precios
- Maneja economía bimonetaria VES/USD con tasa oficial del BCV en tiempo real

## Identidad en código
- Repositorio y carpeta raíz: compa/
- DB name: compa_dev | DB user: compa_user | DB pass: compa_pass
- Prefijos Docker: compa-api, compa-db, compa-redis, compa-worker

## Stack tecnológico FIJO — no cambiar sin consultar
- Backend: Python 3.11 + FastAPI
- Base de datos: PostgreSQL 15 + PostGIS + pg_trgm
- Cola de tareas: Celery + Redis
- ORM: SQLAlchemy 2.0 async + GeoAlchemy2
- Migraciones: Alembic
- IA: LangChain + OpenAI GPT-4o / Claude Sonnet (configurable)
- Scraping: Playwright (Python)
- Frontend: Next.js 14 + TypeScript + TailwindCSS (FASE 2 — no crear ahora)
- Contenedores: Docker + docker-compose

## Estructura de carpetas EXACTA — no inventar, no cambiar

compa/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── rate_limiter.py
│   │   │   └── exceptions.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── catalog.py
│   │   │   ├── prices.py
│   │   │   ├── users.py
│   │   │   ├── crowdsourcing.py
│   │   │   └── sessions.py
│   │   ├── schemas/
│   │   │   ├── catalog_schema.py
│   │   │   ├── scraper_schema.py
│   │   │   ├── user_schema.py
│   │   │   └── webhook_schema.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── v1/
│   │   │       ├── routers/
│   │   │       │   ├── auth.py
│   │   │       │   ├── catalog.py
│   │   │       │   ├── b2b.py
│   │   │       │   ├── webhooks.py
│   │   │       │   └── crowdsource.py
│   │   │       └── router.py
│   │   └── services/
│   │       ├── ai_agent/
│   │       │   ├── agent.py
│   │       │   ├── prompts.py
│   │       │   └── tools/
│   │       ├── session_manager/
│   │       │   └── redis_session.py
│   │       ├── whatsapp/
│   │       │   ├── client.py
│   │       │   └── message_handler.py
│   │       ├── scraper/
│   │       │   ├── engine.py
│   │       │   ├── base_spider.py
│   │       │   └── spiders/
│   │       ├── billing/
│   │       │   └── stripe_service.py
│   │       └── vision_ocr/
│   │           └── validator.py
│   ├── worker/
│   │   ├── celery_app.py
│   │   └── tasks.py
│   ├── scripts/
│   │   └── init_db.py
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example
└── frontend/    <-- FASE 2, NO crear todavía

## Reglas de arquitectura CRÍTICAS — nunca violar

1. NUNCA hacer UPDATE en historial_precios. Solo INSERT siempre
2. La conversión VES/USD ocurre SOLO en la vista SQL (vista_precios_actuales), nunca en Python
3. UUIDs se generan en PostgreSQL con uuid_generate_v4(), no en Python
4. historial_precios usa BIGSERIAL como PK por volumen esperado
5. Todo endpoint va bajo /api/v1/ (versionado desde el inicio)
6. Lógica de negocio en services/, los routers solo reciben y delegan
7. Usar SQLAlchemy async (AsyncSession) en todos los accesos a DB
8. Rate limiting en TODOS los endpoints que invocan al LLM
9. El LLM NO hace conversiones matemáticas de moneda
10. Contexto conversacional en Redis (TTL 24h), no en PostgreSQL
11. El agente LangChain se construye DESPUÉS de tener datos reales en la DB
12. Todos los spiders heredan de BaseSpider y retornan List[ScrapedProduct]
13. Siempre delay aleatorio 1-3 segundos entre requests de scraping
14. Datos scrapeados van a productos_crudos con estado_mapeo='PENDIENTE'

## Variables de entorno — .env de desarrollo local

DATABASE_URL=postgresql+asyncpg://compa_user:compa_pass@localhost:5432/compa_dev
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=cambia-esto-por-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
META_WHATSAPP_TOKEN=
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=
STRIPE_SECRET_KEY=

## Fases — orden estricto, no saltar pasos

FASE 1 (AHORA): Docker + DB con todas las tablas + CRON BCV + FastAPI respondiendo
FASE 2: Spider Playwright (1 cadena piloto) + worker de normalización con LLM
FASE 3: Agente LangChain + Carrito Óptimo + endpoints de búsqueda
FASE 4: Interfaz web Next.js + chat del agente
FASE 5: WhatsApp + pagos + crowdsourcing de campo

## Comandos de referencia rápida

docker compose up -d
docker compose logs -f compa-api
docker exec -it compa-db psql -U compa_user -d compa_dev
docker compose exec compa-api python scripts/init_db.py
curl http://localhost:8000/health
