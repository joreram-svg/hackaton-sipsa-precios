# Migración de sipsa-data a Supabase (Postgres) — Brief autónomo

Ejecutor: Codex. Este documento es autónomo (no tienes historial de conversación previo).

## Contexto ya resuelto (no lo repitas)
- Proyecto Supabase creado ("Baskio"). Conexión verificada con `psycopg2` vía **Session Pooler** (la conexión directa `db.*.supabase.co` es IPv6-only y no resuelve en esta red).
- El connection string ya está en `sipsa-data/.env` como `SUPABASE_DB_URL` (formato `postgresql://postgres.<ref>:<password>@aws-0-us-east-2.pooler.supabase.com:5432/postgres`). Léelo de `.env`/`os.environ`. **No lo hardcodees ni lo imprimas/loguees.**
- `psycopg2-binary` ya está instalado en el entorno Python del sistema.
- Datos reales ya descargados del webservice SOAP oficial de SIPSA y guardados en:
  - `sipsa-data/data/raw/sipsa_precios_ciudad_real_2020_2026.csv` — columnas `fecha,ciudad,cod_producto,producto,precio_kg` — 383.718 filas, fechas 2020-02-03 a 2026-09-11, **todas las ciudades de Colombia** (no solo las 3 configuradas: Bogotá/Medellín/Cali). Ciudades vienen en MAYÚSCULAS (ej "BOGOTÁ, D.C.", "MEDELLÍN", "CALI") — normalízalas igual que a los productos.
  - `sipsa-data/data/raw/sipsa_abastecimiento_real.csv` — columnas `fecha,ciudad_fuente,producto,toneladas` — 164.274 filas.

## Tareas (en orden)

1. Lee `sipsa-data/README.md` y el código actual en `sipsa-data/src/sipsa/db/` (`schema.sql`, `views.sql`, `repo.py`) y `sipsa-data/src/sipsa/config.py` para entender el diseño (esquema `fecha/producto/precio/ciudad`, sin dimensión mercado).

2. Crea `sipsa-data/src/sipsa/db/schema_postgres.sql` adaptando `schema.sql` a Postgres. Aplícalo al Supabase real usando `SUPABASE_DB_URL`.

3. Backend intercambiable: variable de entorno `DB_BACKEND=duckdb|postgres` (default `duckdb`, para no romper nada existente) que controla si `repo.py` habla con DuckDB o Postgres. Factoriza el SQL compartido si es prácticamente idéntico; documenta diferencias de dialecto si las hay.

4. Escribe `sipsa-data/scripts/load_real_data_to_supabase.py`:
   - Lee los dos CSV reales.
   - Normaliza ciudad (mapea a las 3 configuradas donde aplique, pero **conserva TODAS las ciudades del CSV** — expandir `CIUDADES` en `.env`/`config.py` si hace falta, documentándolo).
   - Mapea producto → `producto_id` reutilizando `normalize.py`; no mapeados van a `unmapped.csv` sin romper la carga.
   - Carga a `fact_precio` (upsert, PK `fecha,producto_id,ciudad`) y a `fact_abastecimiento` (agregando `ciudad_fuente`).
   - Idempotente (reejecutar no duplica).
   - Reporta filas insertadas, no mapeados, rango de fechas, ciudades distintas.

5. Implementa/corrige `sipsa-data/src/sipsa/sources/soap_dane.py` con `zeep`. Endpoint `https://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService`, SOAP 1.2. Operaciones confirmadas funcionando (probadas por el arquitecto, HTTP 200, reales):
   - `client.service.promediosSipsaCiudad()` — sin parámetros, devuelve TODO el histórico (~383k filas, ~112MB, ~25s). Campos: `ciudad, producto, precioPromedio, fechaCaptura, codProducto, regId`.
   - `client.service.promedioAbasSipsaMesMadr()` — sin parámetros, histórico de abastecimiento (~164k filas, ~40s). Campos: `artiId, artiNombre, cantidadTon, fechaMesIni, fuenNombre, futiId` (nota: `enviado`, `fechaCreacion`, `tmpAbasMesId` NO vienen en la respuesta real pese a estar en el WSDL como opcionales — no asumas que siempre están).
   - Como cada llamada trae TODO el histórico sin filtro, filtra en el cliente por fecha nueva desde `ingest_log` antes de upsert; no llames esto en cada ingesta trivial (cachear/limitar a 1x/día, ya que el scheduler corre diario).
   - Si en tu entorno el WSDL o la llamada SOAP no son alcanzables por restricción de red/proxy, documéntalo explícitamente como bloqueo de entorno (no bug) — ya está confirmado que el servicio es accesible desde una red normal, y los CSV ya cargados cubren el arranque real.

6. Verificación: `pytest tests/ -q` (no debe romper el modo DuckDB por defecto) + verificación manual contra Postgres: cuenta filas en `fact_precio`/`fact_abastecimiento`, confirma `SELECT DISTINCT ciudad FROM fact_precio` tiene más de 3 valores.

7. Actualiza `sipsa-data/README.md` con sección "Base de datos compartida (Supabase)": cómo un compañero de equipo accede (Table Editor del dashboard, o `SUPABASE_DB_URL` propio en su `.env`), cómo correr `DB_BACKEND=postgres` localmente, cómo re-ejecutar la carga de datos reales.

No hagas commit ni push. Al terminar, reporta en texto plano: filas cargadas por tabla, rango de fechas, ciudades distintas cargadas, estado de tests, y si el adaptador SOAP en vivo funcionó o quedó documentado como bloqueado por red en tu entorno.
