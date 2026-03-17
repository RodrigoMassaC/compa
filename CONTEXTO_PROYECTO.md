# CONTEXTO DEL PROYECTO — Compa Venezuela
# Plataforma de Comparación de Precios e Inteligencia de Mercado con IA

---

## 1. ¿Qué es Compa?

Compa compara precios de productos básicos (alimentos y medicamentos) en Venezuela, ayudando al consumidor a tomar decisiones de compra inteligentes.

### Modelo de negocio dual:

**B2C — Consumidores:**
- Encuentran el **"Carrito Óptimo"**: dónde comprar su lista completa al menor costo posible (máximo 2 establecimientos)
- Comparan precios de productos individuales entre tiendas
- Reciben recomendaciones personalizadas vía chat con agente IA
- **Plan Gratis:** acceso básico al agente y comparación
- **Plan Pro ✨:** funcionalidades avanzadas (listas guardadas, alertas de precio, historial, analytics personales)

**B2B — Empresas:**
- Acceso a inteligencia de mercado y analíticas de precios
- Monitoreo de competencia
- APIs de datos

### Contexto Venezuela:
- Economía **bimonetaria VES/USD** — todos los precios se muestran en ambas monedas
- Tasa de cambio oficial del BCV en tiempo real
- Inflación alta = precios cambian frecuentemente, el scraping constante es crítico
- Usuario objetivo: consumidor venezolano que quiere ahorrar en su compra semanal sin visitar 5 tiendas

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
| Migraciones | Alembic |
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

---

## 4. Estructura de Carpetas EXACTA

```
compa/
├── CONTEXTO_PROYECTO.md          ← Este archivo
├── docker-compose.yml
├── backend/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   ├── security.py
│       │   ├── rate_limiter.py
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
│       │           ├── agent.py       ← Agente IA conversacional ✅ ACTIVO
│       │           ├── catalog.py     ← Endpoints de catálogo ✅ ACTIVO
│       │           ├── auth.py        ← Autenticación (pendiente)
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
└── frontend/
    └── src/
        └── app/
            ├── page.tsx               ← Landing page ✅ ACTIVO
            └── chat/
                └── page.tsx           ← Interfaz agente IA ✅ ACTIVO
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

**`usuarios`** — (pendiente de implementar completamente)
```sql
id_usuario UUID PK
email VARCHAR UNIQUE
nombre VARCHAR
plan ENUM('gratis', 'pro')
creado_en TIMESTAMP
```

**`listas_compras`** — (pendiente de implementar)
```sql
id_lista UUID PK
id_usuario UUID FK
nombre VARCHAR
creado_en TIMESTAMP
```

**`items_lista`** — (pendiente de implementar)
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
GET  /api/v1/productos/buscar?q=leche     ← Búsqueda de productos
GET  /api/v1/productos/{id}/precios       ← Precios de un producto por tienda
GET  /api/v1/cadenas                      ← Lista de cadenas comerciales
GET  /api/v1/tasa                         ← Tasa BCV actual
POST /api/v1/agent/chat                   ← Agente IA conversacional
```

---

## 8. Agente IA — Estado Actual y Decisiones Tomadas

**Archivo:** `./backend/app/api/v1/routers/agent.py`
**Modelo:** `claude-haiku-4-5`

### Flujo completo del agente:
1. Recibe `mensaje` (string) + `historial` (array de mensajes previos `{role, content}`)
2. **Clasificación con contexto:** Claude analiza el mensaje CON los últimos 6 mensajes del historial → decide `buscar` o `conversar`, genera hasta 3 términos de búsqueda con variantes semánticas
3. **Búsqueda en DB:** Query SQL con similitud trigram (threshold **0.30**), sin ILIKE fallback
4. **Filtrado por relevancia:** Claude evalúa los resultados y descarta productos irrelevantes (ej: descarta "Chocolate con Leche" cuando se busca "leche")
5. **Generación de respuesta:** Claude genera respuesta útil con los productos filtrados, comparando precios entre tiendas
6. Retorna `{respuesta, productos[], tipo}`

### Decisiones de diseño importantes:
- **Threshold trigram 0.30** (no bajar de aquí — con 0.15 entran demasiados falsos positivos)
- **Sin ILIKE fallback** — fue eliminado porque matcheaba productos donde la palabra buscada era solo un ingrediente
- **Filtro post-búsqueda con IA** — paso esencial para limpiar resultados antes de mostrarlos
- **Ordenamiento por precio mínimo** — no por similitud trigram
- **Límite de 5 productos** por respuesta
- **Memoria conversacional** — historial de últimos 6 mensajes pasa al clasificador
- **Prompts `system` separados** del mensaje `user` (mejor control del modelo)

### Reglas del agente (RESPONSE_SYSTEM prompt):
- NUNCA sugerir "revisar en otros supermercados" — eso es exactamente lo que Compa hace por el usuario
- SIEMPRE comparar tiendas cuando hay más de una opción disponible
- Mostrar precios siempre en USD y Bs
- Tono profesional y directo, español venezolano natural
- Máximo 3-4 líneas de texto narrativo

---

## 9. Frontend — Estado Actual

**Archivo:** `./frontend/src/app/chat/page.tsx`

### Implementado:
- Sidebar con historial (hardcodeado), botón "Nueva consulta"
- Header con ubicación (Maracay, Aragua — hardcodeado) y tasa BCV
- Chat completo con mensajes usuario/agente
- **`renderMarkdown()`** — convierte `**texto**` en negritas reales
- **`ProductCard`** — tarjeta individual por producto con:
  - Badge "Mejor precio" en el más barato
  - Nombre, marca, presentación, precio USD + Bs, tienda en verde
  - Comparación de tiendas expandida si hay más de una
- Botones "Ver otra marca" (rellena el input) y "Añadir a la lista" (sin funcionalidad aún)
- Sugerencias rápidas en pantalla vacía
- Typing indicator animado
- Planes visible en sidebar: "Plan Gratis" / "Mejorar a Pro ✨"

### Bugs conocidos pendientes:
- Botones "Ver otra marca" / "Añadir a la lista" aparecen en el header en algunos casos (CSS)
- Historial de conversaciones hardcodeado (no persiste)

---

## 10. Funcionalidad de Listas de Compras — PRÓXIMO A IMPLEMENTAR

**Esta es la funcionalidad central del producto — el "Carrito Óptimo".**

### Visión exacta:
El usuario envía una lista de productos (en lenguaje natural o por interfaz) y Compa calcula dónde le sale más barata la compra **total**, no producto por producto.

### Lógica del Carrito Óptimo:
- **Opción 1 — Todo en una tienda:** Calcular el total de la lista en cada tienda disponible y recomendar la más barata en total (aunque algún producto individual sea más caro ahí)
- **Opción 2 — Compra dividida (máximo 2 tiendas):** Evaluar si dividir la compra entre 2 tiendas genera un ahorro significativo vs ir a una sola
- Mostrar el **ahorro estimado** vs la opción más cara
- Considerar productos que no están disponibles en todas las tiendas

### Ejemplo de output esperado:
```
Lista: leche, arroz, pañales, jabón

🏆 Mejor opción — Todo en Excelsior Gama: $18.50
   Ahorro vs opción más cara: $4.20

📍 Alternativa dividida:
   Excelsior Gama (leche, arroz, jabón): $12.30
   Farmatodo (pañales): $4.80
   Total: $17.10 — Ahorro adicional: $1.40 (pero requiere ir a 2 tiendas)
```

### Tablas DB necesarias (pendientes de migración):
- `listas_compras` — listas guardadas por usuario
- `items_lista` — productos dentro de cada lista

### Decisiones pendientes de tomar:
- ¿Input por chat ("necesito leche, arroz y pañales") o interfaz dedicada de lista?
- ¿Implementar compra dividida en v1 o solo "todo en una tienda"?
- ¿Las listas anónimas (sin registro) se guardan en sesión Redis o no se guardan?

---

## 11. Registro de Usuarios y Membresías

### Planes:
- **Plan Gratis:** Acceso al agente, comparación básica, sin listas guardadas
- **Plan Pro ✨:** Listas guardadas, alertas de precio, historial, funciones avanzadas

### Estado: Pendiente de implementar
- Las tablas de `usuarios` existen en el schema pero la autenticación no está activa
- La UI ya muestra el plan ("Plan Gratis" / "Mejorar a Pro ✨") pero sin backend real
- Implementar con JWT (ya configurado en `security.py`)
- Pagos futuros con Stripe

---

## 12. Canales Futuros

### WhatsApp (FASE 5):
- El usuario podrá enviar su lista de compras por WhatsApp
- El agente responde con el Carrito Óptimo directamente en el chat
- Integración via Meta Business API + webhooks
- Archivo base ya existe: `./backend/app/services/whatsapp/`

---

## 13. Fases del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ Completo | Docker + DB + FastAPI + tasa BCV |
| 2 | ✅ Completo | 5 scrapers + normalizador IA |
| 3 | ✅ Completo | Agente conversacional + endpoints de búsqueda |
| 4 | 🔄 En progreso | Frontend Next.js + chat del agente |
| 4.1 | 🔴 Próximo | Listas de compras / Carrito Óptimo |
| 4.2 | 🔴 Próximo | Registro de usuarios + membresías |
| 5 | ⏳ Futuro | WhatsApp + Stripe + crowdsourcing |

---

## 14. Variables de Entorno (.env desarrollo)

```env
DATABASE_URL=postgresql+asyncpg://compa_user:compa_pass@localhost:5432/compa_dev
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=cambia-esto-por-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
META_WHATSAPP_TOKEN=
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=
STRIPE_SECRET_KEY=
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

# Frontend — hot reload activo, no necesita reinicio
cp ~/Downloads/page.tsx ./frontend/src/app/chat/page.tsx

# Levantar todo
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f compa-api
```

---

## 16. Principios y Aprendizajes Técnicos

1. **Trigram sin ILIKE** — el fallback ILIKE trae demasiado ruido. Threshold ≥ 0.30
2. **Filtro post-búsqueda con IA** — necesario para productos donde la palabra buscada es ingrediente secundario
3. **Memoria conversacional** — pasar historial al clasificador es esencial para contexto ("otra marca", "más barato", etc.)
4. **Gama solo tiene food/despensa** — su e-commerce no cubre higiene, hogar ni bebidas
5. **Precios siempre en dos monedas** — USD y Bs usando tasa BCV de `historico_tasa_bcv`
6. **Scrapers frágiles** — selectores CSS cambian frecuentemente; `[class*="price"]` más resiliente que clases específicas
7. **Normalizador resumable** — solo procesa `PENDIENTE`, esencial cuando se corta el crédito de API a mitad del proceso
8. **UUIDs en PostgreSQL** — nunca generar en Python, dejar que la DB los genere con `uuid_generate_v4()`
