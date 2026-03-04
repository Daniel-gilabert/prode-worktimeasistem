-- Añadir campos nuevos a la tabla servicios
-- Ejecutar en: Supabase → SQL Editor → New query → RUN

ALTER TABLE servicios
  ADD COLUMN IF NOT EXISTS tipo_servicio        VARCHAR(30),
  ADD COLUMN IF NOT EXISTS fecha_inicio_contrato DATE,
  ADD COLUMN IF NOT EXISTS fecha_fin_contrato    DATE,
  ADD COLUMN IF NOT EXISTS dias_servicio         VARCHAR(50),
  ADD COLUMN IF NOT EXISTS horario_inicio        VARCHAR(10),
  ADD COLUMN IF NOT EXISTS horario_fin           VARCHAR(10),
  -- Empresa cliente
  ADD COLUMN IF NOT EXISTS empresa_nombre        VARCHAR(200),
  ADD COLUMN IF NOT EXISTS empresa_cif           VARCHAR(20),
  ADD COLUMN IF NOT EXISTS empresa_direccion     VARCHAR(300),
  ADD COLUMN IF NOT EXISTS empresa_cp            VARCHAR(10),
  ADD COLUMN IF NOT EXISTS empresa_ciudad        VARCHAR(100),
  ADD COLUMN IF NOT EXISTS empresa_provincia     VARCHAR(100),
  ADD COLUMN IF NOT EXISTS empresa_pais          VARCHAR(50) DEFAULT 'España',
  -- Contacto principal
  ADD COLUMN IF NOT EXISTS contacto_nombre       VARCHAR(150),
  ADD COLUMN IF NOT EXISTS contacto_cargo        VARCHAR(100),
  ADD COLUMN IF NOT EXISTS contacto_email        VARCHAR(150),
  ADD COLUMN IF NOT EXISTS contacto_telefono     VARCHAR(20),
  ADD COLUMN IF NOT EXISTS contacto_movil        VARCHAR(20),
  -- Contacto secundario
  ADD COLUMN IF NOT EXISTS contacto2_nombre      VARCHAR(150),
  ADD COLUMN IF NOT EXISTS contacto2_email       VARCHAR(150),
  ADD COLUMN IF NOT EXISTS contacto2_telefono    VARCHAR(20),
  -- Facturación
  ADD COLUMN IF NOT EXISTS facturacion_email     VARCHAR(150),
  ADD COLUMN IF NOT EXISTS facturacion_forma_pago VARCHAR(100),
  ADD COLUMN IF NOT EXISTS tarifa_mensual        NUMERIC(10,2),
  -- Notas
  ADD COLUMN IF NOT EXISTS observaciones         TEXT;
