# CONTEXTO DEL PROYECTO — Compa Venezuela
# Plataforma de Comparación de Precios e Inteligencia de Mercado con IA

---

## 1. ¿Qué es Compa?

Compa compara precios de productos básicos (alimentos y medicamentos) en Venezuela, ayudando al consumidor a tomar decisiones de compra inteligentes.

### Modelo de negocio dual:

**B2C — Consumidores:**
- Encuentran el **"Carrito Óptimo"**: dónde comprar su lista completa al menor costo posible
- Comparan precios de productos individuales entre tiendas
- Reciben recomendaciones personalizadas vía chat con agente IA
- **Plan Gratis:** acceso básico al agente y comparación
- **Plan Pro ✨:** funcionalidades avanzadas (listas guardadas, alertas de precio, historial)

**B2B — Empresas (Retailers y Marcas):**
- Planes Básico / Pro / Premium con acceso a inteligencia de mercado
- Monitoreo de competencia, datos por sucursal/SKU
- Event tracking ya implementado como fundación de analíticas B2B

### Contexto Venezuela:
- Economía **bimonetaria VES/USD** — todos los precios se muestran en ambas monedas
- Tasa de cambio oficial del BCV en tiempo real
- Inflación alta = precios cambian frecuentemente, el scraping constante es crítico
- Usuario objetivo: consumidor venezolano que quiere ahorrar en su compra semanal

---

## 2. Stack Tecnológico FIJO — no cambiar sin consultar

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | Python 3.11 + FastAPI |
| Base de datos | PostgreSQL 15 + PostGIS + pg_trgm |
| Cache / Sesiones | Redis 7 |
| Cola de tareas | Celery |
| ORM | SQLAlchemy 2.0 async |
| Migraciones | Alembic + migraciones SQL manuales |
| IA | Anthropic API — Claude Haiku (`claude-haiku-4-5`) |
| Scraping | Scrapy (Python) |
| Contenedores | Docker + docker-compose |
| Pagos (futuro) | Stripe |
| Mensajería (futuro) | WhatsApp via Meta API |

---

## 3. Identidad en Código

```
Repositorio y carpeta raíz: compa/
DB name:     compa_dev
DB user:     compa_user
DB pass:     compa_pass
DB puerto:   5432

Prefijos Docker:
  compa-api      → FastAPI en puerto 8000
  compa-db       → PostgreSQL en puerto 5432
  compa-redis    → Redis en puerto 6379
  compa-worker   → Celery worker
```

**URLs de desarrollo:**
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Variable de entorno frontend: `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`

---

## 4. Estructura de Carpetas EXACTA

```
compa/
├── CONTEXTO_PROYECTO.md          ← Este archivo
├── docker-compose.yml
├── backend/
│   ├── .env                       ← Variables reales (gitignored)
│   ├── .env.example               ← Plantilla de variables
│   └── app/
│       ├── main.py                ← CORS restringido a ALLOWED_ORIGINS
│       ├── core/
│       │   ├── config.py          ← Settings con allowed_origins + cors_origins
│       │   ├── database.py
│       │   ├── security.py
│       │   ├── rate_limiter.py    ← Redis rate limiting
│       │   └── exceptions.py
│       ├── models/
│       │   ├── catalog.py
│       │   ├── prices.py
│       │   ├── users.py
│       │   ├── crowdsourcing.py
│       │   └── sessions.py
│       ├── schemas/
│       │   ├── catalog_schema.py
│       │   ├── scraper_schema.py
│       │   ├── user_schema.py
│       │   └── webhook_schema.py
│       ├── api/
│       │   ├── dependencies.py
│       │   └── v1/
│       │       ├── router.py
│       │       └── routers/
│       │           ├── agent.py       ← Agente IA + Carrito Óptimo ✅ ACTIVO
│       │           ├── catalog.py     ← Endpoints de catálogo + tasa BCV ✅ ACTIVO
│       │           ├── auth.py        ← JWT auth (register/login/me) ✅ ACTIVO
│       │           ├── b2b.py         ← Endpoints B2B (pendiente)
│       │           ├── webhooks.py    ← WhatsApp webhooks (futuro)
│       │           └── crowdsource.py ← Crowdsourcing (futuro)
│       └── services/
│           ├── normalizador/
│           │   └── normalizer.py      ← Normalizador IA ✅ ACTIVO
│           ├── scraper/
│           │   ├── base_spider.py
│           │   └── spiders/           ← 5 scrapers activos ✅
│           ├── session_manager/
│           │   └── redis_session.py
│           ├── whatsapp/              ← Futuro
│           ├── billing/               ← Futuro (Stripe)
│           └── vision_ocr/            ← Futuro
├── worker/
│   ├── celery_app.py
│   └── tasks.py
├── scripts/
│   └── init_db.py
├── alembic/
│   └── versions/
├── migrations/
│   └── 001_add_user_profile_fields.sql  ← Agrega campos de perfil a usuarios
└── frontend/
    ├── .env.local                 ← NEXT_PUBLIC_API_URL (gitignored)
    ├── .env.local.example         ← Plantilla
    └── src/
        ├── lib/
        │   └── auth.ts            ← Token helpers (saveAuth, getToken, clearAuth...)
        └── app/
            ├── page.tsx           ← Landing page con links a /auth ✅ ACTIVO
            ├── auth/
            │   └── page.tsx       ← Login/Registro (tabs, campos opcionales) ✅ ACTIVO
            └── chat/
                └── page.tsx       ← Interfaz agente IA + Carrito Óptimo ✅ ACTIVO
```

---

## 5. Base de Datos — Esquema Principal

### Reglas de arquitectura CRÍTICAS — nunca violar:
1. **NUNCA hacer UPDATE en `historial_precios`** — solo INSERT siempre
2. La conversión VES/USD ocurre **SOLO en la vista SQL**, nunca en Python
3. **UUIDs se generan en PostgreSQL** con `uuid_generate_v4()`, no en Python
4. `historial_precios` usa BIGSERIAL como PK por volumen esperado
5. Todo endpoint va bajo `/api/v1/` (versionado desde el inicio)
6. Lógica de negocio en `services/`, los routers solo reciben y delegan
7. Usar SQLAlchemy async (`AsyncSession`) en todos los accesos a DB
8. **Rate limiting** en TODOS los endpoints que invocan al LLM
9. El LLM **NO hace conversiones matemáticas** de moneda
10. Contexto conversacional en Redis (TTL 24h), no en PostgreSQL
11. Todos los spiders heredan de `BaseSpider`
12. Siempre delay aleatorio 1-3 segundos entre requests de scraping
13. Datos scrapeados van a `productos_crudos` con `estado_normalizacion='PENDIENTE'`

### Tablas principales:

**`cadenas_comerciales`** — Las cadenas de tiendas
```sql
id_cadena UUID PK
nombre_cadena VARCHAR
```

**`establecimientos`** — Sucursales de cada cadena
```sql
id_establecimiento UUID PK
id_cadena UUID FK
nombre VARCHAR
```

**`categorias`** — Árbol de categorías (self-referential)
```sql
id_categoria UUID PK
nombre VARCHAR(100)
descripcion TEXT
id_categoria_padre UUID FK
nivel INTEGER
activo BOOLEAN
```

**`productos_maestros`** — Catálogo normalizado único
```sql
id_producto_maestro UUID PK
nombre_estandar VARCHAR
marca VARCHAR
presentacion VARCHAR
unidad_medida VARCHAR
id_categoria UUID FK
terminos_busqueda TEXT    ← Para búsqueda trigram
```

**`productos_crudos`** — Productos tal como vienen de cada scraper
```sql
id_producto_crudo UUID PK
id_establecimiento UUID FK
id_producto_maestro UUID FK   ← Mapeado por el normalizador
nombre_original VARCHAR
estado_normalizacion ENUM('PENDIENTE', 'NORMALIZADO', 'REQUIERE_HUMANO')
```

**`historial_precios`** — Solo INSERT, nunca UPDATE
```sql
id BIGSERIAL PK
id_producto_crudo UUID FK
precio_bruto DECIMAL
moneda_origen VARCHAR    ← 'USD' o 'VES'
fecha_lectura TIMESTAMP
```

**`historico_tasa_bcv`** — Tasa de cambio BCV
```sql
valor_usd DECIMAL
fecha TIMESTAMP
```

**`usuarios`** — ✅ ACTIVO con campos de perfil extendidos
```sql
id_usuario UUID PK
email VARCHAR UNIQUE
nombre_completo VARCHAR
hashed_password VARCHAR
plan ENUM('gratis', 'pro', 'b2b_basico', 'b2b_pro', 'b2b_premium')
fecha_nacimiento DATE          ← Migración 001 ✅
sexo VARCHAR(20)               ← Migración 001 ✅
ciudad VARCHAR(100)            ← Migración 001 ✅
estado_ven VARCHAR(50)         ← 24 estados venezolanos, migración 001 ✅
telefono_wa VARCHAR(20)        ← Para futura integración WhatsApp
creado_en TIMESTAMP
activo BOOLEAN
```

**`listas_compras`** — (pendiente de migración)
```sql
id_lista UUID PK
id_usuario UUID FK
nombre VARCHAR
creado_en TIMESTAMP
```

**`items_lista`** — (pendiente de migración)
```sql
id_item UUID PK
id_lista UUID FK
id_producto_maestro UUID FK
cantidad INTEGER
```

### UUIDs importantes:
```
Gama establecimiento:   3411bdba-501d-4d0f-8cb5-d598314502e4
Gama cadena:            710be948-38ef-4a93-bc09-eda81dc9d627
Categoría Alimentos:    bc60dedd-82c3-43bd-ba3c-8e26548965fb
Categoría Bebidas:      4bcc6340-a330-4218-baac-63475f5e2461
Categoría Higiene:      8b658f8a-945c-4a79-9525-7068f6d7780d
Categoría Medicamentos: 79793cc8-0ee2-45d0-a325-4677b2b199bb
```

---

## 6. Estado Actual de Datos (Marzo 2026)

| Cadena | Productos scrapeados | Tipo |
|--------|---------------------|------|
| Farmago | 4,182 | Farmacia |
| Central Madeirense | 3,392 | Supermercado |
| Locatel | 1,386 | Farmacia/salud |
| Excelsior Gama | 571 | Supermercado (solo food/despensa) |
| Farmatodo | 248 | Farmacia |
| **TOTAL** | **~9,779** | |

**Normalización:** 9,775 productos → 6,477 productos maestros únicos
- Herramienta: Claude Haiku + similitud trigram (threshold 0.6)
- Estado: completado, algunos en `REQUIERE_HUMANO` pendientes de revisión

**Nota importante:** Excelsior Gama solo tiene food/despensa en su e-commerce. No hay productos de higiene, hogar ni bebidas disponibles vía scraping.

---

## 7. API REST — Endpoints Disponibles

```
GET  /api/v1/catalog/buscar?q=leche   ← Búsqueda de productos
GET  /api/v1/catalog/tasa             ← Tasa BCV actual
POST /api/v1/agent/chat               ← Agente IA conversacional (rate limited)
POST /api/v1/auth/register            ← Registro de usuarios ✅
POST /api/v1/auth/login               ← Login JWT ✅
GET  /api/v1/auth/me                  ← Perfil del usuario autenticado ✅
```

---

## 8. Agente IA — Estado Actual y Decisiones Tomadas

**Archivo:** `./backend/app/api/v1/routers/agent.py`
**Modelo:** `claude-haiku-4-5`

### Flujo completo del agente (búsqueda individual):
1. Recibe `mensaje` (string) + `historial` (array de mensajes previos `{role, content}`)
2. **Clasificación con contexto:** Claude analiza el mensaje CON los últimos 6 mensajes del historial → decide `buscar` o `conversar`, genera hasta 3 términos de búsqueda con variantes semánticas
3. **Búsqueda en DB:** Query SQL con similitud trigram (threshold **0.35**), sin ILIKE fallback
4. **Pre-filtro substring (gratis):** Descarta productos cuyo nombre/marca no contiene ninguna palabra clave (≥4 chars) de los términos buscados
5. **Filtro IA de relevancia:** Claude evalúa los resultados con todos los términos + mensaje original — descarta falsos positivos semánticos
6. **Generación de respuesta:** Claude genera respuesta útil con productos filtrados, comparando precios
7. **Event tracking:** `log_consulta()` registra la consulta para analíticas B2B
8. Retorna `{respuesta, productos[], tipo}`

### Flujo Carrito Óptimo:
1. Detecta prefijo `"Carrito:"` en el mensaje
2. Extrae items de la lista
3. Para cada item × cada tienda: `buscar_item_por_tienda()` con threshold 0.35
4. `filtrar_carrito_batch()` — Claude valida en batch si los productos encontrados corresponden a lo buscado
5. `calcular_carrito_optimo()` — agrupa por tienda, calcula totales USD+VES, ordena por precio total
6. Retorna `{respuesta, carrito: {tiendas[], ahorro_maximo_usd, total_items}, tipo: "carrito"}`

### Rate Limiting:
- **Anónimo:** 15 requests/minuto por IP
- **Autenticado:** 40 requests/minuto por user_id
- Implementado con Redis en `core/rate_limiter.py`
- Se aplica con `check_rate_limit()` en el endpoint `/agent/chat`

### Anti-falsos-positivos (3 capas):
1. **Threshold DB:** 0.35 (antes 0.30) — menos productos entran al pipeline
2. **Pre-filtro substring:** Elimina productos gratis sin llamar a Claude (Frescolita no contiene "leche")
3. **Filtro IA con contexto completo:** Claude recibe todos los términos + mensaje original del usuario

### Decisiones de diseño importantes:
- **Threshold trigram 0.35** — subido de 0.30 para reducir falsos positivos
- **Sin ILIKE fallback** — fue eliminado porque matcheaba ingredientes secundarios
- **Filtro post-búsqueda con IA** — paso esencial para limpiar resultados
- **Ordenamiento por precio mínimo** — no por similitud trigram
- **Límite de 5 productos** por respuesta
- **Memoria conversacional** — historial de últimos 6 mensajes pasa al clasificador

### Reglas del agente (RESPONSE_SYSTEM prompt):
- NUNCA sugerir "revisar en otros supermercados" — eso es exactamente lo que Compa hace
- SIEMPRE comparar tiendas cuando hay más de una opción disponible
- Mostrar precios siempre en USD y Bs
- Tono profesional y directo, español venezolano natural
- Máximo 3-4 líneas de texto narrativo

---

## 9. Autenticación — Estado Actual ✅

**Backend:** `./backend/app/api/v1/routers/auth.py`
**Frontend:** `./frontend/src/app/auth/page.tsx` + `./frontend/src/lib/auth.ts`

### Implementado:
- Registro con campos: email, contraseña, nombre completo
- Campos opcionales en registro: fecha nacimiento, sexo, ciudad, estado venezolano (24 estados), teléfono WhatsApp
- Login con JWT (HS256, 24h de expiración)
- Token guardado en `localStorage` vía `lib/auth.ts`
- `/me` endpoint para validar token y obtener perfil
- Sidebar del chat muestra usuario real o "Invitado" si no está autenticado
- Botón de logout (ícono settings en el sidebar)

### Migración aplicada:
`migrations/001_add_user_profile_fields.sql` — agrega `fecha_nacimiento`, `sexo`, `ciudad`, `estado_ven` a `usuarios`

### Pendiente:
- Verificación de email
- Recuperación de contraseña
- Integración WhatsApp como canal de auth alternativo (Fase 5)

---

## 10. Frontend — Estado Actual ✅

**Archivos:**
- `./frontend/src/app/chat/page.tsx` — Chat principal
- `./frontend/src/app/auth/page.tsx` — Login/Registro
- `./frontend/src/app/page.tsx` — Landing page
- `./frontend/src/lib/auth.ts` — Helpers de token

### Implementado en chat:
- Sidebar con **historial real** de conversaciones (localStorage, máx 30, agrupado Hoy/Ayer/Anterior)
- Botón "Nueva consulta" para resetear estado
- Header con ubicación (hardcoded) y tasa BCV **dinámica** (fetch a `/catalog/tasa`)
- **`renderMarkdown()`** — convierte `**texto**` en negritas
- **`ProductCard`** — badge "Mejor precio", nombre, marca, presentación, USD+Bs, comparación multi-tienda
- **`CartOptimalCard`** — totales por tienda, desglose item por item, badge "Lista incompleta"
- **"Añadir a la lista"** — botón en cada respuesta de productos, acumula items en estado
- **Widget flotante** — aparece cuando hay items en lista, muestra count + "Calcular carrito" CTA
- Usuario real en sidebar (nombre + plan) o "Invitado" con link a `/auth`
- Botón logout
- Todas las URLs usan `NEXT_PUBLIC_API_URL` (no hardcoded)

### Landing page:
- Botones "Iniciar sesión" → `/auth` y "Registrarse gratis" → `/auth?mode=register`
- Secciones: hero, logos (Walmart/Farmatodo/etc.), features B2C, features B2B, CTA final

---

## 11. CORS y Variables de Entorno

### Backend:
- CORS restringido a `ALLOWED_ORIGINS` (lista separada por comas)
- Desarrollo: `ALLOWED_ORIGINS=http://localhost:3000`
- Producción: `ALLOWED_ORIGINS=https://app.compa.com,https://compa.com`
- Métodos permitidos: GET, POST, PUT, DELETE, OPTIONS
- Headers permitidos: Authorization, Content-Type

### Frontend:
- `NEXT_PUBLIC_API_URL` — URL base del API
- Desarrollo: `http://localhost:8000/api/v1` (en `.env.local`)
- Producción: `https://api.compa.com/api/v1` (en `.env.production.local`)

---

## 12. Canales Futuros

### WhatsApp (FASE 5):
- El usuario podrá enviar su lista de compras por WhatsApp
- El agente responde con el Carrito Óptimo directamente en el chat
- Integración via Meta Business API + webhooks
- `telefono_wa` ya está en la tabla `usuarios`
- Archivo base existe: `./backend/app/services/whatsapp/`

---

## 13. Fases del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ Completo | Docker + DB + FastAPI + tasa BCV |
| 2 | ✅ Completo | 5 scrapers + normalizador IA |
| 3 | ✅ Completo | Agente conversacional + endpoints de búsqueda |
| 4 | ✅ Completo | Frontend Next.js + chat del agente |
| 4.1 | ✅ Completo | Carrito Óptimo (comparación multi-tienda) |
| 4.2 | ✅ Completo | Autenticación JWT + registro con perfil venezolano |
| 4.3 | ✅ Completo | Rate limiting + event tracking + anti-falsos-positivos |
| 4.4 | ✅ Completo | Historial real + lista de compras frontend + CORS + env vars |
| 5 | 🔴 Próximo | Actualizar scrapers (precios desactualizados) |
| 6 | ⏳ Futuro | Dashboard B2B + planes de pago Stripe |
| 7 | ⏳ Futuro | WhatsApp + crowdsourcing |

---

## 14. Variables de Entorno

### Backend (`.env`):
```env
DATABASE_URL=postgresql+asyncpg://compa_user:compa_pass@compa-db:5432/compa_dev
REDIS_URL=redis://compa-redis:6379
SECRET_KEY=<openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
META_WHATSAPP_TOKEN=
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=
STRIPE_SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:3000
ENV=development
LOG_LEVEL=INFO
```

### Frontend (`.env.local`):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## 15. Comandos de Referencia Rápida

```bash
# Ver estado de contenedores
docker ps

# Reiniciar API después de cambios en backend
docker cp ./backend/app/api/v1/routers/agent.py compa-api:/app/app/api/v1/routers/agent.py
docker restart compa-api

# Ver logs
docker logs compa-api --tail 20

# Conectar a DB
docker exec compa-db psql -U compa_user -d compa_dev

# Query rápida en DB
docker exec compa-db psql -U compa_user -d compa_dev -c "SELECT COUNT(*) FROM productos_maestros;"

# Aplicar migración
docker exec compa-db psql -U compa_user -d compa_dev -f /migrations/001_add_user_profile_fields.sql

# Levantar todo
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f compa-api
```

---

## 16. Principios y Aprendizajes Técnicos

1. **Trigram sin ILIKE** — el fallback ILIKE trae demasiado ruido. Threshold ≥ 0.35
2. **3 capas anti-falsos-positivos** — DB threshold + substring pre-filter (gratis) + Claude semántico
3. **Memoria conversacional** — pasar historial al clasificador es esencial ("otra marca", "más barato")
4. **Gama solo tiene food/despensa** — su e-commerce no cubre higiene, hogar ni bebidas
5. **Precios siempre en dos monedas** — USD y Bs usando tasa BCV de `historico_tasa_bcv`
6. **Scrapers frágiles** — selectores CSS cambian frecuentemente; `[class*="price"]` más resiliente
7. **Normalizador resumable** — solo procesa `PENDIENTE`, esencial cuando se corta el crédito de API
8. **UUIDs en PostgreSQL** — nunca generar en Python, dejar que la DB los genere con `uuid_generate_v4()`
9. **TDZ bug React** — si una variable de estado tiene el mismo nombre que una `const` local en el mismo scope, genera `ReferenceError` por zona temporal muerta. Renombrar la variable local.
10. **`NEXT_PUBLIC_` prefix** — necesario en Next.js para que las env vars sean accesibles en el cliente (browser)
11. **CORS en producción** — usar `ALLOWED_ORIGINS` en `.env` en lugar de `"*"` para seguridad real
