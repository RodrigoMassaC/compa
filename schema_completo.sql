-- ============================================================
-- COMPA — Schema completo de base de datos v2.1
-- Motor: PostgreSQL 15+ con extensiones PostGIS y pg_trgm
-- Ejecutar con: scripts/init_db.py
-- ============================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- MÓDULO 1: CATÁLOGOS
-- ============================================================

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre             VARCHAR(100) NOT NULL,
    descripcion        TEXT,
    id_categoria_padre UUID REFERENCES categorias(id_categoria) ON DELETE SET NULL,
    nivel              INTEGER NOT NULL DEFAULT 1,
    activo             BOOLEAN DEFAULT TRUE,
    creado_en          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_categorias_padre ON categorias(id_categoria_padre);

CREATE TABLE IF NOT EXISTS productos_maestros (
    id_producto_maestro UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_categoria        UUID    REFERENCES categorias(id_categoria) ON DELETE RESTRICT,
    nombre_estandar     VARCHAR(255) NOT NULL,
    marca               VARCHAR(100),
    presentacion        VARCHAR(50),
    unidad_medida       VARCHAR(20),
    codigo_barras       VARCHAR(50) UNIQUE,
    terminos_busqueda   TEXT,
    imagen_url          VARCHAR(500),
    activo              BOOLEAN DEFAULT TRUE,
    creado_en           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pm_nombre   ON productos_maestros USING GIN (nombre_estandar gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pm_terminos ON productos_maestros USING GIN (terminos_busqueda gin_trgm_ops);

-- ============================================================
-- MÓDULO 2: RED COMERCIAL Y GEOLOCALIZACIÓN
-- ============================================================

CREATE TABLE IF NOT EXISTS cadenas_comerciales (
    id_cadena     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre_cadena VARCHAR(150) NOT NULL UNIQUE,
    tipo_comercio VARCHAR(50) CHECK (tipo_comercio IN ('SUPERMERCADO','FARMACIA','CONVENIENCIA','ABASTO')),
    logo_url      VARCHAR(500),
    sitio_web     VARCHAR(255),
    activo        BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS establecimientos (
    id_establecimiento UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_cadena          UUID REFERENCES cadenas_comerciales(id_cadena) ON DELETE CASCADE,
    nombre_sucursal    VARCHAR(150) NOT NULL,
    direccion_completa TEXT,
    estado             VARCHAR(50),
    ciudad             VARCHAR(50),
    zona_barrio        VARCHAR(100),
    ubicacion          GEOMETRY(Point, 4326) NOT NULL,
    horario_apertura   TIME,
    horario_cierre     TIME,
    abierto_24h        BOOLEAN DEFAULT FALSE,
    activo             BOOLEAN DEFAULT TRUE,
    creado_en          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_cadena, nombre_sucursal)
);
CREATE INDEX IF NOT EXISTS idx_establecimientos_ubicacion ON establecimientos USING GIST (ubicacion);

-- ============================================================
-- MÓDULO 3: MOTOR DE DATOS
-- ============================================================

CREATE TABLE IF NOT EXISTS productos_crudos (
    id_producto_crudo   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_establecimiento  UUID REFERENCES establecimientos(id_establecimiento) ON DELETE CASCADE,
    id_producto_maestro UUID REFERENCES productos_maestros(id_producto_maestro) ON DELETE SET NULL,
    nombre_original     VARCHAR(255) NOT NULL,
    sku_comercio        VARCHAR(100),
    url_origen          VARCHAR(1000),
    estado_mapeo        VARCHAR(20) DEFAULT 'PENDIENTE'
                        CHECK (estado_mapeo IN ('PENDIENTE','MAPEA_OK','REQUIERE_HUMANO','DESCARTADO')),
    creado_en           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_establecimiento, sku_comercio)
);
CREATE INDEX IF NOT EXISTS idx_crudos_maestro ON productos_crudos(id_producto_maestro);
CREATE INDEX IF NOT EXISTS idx_crudos_estado  ON productos_crudos(estado_mapeo);

CREATE TABLE IF NOT EXISTS historico_tasa_bcv (
    fecha     DATE PRIMARY KEY,
    valor_usd DECIMAL(12, 4) NOT NULL,
    fuente    VARCHAR(50) DEFAULT 'BCV',
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historial_precios (
    id_precio         BIGSERIAL PRIMARY KEY,
    id_producto_crudo UUID REFERENCES productos_crudos(id_producto_crudo) ON DELETE CASCADE,
    precio_bruto      DECIMAL(15, 2) NOT NULL,
    moneda_origen     VARCHAR(3) CHECK (moneda_origen IN ('VES','USD')) NOT NULL,
    es_promocion      BOOLEAN DEFAULT FALSE,
    fuente_datos      VARCHAR(20) CHECK (fuente_datos IN ('SCRAPING_WEB','CROWDSOURCING_APP','API_INTEGRACION')) NOT NULL,
    fecha_lectura     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_precios_crudo_fecha ON historial_precios(id_producto_crudo, fecha_lectura DESC);
CREATE INDEX IF NOT EXISTS idx_precios_fecha       ON historial_precios(fecha_lectura DESC);

CREATE TABLE IF NOT EXISTS auditoria_crowdsourcing (
    id_auditoria          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_precio             BIGINT REFERENCES historial_precios(id_precio) ON DELETE CASCADE,
    id_usuario_recolector UUID,
    imagen_evidencia_url  VARCHAR(1000) NOT NULL,
    ocr_texto_extraido    TEXT,
    ocr_confianza         DECIMAL(5, 2),
    estado_validacion     VARCHAR(20) DEFAULT 'PENDIENTE'
                          CHECK (estado_validacion IN ('PENDIENTE','APROBADO_IA','RECHAZADO_IA','REVISION_MANUAL')),
    creado_en             TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rutas_recolectores (
    id_ruta               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario_admin      UUID NOT NULL,
    id_usuario_recolector UUID NOT NULL,
    nombre_ruta           VARCHAR(150) NOT NULL,
    fecha_asignacion      DATE NOT NULL,
    fecha_completado      DATE,
    estado                VARCHAR(20) DEFAULT 'ASIGNADA'
                          CHECK (estado IN ('ASIGNADA','EN_PROGRESO','COMPLETADA','CANCELADA')),
    establecimientos_ids  UUID[],
    notas_admin           TEXT,
    creado_en             TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rutas_recolector ON rutas_recolectores(id_usuario_recolector, fecha_asignacion DESC);

-- ============================================================
-- MÓDULO 4: USUARIOS Y MEMBRESÍAS
-- ============================================================

CREATE TABLE IF NOT EXISTS planes_membresia (
    id_plan                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_plan              VARCHAR(50) UNIQUE NOT NULL,
    nombre_comercial         VARCHAR(100) NOT NULL,
    descripcion              TEXT,
    precio_mensual_usd       DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    precio_anual_usd         DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    limite_consultas_wa_mes  INTEGER DEFAULT 50,
    limite_consultas_web_mes INTEGER DEFAULT 200,
    acceso_historico_meses   INTEGER DEFAULT 1,
    exportar_excel           BOOLEAN DEFAULT FALSE,
    soporte_prioritario      BOOLEAN DEFAULT FALSE,
    activo                   BOOLEAN DEFAULT TRUE
);

INSERT INTO planes_membresia
    (codigo_plan, nombre_comercial, precio_mensual_usd, precio_anual_usd,
     limite_consultas_wa_mes, limite_consultas_web_mes, acceso_historico_meses)
VALUES
    ('FREE',       'Gratuito',   0.00,   0.00,  50,    200,   1),
    ('BASIC',      'Básico',     9.99,  99.00,  200,   1000,  3),
    ('PRO',        'Pro',       29.99, 299.00,  1000,  5000,  12),
    ('ENTERPRISE', 'Enterprise',99.99, 999.00,  99999, 99999, 99)
ON CONFLICT (codigo_plan) DO NOTHING;

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rol_usuario           VARCHAR(20) DEFAULT 'CONSUMIDOR'
                          CHECK (rol_usuario IN ('CONSUMIDOR','B2B_EMPRESA','RECOLECTOR_DATA','ADMIN')),
    telefono_wa           VARCHAR(20) UNIQUE,
    email                 VARCHAR(150) UNIQUE,
    password_hash         VARCHAR(255),
    nombre_completo       VARCHAR(150),
    nombre_empresa        VARCHAR(150),
    id_plan_actual        UUID REFERENCES planes_membresia(id_plan) ON DELETE RESTRICT,
    estado_suscripcion    VARCHAR(20) DEFAULT 'ACTIVA'
                          CHECK (estado_suscripcion IN ('ACTIVA','VENCIDA','CANCELADA','PRUEBA')),
    fecha_fin_suscripcion TIMESTAMP WITH TIME ZONE,
    ubicacion_default     GEOMETRY(Point, 4326),
    creado_en             TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ultimo_login          TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_usuarios_wa ON usuarios(telefono_wa);

CREATE TABLE IF NOT EXISTS sesiones_agente (
    id_sesion      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario     UUID REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    canal_origen   VARCHAR(20) CHECK (canal_origen IN ('WHATSAPP','WEB_APP','API')),
    historial_json JSONB NOT NULL DEFAULT '[]',
    ultimo_mensaje TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expira_en      TIMESTAMP WITH TIME ZONE,
    activa         BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones_agente(id_usuario, ultimo_mensaje DESC);

CREATE TABLE IF NOT EXISTS consultas_usuarios (
    id_consulta             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario              UUID REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    texto_consulta_original TEXT NOT NULL,
    tipo_consulta           VARCHAR(20) CHECK (tipo_consulta IN ('PRODUCTO_UNICO','CARRITO_MULTIPLE')),
    canal_origen            VARCHAR(20) CHECK (canal_origen IN ('WHATSAPP','WEB_APP','API')),
    ubicacion_consulta      GEOMETRY(Point, 4326),
    tokens_ia_consumidos    INTEGER DEFAULT 0,
    fecha_consulta          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_consultas_usuario_fecha ON consultas_usuarios(id_usuario, fecha_consulta DESC);
CREATE INDEX IF NOT EXISTS idx_consultas_ubicacion     ON consultas_usuarios USING GIST (ubicacion_consulta);

CREATE TABLE IF NOT EXISTS transacciones_pago (
    id_transaccion  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario      UUID REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    id_plan         UUID REFERENCES planes_membresia(id_plan),
    monto_usd       DECIMAL(10, 2) NOT NULL,
    metodo_pago     VARCHAR(50),
    referencia_pago VARCHAR(150) UNIQUE,
    estado_pago     VARCHAR(20) CHECK (estado_pago IN ('PENDIENTE','COMPLETADO','FALLIDO','REEMBOLSADO')),
    fecha_pago      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- VISTA MAESTRA — Precios actuales con conversión BCV al vuelo
-- ============================================================

CREATE OR REPLACE VIEW vista_precios_actuales AS
SELECT DISTINCT ON (c.id_producto_crudo)
    m.id_producto_maestro,
    m.nombre_estandar,
    m.presentacion,
    e.id_establecimiento,
    e.nombre_sucursal,
    e.ubicacion AS ubicacion_local,
    cad.nombre_cadena,
    cad.tipo_comercio,
    p.precio_bruto,
    p.moneda_origen,
    CASE
        WHEN p.moneda_origen = 'USD' THEN p.precio_bruto
        ELSE ROUND(p.precio_bruto /
             NULLIF((SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1), 0), 2)
    END AS precio_usd,
    CASE
        WHEN p.moneda_origen = 'VES' THEN p.precio_bruto
        ELSE ROUND(p.precio_bruto *
             (SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1), 2)
    END AS precio_ves,
    (SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1) AS tasa_bcv,
    p.es_promocion,
    p.fuente_datos,
    p.fecha_lectura
FROM historial_precios p
JOIN productos_crudos c      ON p.id_producto_crudo   = c.id_producto_crudo
JOIN productos_maestros m    ON c.id_producto_maestro = m.id_producto_maestro
JOIN establecimientos e      ON c.id_establecimiento  = e.id_establecimiento
JOIN cadenas_comerciales cad ON e.id_cadena            = cad.id_cadena
WHERE p.fecha_lectura >= NOW() - INTERVAL '7 days'
  AND c.estado_mapeo = 'MAPEA_OK'
ORDER BY c.id_producto_crudo, p.fecha_lectura DESC;

-- ============================================================
-- DATOS INICIALES DE DESARROLLO
-- ============================================================

INSERT INTO categorias (nombre, nivel) VALUES
    ('Alimentos', 1), ('Medicamentos', 1), ('Higiene', 1), ('Bebidas', 1)
ON CONFLICT DO NOTHING;

INSERT INTO cadenas_comerciales (nombre_cadena, tipo_comercio, sitio_web) VALUES
    ('Farmatodo',  'FARMACIA',      'https://farmatodo.com.ve'),
    ('Locatel',    'FARMACIA',      'https://locatel.com.ve'),
    ('Excelsior Gama', 'SUPERMERCADO', 'https://excelsiorgama.com')
ON CONFLICT (nombre_cadena) DO NOTHING;

SELECT 'Compa DB — Schema creado exitosamente ✓' AS resultado;
