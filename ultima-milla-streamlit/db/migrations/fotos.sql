-- =============================================================
-- FOTOS: columnas en tablas + bucket en Storage
-- Ejecutar en Supabase → SQL Editor → New query → RUN
-- =============================================================

-- Añadir columna foto a empleados
ALTER TABLE empleados
  ADD COLUMN IF NOT EXISTS foto_url TEXT;

-- Tabla para fotos de marcas de vehículos
CREATE TABLE IF NOT EXISTS marcas_vehiculos (
    id          SERIAL PRIMARY KEY,
    marca       VARCHAR(50) UNIQUE NOT NULL,
    foto_url    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insertar las 3 marcas
INSERT INTO marcas_vehiculos (marca) VALUES
  ('Renault'),
  ('Paxtser'),
  ('Scoobic')
ON CONFLICT (marca) DO NOTHING;

-- =============================================================
-- BUCKET DE STORAGE
-- Crear manualmente en: Supabase → Storage → New bucket
--   Nombre: fotos-app
--   Public bucket: SÍ (activar el toggle)
-- =============================================================

-- Políticas de acceso al bucket fotos-app
-- (ejecutar después de crear el bucket manualmente en Supabase → Storage)

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename  = 'objects'
      AND policyname = 'Acceso público lectura fotos'
  ) THEN
    EXECUTE 'CREATE POLICY "Acceso público lectura fotos"
      ON storage.objects FOR SELECT
      USING (bucket_id = ''fotos-app'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename  = 'objects'
      AND policyname = 'Subida autenticada fotos'
  ) THEN
    EXECUTE 'CREATE POLICY "Subida autenticada fotos"
      ON storage.objects FOR INSERT
      WITH CHECK (bucket_id = ''fotos-app'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename  = 'objects'
      AND policyname = 'Actualizar fotos'
  ) THEN
    EXECUTE 'CREATE POLICY "Actualizar fotos"
      ON storage.objects FOR UPDATE
      USING (bucket_id = ''fotos-app'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename  = 'objects'
      AND policyname = 'Borrar fotos'
  ) THEN
    EXECUTE 'CREATE POLICY "Borrar fotos"
      ON storage.objects FOR DELETE
      USING (bucket_id = ''fotos-app'')';
  END IF;
END $$;
