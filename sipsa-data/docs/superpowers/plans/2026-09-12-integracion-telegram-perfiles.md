# Integración Telegram y perfiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versionar las tablas de recomendaciones, completar los cinco contratos REST y portar a `main` la experiencia Telegram con perfil, ciudad y recomendaciones reales.

**Architecture:** `Repository` conserva los contratos de datos REST existentes y `ApiTelegramDataProvider` los transforma a `UiPayload` legible sin cambiar los esquemas públicos. `PreferenceStore` persiste perfil y ciudad por chat; `SupabaseRecommendationsProvider` consulta solo las tablas permitidas mediante un mapeo fijo y degrada explícitamente en DuckDB.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, DuckDB, PostgreSQL/psycopg2, httpx, python-telegram-bot, SQLite y pytest.

**Spec:** `docs/integracion_telegram_perfiles_brief.md`

## Global Constraints

- Trabajar en el repo principal `C:\Users\Categorymanager\Desktop\JORE\Phyton\Hackaton`, rama `main`.
- No modificar `.worktrees/web-dashboard` ni `sipsa-data/web/`; esos archivos solo se leen como referencia.
- No hacer commit, push, publicar ni conectarse a sistemas reales durante las pruebas.
- Mapeo UI/API: `consumer -> consumidor`, `small_business -> restaurante`, `tendero -> mayorista`.
- Mapeo UI/tablas: `consumer -> recomendaciones_consumidor`, `small_business -> recomendaciones_restaurante`, `tendero -> recomendaciones_tendero`.
- Fechas REST en ISO `YYYY-MM-DD`; errores con `{ "error": { "code": "...", "message": "..." } }`.
- Ejecutar `python -m pytest -p no:cacheprovider tests/ -q` desde `sipsa-data` antes de reportar.

---

### Task 1: Esquema versionado de recomendaciones

**Files:**
- Modify: `src/sipsa/db/schema.sql`
- Modify: `src/sipsa/db/schema_postgres.sql`
- Test: `tests/test_recommendation_schema.py`

**Interfaces:**
- Produces: `recomendaciones_consumidor`, `recomendaciones_restaurante` y `recomendaciones_tendero` con columnas `id`, `fecha`, `ciudad`, `tipo`, `estado`, `contenido`, `fuente_fecha`, `created_at`, `updated_at`; PK, unicidad `(fecha, ciudad, tipo)` y estados permitidos.

- [ ] **Step 1: Escribir prueba RED** que aplique `schema.sql` a DuckDB temporal e inspeccione las tres tablas, sus columnas, unicidad y validación de `estado`; inspeccionar también que el SQL PostgreSQL declare `JSONB`, identidad y los tres nombres.
- [ ] **Step 2: Ejecutar RED** con `python -m pytest -p no:cacheprovider tests/test_recommendation_schema.py -q` y confirmar que faltan las tablas.
- [ ] **Step 3: Implementar esquema mínimo** replicando el contrato auditado; usar secuencias locales en DuckDB e identidad `GENERATED ALWAYS` en PostgreSQL.
- [ ] **Step 4: Ejecutar GREEN** con el mismo comando y confirmar cero fallos.

### Task 2: Contratos REST y adaptador HTTP para Telegram

**Files:**
- Modify: `src/sipsa/db/repo.py`
- Modify: `src/sipsa/api/main.py`
- Create: `src/sipsa/telegram_ui/__init__.py`
- Create: `src/sipsa/telegram_ui/data_provider.py`
- Test: `tests/test_api_smoke.py`
- Create/Test: `tests/test_ui_contract.py`

**Interfaces:**
- Produces: `GET /v1/ciudades`, `/v1/productos`, `/v1/resumen-semanal`, `/v1/tendencia/{producto_id}` y `/v1/comparar` con los modelos actuales; `/v1/productos?q=` filtra por nombre/ID sin acentos.
- Produces: `API_AUDIENCE = {"consumer": "consumidor", "small_business": "restaurante", "tendero": "mayorista"}` y métodos async que convierten las respuestas REST reales a `UiPayload`.

- [ ] **Step 1: Escribir pruebas RED** para búsqueda `q`, rutas y parámetros exactos, transformación de ciudades/productos/resumen/tendencia/comparación y manejo de error HTTP/formato.
- [ ] **Step 2: Ejecutar RED** y confirmar fallo por paquete/mapeo/filtro ausente.
- [ ] **Step 3: Implementar el filtro y adaptador** sin cambiar los modelos públicos ni duplicar cálculos de negocio.
- [ ] **Step 4: Ejecutar GREEN** en los dos archivos de pruebas.

### Task 3: Estado, menús y recomendaciones por perfil/ciudad

**Files:**
- Modify: `src/sipsa/config.py`
- Create: `src/sipsa/telegram_ui/state.py`
- Create: `src/sipsa/telegram_ui/menus.py`
- Create: `src/sipsa/telegram_ui/handlers.py`
- Modify: `src/sipsa/telegram_ui/data_provider.py`
- Create/Test: `tests/test_telegram_ui.py`

**Interfaces:**
- Produces: `UserProfile.CONSUMER`, `SMALL_BUSINESS`, `TENDERO`; `PreferenceStore`; menús para los tres perfiles; `SupabaseRecommendationsProvider.recommendations(profile, city) -> UiPayload`.
- Consumes: `Settings.db_backend`, `Settings.supabase_db_url`, `Settings.telegram_state_path` y el mapeo fijo de tablas.

- [ ] **Step 1: Escribir pruebas RED** para persistencia, tercer perfil/menú, filtrado de items por ciudad, SQL parametrizada, selección de tabla fija y degradación DuckDB.
- [ ] **Step 2: Ejecutar RED** y confirmar fallo por módulos/funciones ausentes.
- [ ] **Step 3: Portar estado/menús/handlers** adaptando textos y acciones para consumidor, restaurante y tendero; integrar `/recomendaciones` y callbacks.
- [ ] **Step 4: Implementar proveedor real** con conexión PostgreSQL de solo lectura, parseo defensivo de JSON y texto limitado para Telegram.
- [ ] **Step 5: Ejecutar GREEN** en `tests/test_telegram_ui.py` y `tests/test_ui_contract.py`.

### Task 4: Composición del bot, configuración, documentación y cierre

**Files:**
- Modify: `src/sipsa/telegram_bot.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_telegram_ui.py`

**Interfaces:**
- Produces: comandos `/start`, `/inicio`, `/perfil`, `/ciudad`, `/recomendaciones`, `/hoy`, `/precio`, `/alertas`; callbacks y búsqueda de texto; inyección de providers/store en `build_application`.

- [ ] **Step 1: Escribir prueba RED** del registro de comandos y dependencias sin iniciar red.
- [ ] **Step 2: Ejecutar RED** y confirmar que faltan handlers/dependencias.
- [ ] **Step 3: Fusionar composición UI con comandos existentes**, conservando push diario y salida segura sin token.
- [ ] **Step 4: Documentar variables y comandos exactos** en `.env.example` y `README.md`.
- [ ] **Step 5: Ejecutar pruebas focalizadas**, revisar diff/archivos fuera de alcance/imports muertos y corregir regresiones.
- [ ] **Step 6: Ejecutar verificación final fresca**: `python -m pytest -p no:cacheprovider tests/ -q` desde `sipsa-data`, registrar salida y código exactos.
