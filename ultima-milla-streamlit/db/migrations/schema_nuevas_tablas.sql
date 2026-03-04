-- =============================================================
-- TABLAS NUEVAS para ultima-milla-manager
-- Ejecutar en: Supabase → SQL Editor → New query → RUN
--
-- La tabla "vehiculos" YA EXISTE con su estructura original.
-- Este script crea solo las tablas que faltan.
-- =============================================================

-- ---------------------------------------------------------------
-- EMPLEADOS / CONDUCTORES
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empleados (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    apellidos       VARCHAR(100) NOT NULL,
    dni             VARCHAR(20)  UNIQUE NOT NULL,
    telefono        VARCHAR(20),
    email           VARCHAR(100),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------
-- SERVICIOS (rutas permanentes)
-- Referencias a vehiculos usando el id de la tabla existente
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS servicios (
    id                  SERIAL PRIMARY KEY,
    codigo              VARCHAR(50)  UNIQUE NOT NULL,
    descripcion         VARCHAR(200) NOT NULL,
    zona                VARCHAR(100),
    empleado_base_id    INTEGER  NOT NULL REFERENCES empleados(id),
    vehiculo_base_id    INTEGER  NOT NULL REFERENCES vehiculos(id),
    activo              BOOLEAN  NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------
-- SUSTITUCIONES TEMPORALES
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sustituciones (
    id              SERIAL PRIMARY KEY,
    servicio_id     INTEGER NOT NULL REFERENCES servicios(id),
    tipo            VARCHAR(20) NOT NULL CHECK (tipo IN ('empleado', 'vehiculo')),
    empleado_id     INTEGER REFERENCES empleados(id),
    vehiculo_id     INTEGER REFERENCES vehiculos(id),
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE NOT NULL,
    motivo          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sust_ref CHECK (
        (tipo = 'empleado' AND empleado_id IS NOT NULL AND vehiculo_id IS NULL) OR
        (tipo = 'vehiculo' AND vehiculo_id IS NOT NULL AND empleado_id IS NULL)
    ),
    CONSTRAINT chk_sust_rango CHECK (fecha_fin >= fecha_inicio)
);

-- ---------------------------------------------------------------
-- AUSENCIAS DE EMPLEADOS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ausencias (
    id              SERIAL PRIMARY KEY,
    empleado_id     INTEGER NOT NULL REFERENCES empleados(id),
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE NOT NULL,
    tipo            VARCHAR(50) NOT NULL,
    observaciones   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_aus_rango CHECK (fecha_fin >= fecha_inicio)
);

-- ---------------------------------------------------------------
-- INCIDENCIAS DE VEHÍCULOS
-- Referencia a vehiculos.id (tabla existente)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidencias (
    id              SERIAL PRIMARY KEY,
    vehiculo_id     INTEGER NOT NULL REFERENCES vehiculos(id),
    gravedad        VARCHAR(20) NOT NULL CHECK (gravedad IN ('leve', 'grave')),
    descripcion     TEXT NOT NULL,
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE,   -- NULL = incidencia abierta
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_inc_rango CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

-- ---------------------------------------------------------------
-- Índices para búsqueda rápida por fecha
-- ---------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sust_srv_fecha  ON sustituciones (servicio_id, fecha_inicio, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_aus_emp_fecha   ON ausencias     (empleado_id,  fecha_inicio, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_inc_veh_fecha   ON incidencias   (vehiculo_id,  fecha_inicio);
