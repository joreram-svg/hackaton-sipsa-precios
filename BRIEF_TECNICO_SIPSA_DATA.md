# BRIEF TÉCNICO — Capa de Datos SIPSA para Agente de Precios de Alimentos (Colombia)

Ejecutor: Codex. Tiempo total: 4 h. Este documento es autónomo.

## 0-A. ACTUALIZACIÓN (aprobada por el técnico) — Esquema simplificado

Cambio de alcance sobre este brief: **se elimina la dimensión `mercado`** (no habrá `dim_mercado` ni `mercado_id`). El dato queda a nivel de **`fecha, producto, precio, ciudad`** únicamente. Todo lo que en las secciones 4, 6 y 7 hace referencia a `mercado_id`/`dim_mercado`/`comparar_mercados` se reemplaza por `ciudad` directamente (ya no hay comparación entre mercados de una misma ciudad, sino entre ciudades). Concretamente:
- `fact_precio(fecha, producto_id, ciudad, precio, fuente, ingested_at)` — PK `(fecha, producto_id, ciudad)`. Se elimina `dim_mercado`, `mercado_id`, `precio_min`, `precio_max` (mantener solo `precio`, promedio semanal).
- Cualquier adaptador (`excel_dane`, `soap_dane`, `socrata`, `seed`) que produzca varios mercados por ciudad debe promediarlos antes de insertar (agregación a nivel ciudad).
- Endpoints y tools MCP: donde el contrato pida `mercado_id`, usar `ciudad` en su lugar; `GET /v1/mercados` y `comparar_mercados` se renombran a `GET /v1/ciudades` y `comparar_ciudades(producto_id) -> [{ciudad, precio_actual, var_1w_pct}]`.
- Vistas analíticas (`v_variacion`, `v_percentil`, `v_tendencia`) agrupan por `(producto_id, ciudad)` en vez de `(producto_id, mercado_id)`.
- El resto del brief (fórmulas de score, plan de 4h, criterios de aceptación) aplica igual, solo sustituyendo `mercado_id` por `ciudad`.

## 0. Objetivo
Construir el servicio `sipsa-data`: ingesta de precios mayoristas de alimentos del DANE (SIPSA), almacenamiento histórico, capa analítica y exposición vía REST + MCP para que otros agentes (consumidor / restaurante / mayorista) consuman señales de precio. Debe funcionar en demo aunque el DANE esté caído (modo `seed`).

## 1. Stack (fijo, no discutir)
- Python 3.11, gestor `uv` (fallback `pip`).
- Deps: `duckdb`, `pandas`, `pyarrow`, `httpx`, `openpyxl`, `fastapi`, `uvicorn`, `pydantic>=2`, `apscheduler`, `fastmcp`, `python-dotenv`, `zeep` (solo adaptador SOAP).
- Almacenamiento: DuckDB en `data/sipsa.duckdb` + Parquet crudo en `data/raw/`.
- Sin Docker en esta fase. Sin auth salvo `X-Admin-Token` en endpoints admin.

## 2. Estructura de directorios
```
sipsa-data/
  pyproject.toml
  .env.example
  README.md
  data/raw/            # parquet crudo, nunca se borra
  data/sipsa.duckdb
  data/snapshot/       # JSON precalculado para demo offline
  src/sipsa/
    __init__.py
    config.py          # Settings (pydantic-settings): DB_PATH, ADMIN_TOKEN, SOURCE_PRIORITY, CIUDADES, HIST_WEEKS
    catalog/
      productos.csv    # catálogo maestro (ver 4.3)
      mercados.csv
    sources/
      base.py          # interfaz SourceAdapter
      excel_dane.py    # adaptador 1
      soap_dane.py     # adaptador 2
      socrata.py       # adaptador 3
      seed.py          # adaptador 4: datos sintéticos realistas
    ingest/
      pipeline.py      # run_ingest(): fetch -> normalize -> upsert -> log
      normalize.py     # mapeo nombres -> producto_id, unidades -> kg
    db/
      schema.sql
      views.sql
      repo.py          # funciones de consulta tipadas
    analytics/
      signals.py       # variaciones, percentil, score, señal
      forecast.py      # pronóstico simple
    api/
      main.py          # FastAPI
      models.py        # Pydantic response models
    mcp/
      server.py        # fastmcp, mismas funciones que la API
    scheduler.py       # apscheduler: ingest diario 06:00 America/Bogota
  scripts/
    bootstrap.py       # crea DB, carga catálogo, ingesta histórica (o seed), genera snapshot
    make_snapshot.py
  tests/
    test_normalize.py
    test_signals.py
    test_api_smoke.py
```

## 3. Fuentes de datos (orden de prioridad; el pipeline usa la primera que responda)

| # | Adaptador | Detalle | Verificar |
|---|---|---|---|
| 1 | `excel_dane` | Anexos semanales SIPSA "Precios mayoristas" (xlsx) publicados en la página SIPSA del DANE (dane.gov.co -> Estadísticas por tema -> Agropecuario -> SIPSA). Descargar los anexos históricos disponibles (semanal, boletín). | Descubrir URL real de los anexos con `httpx` + regex sobre el HTML de la página SIPSA. Guardar URL encontrada en `data/raw/sources.json`. |
| 2 | `soap_dane` | WSDL `https://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService?WSDL`. Métodos esperados: `promediosSipsaSemanaMadr` (precio promedio semanal producto x mercado), `promediosSipsaCiudad`, `promediosSipsaParcial`, `promedioAbasSipsaMesMadr` (abastecimiento). | Inspeccionar WSDL con `zeep` y adaptar nombres reales. Timeout 30 s. |
| 3 | `socrata` | `https://www.datos.gov.co/resource/<DATASET_ID>.json` (buscar dataset "SIPSA precios mayoristas"). Paginar con `$limit=50000&$offset`. | ID de dataset en `.env` (`SOCRATA_DATASET_ID`), vacío = deshabilitado. |
| 4 | `seed` | Genera 104 semanas sintéticas para el catálogo completo con estacionalidad senoidal + ruido + tendencias plausibles (papa, tomate, cebolla con ciclos marcados). Determinista (`seed=42`). | Siempre disponible. Marca `fuente='seed'`. |

Regla: si una fuente real devuelve menos de 4 semanas de datos, complementar con `seed` para las semanas faltantes y marcar `fuente` por fila. Nunca mezclar silenciosamente: el endpoint `/health` reporta `fuente_activa` y `pct_seed`.

### 3.1 Interfaz `SourceAdapter`
```python
class SourceAdapter(Protocol):
    name: str
    def available(self) -> bool: ...
    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame: ...   # columnas 4.1 RAW
    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None: ...
```

## 4. Modelo de datos

### 4.1 DataFrame RAW (salida de cualquier adaptador)
`fecha:date, producto_raw:str, mercado_raw:str, ciudad_raw:str, precio_prom:float, precio_min:float|null, precio_max:float|null, unidad_raw:str, fuente:str`

### 4.2 Esquema DuckDB (`schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS dim_producto (
  producto_id VARCHAR PRIMARY KEY,      -- slug: 'papa_pastusa'
  nombre VARCHAR NOT NULL,              -- 'Papa pastusa'
  categoria VARCHAR NOT NULL,           -- 'tuberculos'|'verduras'|'frutas'|'granos'|'procesados'|'carnes'|'lacteos'
  unidad_base VARCHAR NOT NULL DEFAULT 'kg',
  alias JSON                            -- lista de nombres SIPSA que mapean aquí
);
CREATE TABLE IF NOT EXISTS dim_mercado (
  mercado_id VARCHAR PRIMARY KEY,       -- 'bogota_corabastos'
  nombre VARCHAR NOT NULL,
  ciudad VARCHAR NOT NULL               -- 'Bogotá'
);
CREATE TABLE IF NOT EXISTS fact_precio (
  fecha DATE NOT NULL,                  -- lunes de la semana ISO
  producto_id VARCHAR NOT NULL,
  mercado_id VARCHAR NOT NULL,
  precio_prom DOUBLE NOT NULL,          -- COP por unidad_base
  precio_min DOUBLE,
  precio_max DOUBLE,
  fuente VARCHAR NOT NULL,
  ingested_at TIMESTAMP DEFAULT now(),
  PRIMARY KEY (fecha, producto_id, mercado_id)
);
CREATE TABLE IF NOT EXISTS fact_abastecimiento (
  fecha DATE NOT NULL, producto_id VARCHAR NOT NULL, ciudad VARCHAR NOT NULL,
  toneladas DOUBLE NOT NULL, fuente VARCHAR NOT NULL,
  PRIMARY KEY (fecha, producto_id, ciudad)
);
CREATE TABLE IF NOT EXISTS ingest_log (
  run_id VARCHAR PRIMARY KEY, started_at TIMESTAMP, finished_at TIMESTAMP,
  fuente VARCHAR, filas_insertadas INT, filas_actualizadas INT, semanas_min DATE, semanas_max DATE,
  status VARCHAR, error VARCHAR
);
```
Upsert: `INSERT ... ON CONFLICT (fecha, producto_id, mercado_id) DO UPDATE` (idempotente).

### 4.3 Catálogo maestro (`productos.csv`) — alcance mínimo 40 productos
Columnas: `producto_id,nombre,categoria,unidad_base,alias` (alias separados por `|`).
Obligatorios: papa_pastusa, papa_criolla, tomate_chonto, cebolla_cabezona, cebolla_larga, zanahoria, platano_harton, yuca, arroz, frijol, lenteja, aguacate, banano, limon_tahiti, naranja, mango, papaya, pina, mora, lulo, maracuya, lechuga, repollo, pimenton, habichuela, arveja, ahuyama, huevo, pollo, res, cerdo, panela, azucar, aceite, maiz, arracacha, coliflor, brocoli, espinaca, fresa.
Mercados mínimos: `bogota_corabastos`, `medellin_cma`, `cali_cavasa`, `barranquilla_granabastos`, `bucaramanga_centroabastos`.
Normalización: `normalize.py::match_producto(nombre_raw) -> producto_id | None` con: lower + strip acentos + match exacto en alias -> fallback `difflib.get_close_matches(cutoff=0.85)`. No mapeados -> `data/raw/unmapped.csv` (no rompen el pipeline).
Unidades: convertir todo a COP/kg. Tabla `UNIDAD_FACTOR = {"kg":1,"kilo":1,"lb":0.5,"libra":0.5,"arroba":12.5,"@":12.5,"bulto":50,"caja":None}` (caja usa factor propio por producto si existe); si no hay factor conocido, conservar y marcar `unidad_base` distinta en el producto.

## 5. Capa analítica (`views.sql` + `signals.py`)

Vistas (todas sobre `fact_precio`, granularidad semanal, ventana histórica `HIST_WEEKS=104`):
- `v_ultima_semana`: última `fecha` por mercado.
- `v_variacion`: por (producto, mercado): `precio_actual, precio_1w, precio_4w, precio_52w, var_1w_pct, var_4w_pct, var_52w_pct`.
- `v_percentil`: `percentil_hist` = rank percentil del precio actual dentro de las últimas 104 semanas (0 = el más barato de la historia, 1 = el más caro).
- `v_tendencia`: pendiente de regresión lineal sobre las últimas 8 semanas, normalizada (`pendiente_pct_sem`).

Score de oportunidad (0–100, mayor = mejor momento para comprar):
```
base = 0.45*(1 - percentil_hist) + 0.35*(0.5 + clip(-var_4w_pct/0.30, -1, 1)/2) + 0.20*(0.5 + clip(-var_1w_pct/0.15, -1, 1)/2)
score = 100 * clip(base, 0, 1)
senal = 'COMPRAR' if score >= 65 else 'EVITAR' if score <= 35 else 'NEUTRAL'
```
Perfil (multiplica los tres pesos 0.45/0.35/0.20, no cambia la fórmula, luego renormaliza a suma 1):
- `consumidor`: peso var_1w x1.5
- `restaurante`: peso var_4w x1.5
- `mayorista`: peso percentil x1.5, además usa `forecast()` para la razón.

Pronóstico (`forecast.py`): `forecast(producto_id, mercado_id, horizonte_semanas in [1..4])` = 0.6*media móvil 4 sem + 0.4*precio de la misma semana del año anterior ajustado por `var_52w`. Devuelve `precio_esperado, banda_inf, banda_sup` (± 1 desvío estándar de las últimas 12 semanas). Sin ML. Marcar `metodo='ma4+estacional'`.

## 6. Contrato REST (FastAPI, prefijo `/v1`, JSON, `Content-Type: application/json`)

Convención de error: `{ "error": {"code": "NOT_FOUND|BAD_REQUEST|UPSTREAM_DOWN", "message": str} }`.
Fechas ISO `YYYY-MM-DD`. Precios en COP/kg (float, 2 decimales). Ciudad por defecto: `Bogotá`.

| Método | Ruta | Query | Respuesta |
|---|---|---|---|
| GET | `/v1/health` | — | `{status, fuente_activa, ultima_fecha, semanas_disponibles, pct_seed, productos, mercados}` |
| GET | `/v1/productos` | `categoria?` | `[{producto_id, nombre, categoria, unidad_base}]` |
| GET | `/v1/mercados` | `ciudad?` | `[{mercado_id, nombre, ciudad}]` |
| GET | `/v1/precios` | `producto_id*, mercado_id?, desde?, hasta?` | `{producto_id, mercado_id, unidad:'COP/kg', serie:[{fecha, precio_prom, precio_min, precio_max, fuente}]}` |
| GET | `/v1/oportunidades` | `ciudad?, categoria?, perfil?=consumidor\|restaurante\|mayorista, top?=10` | `{fecha, ciudad, perfil, items:[OportunidadItem]}` ordenado por `score` desc |
| GET | `/v1/evitar` | igual a oportunidades | mismos items ordenados por `score` asc |
| GET | `/v1/tendencia/{producto_id}` | `mercado_id?, semanas?=12` | `{producto_id, mercado_id, serie:[{fecha, precio_prom}], var_1w_pct, var_4w_pct, var_52w_pct, percentil_hist, pendiente_pct_sem}` |
| GET | `/v1/forecast/{producto_id}` | `mercado_id?, horizonte?=2` | `{producto_id, mercado_id, horizonte_semanas, precio_actual, precio_esperado, banda_inf, banda_sup, var_esperada_pct, metodo}` |
| GET | `/v1/alertas` | `ciudad?, umbral_pct?=15, ventana?=1w\|4w` | `{fecha, alertas:[{producto_id, nombre, mercado_id, var_pct, direccion:'SUBE'\|'BAJA', precio_actual}]}` |
| GET | `/v1/resumen-semanal` | `ciudad?, perfil?` | `{fecha, ciudad, perfil, top_comprar:[OportunidadItem x5], top_evitar:[OportunidadItem x5], alertas:[...], texto:str}` — `texto` = resumen en español listo para WhatsApp (<=600 chars, con emojis ↑↓, sin markdown) |
| GET | `/v1/comparar` | `producto_id*` | `[{mercado_id, ciudad, precio_actual, var_1w_pct}]` ordenado por precio |
| POST | `/v1/admin/ingest` | header `X-Admin-Token` | `{run_id, status, filas_insertadas, fuente}` (síncrono, timeout 120 s) |
| POST | `/v1/admin/snapshot` | header `X-Admin-Token` | `{archivos:[...]}` |

```python
class OportunidadItem(BaseModel):
    producto_id: str; nombre: str; categoria: str; mercado_id: str
    precio_actual: float; precio_1w: float; precio_4w: float
    var_1w_pct: float; var_4w_pct: float; percentil_hist: float
    score: float; senal: Literal['COMPRAR','NEUTRAL','EVITAR']
    razon: str   # frase corta generada por reglas: "18% más barata que hace un mes y en el 10% más bajo de 2 años"
```

## 7. Servidor MCP (`mcp/server.py`, fastmcp, transporte stdio y SSE en `:8001`)
Herramientas (mismas funciones internas que la API, nunca duplicar lógica):
```
listar_productos(categoria: str|None) -> list
mejores_precios(ciudad: str='Bogotá', categoria: str|None=None, perfil: str='consumidor', top: int=10) -> dict   # = /oportunidades
productos_a_evitar(ciudad, categoria, top) -> dict
tendencia_producto(producto_id: str, mercado_id: str|None=None, semanas: int=12) -> dict
pronostico_producto(producto_id: str, mercado_id: str|None=None, horizonte: int=2) -> dict
alertas_precio(ciudad: str='Bogotá', umbral_pct: float=15, ventana: str='1w') -> dict
resumen_semanal(ciudad: str='Bogotá', perfil: str='consumidor') -> dict
comparar_mercados(producto_id: str) -> list
```
Cada tool con docstring de 1–2 líneas en español describiendo cuándo usarla (el LLM la lee).

## 8. Scheduler y snapshot
- `scheduler.py`: job `run_ingest()` diario 06:00 America/Bogota + `make_snapshot()` al terminar. Arranca con la API (`lifespan`).
- `make_snapshot.py`: escribe en `data/snapshot/` los JSON de `/resumen-semanal` x {ciudades} x {perfiles} y `/oportunidades`. Si la DB no responde, la API sirve el snapshot (header `X-Data-Mode: snapshot`).

## 9. Configuración (`.env.example`)
```
DB_PATH=data/sipsa.duckdb
ADMIN_TOKEN=change-me
SOURCE_PRIORITY=excel_dane,soap_dane,socrata,seed
SOCRATA_DATASET_ID=
CIUDADES=Bogotá,Medellín,Cali
HIST_WEEKS=104
API_PORT=8000
MCP_PORT=8001
TZ=America/Bogota
```

## 10. Plan de ejecución (4 h, en este orden; no avanzar sin cumplir el checkpoint)

| Tiempo | Tarea | Checkpoint |
|---|---|---|
| 0:00–0:30 | Scaffold, `pyproject`, `schema.sql`, catálogo CSV (40 productos, 5 mercados), adaptador `seed`, `bootstrap.py` | `python scripts/bootstrap.py --source seed` crea DB con 104 semanas x 40 x 5 filas |
| 0:30–1:30 | `views.sql`, `signals.py`, `forecast.py`, `repo.py` | `tests/test_signals.py` pasa; `oportunidades` devuelve señales coherentes con seed |
| 1:30–2:15 | FastAPI completa (sección 6) + `resumen-semanal.texto` | `tests/test_api_smoke.py` (todos los GET 200) |
| 2:15–2:45 | MCP server (sección 7) | `fastmcp dev` lista 8 tools y `mejores_precios` responde |
| 2:45–3:30 | Adaptadores reales `excel_dane` -> `soap_dane` -> `socrata` (parar en el primero que funcione), `normalize.py`, `unmapped.csv` | `bootstrap.py --source auto` inserta >= 4 semanas reales; `/health.pct_seed` reportado |
| 3:30–3:50 | Scheduler, snapshot, modo offline | Apagar DB -> API sigue respondiendo con `X-Data-Mode: snapshot` |
| 3:50–4:00 | README: arranque en 3 comandos, tabla de endpoints, ejemplo `curl` por endpoint, ejemplo de config MCP para Claude Desktop/Codex | — |

Si a las 2:45 los adaptadores reales no funcionan en 30 min, quedarse con `seed` y documentarlo en `/health`. Prioridad absoluta: API + MCP estables sobre datos reales.

## 11. Criterios de aceptación
1. `uv run scripts/bootstrap.py --source auto && uv run uvicorn sipsa.api.main:app` levanta en menos de 60 s.
2. `GET /v1/resumen-semanal?ciudad=Bogotá&perfil=restaurante` devuelve `texto` legible en español con 5 comprar / 5 evitar.
3. MCP expone las 8 herramientas y cada una responde en menos de 2 s.
4. Reingestar dos veces el mismo rango no duplica filas (`ingest_log.filas_insertadas = 0` en la segunda).
5. Productos no mapeados no rompen la ingesta y quedan en `unmapped.csv`.
6. Tests: 3 archivos, menos de 15 tests en total, ejecutan en menos de 20 s.

## 12. Fuera de alcance
Auth de usuarios, frontend, envío WhatsApp, ML, Docker, precios minoristas mensuales, más de 3 ciudades.
