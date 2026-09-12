CREATE TABLE IF NOT EXISTS dim_producto (
  producto_id VARCHAR PRIMARY KEY,
  nombre VARCHAR NOT NULL,
  categoria VARCHAR NOT NULL,
  unidad_base VARCHAR NOT NULL DEFAULT 'kg',
  alias JSON
);
CREATE TABLE IF NOT EXISTS fact_precio (
  fecha DATE NOT NULL,
  producto_id VARCHAR NOT NULL,
  ciudad VARCHAR NOT NULL,
  precio DOUBLE NOT NULL,
  fuente VARCHAR NOT NULL,
  ingested_at TIMESTAMP DEFAULT now(),
  PRIMARY KEY (fecha, producto_id, ciudad)
);
CREATE TABLE IF NOT EXISTS fact_abastecimiento (
  fecha DATE NOT NULL,
  producto_id VARCHAR NOT NULL,
  ciudad VARCHAR NOT NULL,
  toneladas DOUBLE NOT NULL,
  fuente VARCHAR NOT NULL,
  PRIMARY KEY (fecha, producto_id, ciudad)
);
CREATE TABLE IF NOT EXISTS ingest_log (
  run_id VARCHAR PRIMARY KEY,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  fuente VARCHAR,
  filas_insertadas INT,
  filas_actualizadas INT,
  semanas_min DATE,
  semanas_max DATE,
  status VARCHAR,
  error VARCHAR
);
