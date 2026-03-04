-- =============================================================
-- DOCUMENTOS POR SERVICIO
-- Ejecutar en: Supabase → SQL Editor → New query → RUN
-- =============================================================

CREATE TABLE IF NOT EXISTS documentos_servicio (
    id              SERIAL PRIMARY KEY,
    servicio_id     INTEGER      NOT NULL REFERENCES servicios(id) ON DELETE CASCADE,
    nombre          VARCHAR(200) NOT NULL,           -- nombre visible del documento
    nombre_archivo  VARCHAR(300) NOT NULL,           -- nombre real en Storage
    tipo            VARCHAR(50)  NOT NULL,           -- contrato / seguro / permiso / factura / otro
    descripcion     TEXT,
    storage_path    TEXT         NOT NULL,           -- ruta en bucket docs-servicios
    url_publica     TEXT,                            -- URL de descarga directa
    subido_por      VARCHAR(100),
    fecha_subida    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docs_servicio ON documentos_servicio (servicio_id);

-- =============================================================
-- BUCKET DE STORAGE PARA DOCUMENTOS
-- Crear manualmente en: Supabase → Storage → New bucket
--   Nombre:         docs-servicios
--   Public bucket:  SÍ (activar toggle)
-- =============================================================
