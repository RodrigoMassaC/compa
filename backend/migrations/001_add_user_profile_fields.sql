-- ============================================================
-- Migración 001: Campos de perfil de usuario
-- Agrega fecha_nacimiento, sexo, ciudad, estado_ven a usuarios
-- Ejecutar UNA sola vez en DB existente.
-- ============================================================

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE,
    ADD COLUMN IF NOT EXISTS sexo             VARCHAR(10)
        CHECK (sexo IN ('M', 'F', 'OTRO')),
    ADD COLUMN IF NOT EXISTS ciudad           VARCHAR(100),
    ADD COLUMN IF NOT EXISTS estado_ven       VARCHAR(100);

-- Comentarios descriptivos
COMMENT ON COLUMN usuarios.fecha_nacimiento IS 'Fecha de nacimiento — calculamos la edad dinámicamente';
COMMENT ON COLUMN usuarios.sexo             IS 'Género del usuario: M / F / OTRO';
COMMENT ON COLUMN usuarios.ciudad           IS 'Ciudad de residencia (ej: Maracay, Caracas)';
COMMENT ON COLUMN usuarios.estado_ven       IS 'Estado venezolano de residencia (ej: Aragua, Miranda)';

SELECT 'Migración 001 aplicada correctamente ✓' AS resultado;
