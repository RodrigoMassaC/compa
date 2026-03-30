-- ============================================================
-- Migración 002 — Listas de compras
-- Ejecutar: docker exec compa-db psql -U compa_user -d compa_dev -f /migrations/002_listas_compras.sql
-- ============================================================

-- Tabla de listas de compras (encabezado)
CREATE TABLE IF NOT EXISTS listas_compras (
    id_lista        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_usuario      UUID NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    nombre          VARCHAR(100) NOT NULL DEFAULT 'Mi lista',
    creado_en       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    actualizado_en  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listas_usuario ON listas_compras(id_usuario);

-- Tabla de ítems de cada lista
CREATE TABLE IF NOT EXISTS items_lista (
    id_item             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_lista            UUID NOT NULL REFERENCES listas_compras(id_lista) ON DELETE CASCADE,
    nombre_item         VARCHAR(200) NOT NULL,          -- texto libre del usuario
    id_producto_maestro UUID REFERENCES productos_maestros(id_producto_maestro),  -- match opcional
    cantidad            INTEGER NOT NULL DEFAULT 1,
    creado_en           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_lista ON items_lista(id_lista);

-- Trigger para actualizar actualizado_en en listas_compras
CREATE OR REPLACE FUNCTION update_lista_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE listas_compras SET actualizado_en = NOW() WHERE id_lista = NEW.id_lista;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_items_update_lista ON items_lista;
CREATE TRIGGER trg_items_update_lista
    AFTER INSERT OR DELETE ON items_lista
    FOR EACH ROW EXECUTE FUNCTION update_lista_timestamp();

RAISE NOTICE '✅ Migración 002 aplicada: listas_compras + items_lista';

-- 003: términos y condiciones
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS terminos_aceptados_en TIMESTAMPTZ;
