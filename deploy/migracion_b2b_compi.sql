-- ============================================================================
-- Migración B2B "Compi" — el producto B2B de Compa
-- ============================================================================
-- Crea:
--   1. empresas             → cliente B2B (1 empresa = 1 plan activo)
--   2. empresa_usuarios     → quiénes acceden a la empresa (multi-user en Pro/Premium)
--   3. solicitudes_b2b      → form de contacto público, antes de activación
--   4. Columnas nuevas en consultas_usuarios para enriquecimiento de queries
-- ============================================================================

BEGIN;

-- ── 1. Empresas suscritas a Compi ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS empresas (
    id_empresa          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario_dueno    UUID REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    nombre_comercial    TEXT NOT NULL,
    rif                 TEXT,
    sector              TEXT,                 -- supermercado | farmacia | bodega | licorería | otros
    plan                TEXT NOT NULL CHECK (plan IN ('basico','pro','premium')),
    estado              TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa','pausada','cancelada')),
    activada_en         TIMESTAMPTZ DEFAULT NOW(),
    activa_hasta        TIMESTAMPTZ,          -- NULL = sin vencimiento (admin gestiona)
    cadenas_focus       TEXT[],               -- arr de nombres de cadenas que monitorea (vacío = todas)
    notas_admin         TEXT,
    creado_en           TIMESTAMPTZ DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_empresas_dueno ON empresas(id_usuario_dueno);
CREATE INDEX IF NOT EXISTS idx_empresas_estado ON empresas(estado);

-- ── 2. Usuarios con acceso a una empresa (multi-user para Pro/Premium) ───────
CREATE TABLE IF NOT EXISTS empresa_usuarios (
    id_empresa  UUID REFERENCES empresas(id_empresa) ON DELETE CASCADE,
    id_usuario  UUID REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    rol         TEXT NOT NULL DEFAULT 'viewer' CHECK (rol IN ('owner','admin','viewer')),
    agregado_en TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id_empresa, id_usuario)
);

-- ── 3. Solicitudes de acceso B2B (form público "Solicitar acceso") ───────────
CREATE TABLE IF NOT EXISTS solicitudes_b2b (
    id_solicitud      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre_comercial  TEXT NOT NULL,
    rif               TEXT,
    sector            TEXT,
    contacto_nombre   TEXT NOT NULL,
    contacto_email    TEXT NOT NULL,
    contacto_telefono TEXT,
    plan_interes      TEXT CHECK (plan_interes IN ('basico','pro','premium','no_seguro')),
    mensaje           TEXT,
    estado            TEXT NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente','contactado','activada','descartada')),
    id_empresa_creada UUID REFERENCES empresas(id_empresa) ON DELETE SET NULL,
    notas_admin       TEXT,
    creado_en         TIMESTAMPTZ DEFAULT NOW(),
    atendida_en       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes_b2b(estado, creado_en DESC);

-- ── 4. Enriquecer consultas_usuarios para BI agregada ────────────────────────
-- Necesario para que el dashboard B2B muestre "rubros más comparados" y
-- "cadenas más mencionadas" sin re-parsear el texto cada vez.
ALTER TABLE consultas_usuarios
    ADD COLUMN IF NOT EXISTS rubro_detectado  TEXT,
    ADD COLUMN IF NOT EXISTS cadena_mencionada TEXT,
    ADD COLUMN IF NOT EXISTS enriquecida_en   TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_consultas_rubro ON consultas_usuarios(rubro_detectado, fecha_consulta DESC);
CREATE INDEX IF NOT EXISTS idx_consultas_cadena ON consultas_usuarios(cadena_mencionada, fecha_consulta DESC);

-- ── 5. Tracking de clicks hacia cadenas (visibilidad digital) ────────────────
CREATE TABLE IF NOT EXISTS clicks_cadena (
    id_click       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario     UUID REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_cadena      UUID REFERENCES cadenas_comerciales(id_cadena) ON DELETE CASCADE,
    tipo_destino   TEXT CHECK (tipo_destino IN ('web','whatsapp','resultado','otros')),
    canal_origen   TEXT CHECK (canal_origen IN ('WEB_APP','WHATSAPP','API')),
    ip             INET,
    ciudad_estimada TEXT,
    creado_en      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clicks_cadena_fecha ON clicks_cadena(id_cadena, creado_en DESC);

COMMIT;
