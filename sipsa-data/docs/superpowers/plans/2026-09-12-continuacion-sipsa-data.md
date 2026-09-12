# Continuación SIPSA Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el servicio SIPSA Data desde el checkpoint 3, migrándolo al grano semanal fecha/producto/precio/ciudad y añadiendo MCP, fuentes reales con fallback, operación offline, dashboard, bot y documentación.

**Architecture:** DuckDB es la fuente local de verdad y `Repository` concentra toda la consulta usada por REST, MCP y Telegram. Los adaptadores entregan el RAW común; la normalización resuelve productos/unidades y agrega mercados al nivel ciudad antes del upsert. Los snapshots son una caché JSON de lectura para las rutas de demo cuando DuckDB no está disponible.

**Tech Stack:** Python 3.11+, DuckDB, pandas, FastAPI, FastMCP, APScheduler, httpx, openpyxl, zeep opcional y python-telegram-bot 21+; frontend HTML/CSS/JS vanilla.

**Spec:** `../BRIEF_TECNICO_SIPSA_DATA.md` (brief padre, secciones 0-A, 10 y 13)

## Global Constraints

- Trabajar solo dentro de `sipsa-data`; leer el brief desde la carpeta padre.
- No conservar `dim_mercado`, `mercado_id`, `precio_min` ni `precio_max` en el modelo normalizado.
- Grano de `fact_precio`: `(fecha, producto_id, ciudad)` y valor `precio` COP/kg.
- Reusar `Repository` desde REST, MCP y Telegram; no duplicar reglas de negocio.
- Datos reales fallan de forma controlada hacia seed y cada fila conserva `fuente`.
- No hacer commit, push, publicar ni tocar producción.

---

### Task 1: Esquema simplificado y migración DuckDB

**Files:**
- Modify: `src/sipsa/db/schema.sql`, `src/sipsa/db/views.sql`, `src/sipsa/db/repo.py`
- Modify: `src/sipsa/ingest/pipeline.py`, `src/sipsa/sources/seed.py`
- Modify: `src/sipsa/analytics/forecast.py`, `src/sipsa/api/models.py`, `src/sipsa/api/main.py`
- Modify/Test: `tests/test_normalize.py`, `tests/test_api_smoke.py`

**Interfaces:**
- Produces: `fact_precio(fecha, producto_id, ciudad, precio, fuente, ingested_at)`; consultas con argumento `ciudad`; endpoint `/v1/ciudades`; tool futura `comparar_ciudades`.

- [ ] Escribir una prueba que cree un DuckDB legado con dos mercados de una ciudad y exija una fila migrada con el precio promedio.
- [ ] Ejecutar la prueba y confirmar que falla por el esquema legado aún vigente.
- [ ] Implementar migración transaccional, actualizar semilla/vistas/repositorio/modelos/rutas y eliminar dependencias de mercado.
- [ ] Ejecutar pruebas focalizadas y luego `python scripts/bootstrap.py --source seed` dos veces; confirmar 12.480 filas, esquema real correcto e idempotencia.

### Task 2: Servidor MCP

**Files:**
- Create: `src/sipsa/mcp/__init__.py`, `src/sipsa/mcp/server.py`
- Modify/Test: `tests/test_api_smoke.py`

**Interfaces:**
- Consumes: métodos públicos de `Repository` y `build_weekly_summary`.
- Produces: ocho tools: `listar_productos`, `mejores_precios`, `productos_a_evitar`, `tendencia_producto`, `pronostico_producto`, `alertas_precio`, `resumen_semanal`, `comparar_ciudades`.

- [ ] Actualizar la prueba MCP al contrato por ciudad y confirmar RED por módulo ausente.
- [ ] Verificar/instalar `fastmcp`; si la red impide instalarlo, registrar el error y mantener importación opcional testeable.
- [ ] Implementar tools delgadas con docstrings en español y CLI stdio/SSE.
- [ ] Ejecutar el smoke de registro, una invocación con DuckDB real y el comando de inspección disponible en la versión instalada.

### Task 3: Adaptadores, normalización y fallback

**Files:**
- Create: `src/sipsa/ingest/normalize.py`
- Create: `src/sipsa/sources/excel_dane.py`, `soap_dane.py`, `socrata.py`
- Modify: `src/sipsa/ingest/pipeline.py`
- Modify/Test: `tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize_prices(raw, catalog, unmapped_path) -> DataFrame[fecha, producto_id, ciudad, precio, fuente]` y adaptadores `SourceAdapter`.

- [ ] Escribir pruebas para alias/acentos, conversión de libra, agregación de mercados por ciudad, `unmapped.csv` y fallback automático.
- [ ] Confirmar RED por normalizador/adaptadores ausentes.
- [ ] Implementar descubrimiento/lectura Excel, SOAP lazy, paginación Socrata y selección por prioridad con seed complementario.
- [ ] Ejecutar pruebas y `bootstrap.py --source auto`; comprobar fuente/pct_seed y documentar si el entorno no entrega cuatro semanas reales.

### Task 4: Scheduler, snapshot y offline

**Files:**
- Create: `scripts/make_snapshot.py`, `src/sipsa/scheduler.py`
- Modify: `src/sipsa/api/main.py`
- Create/Test: `tests/test_offline.py`

**Interfaces:**
- Produces: `make_snapshot(settings=None) -> list[str]`, job diario 06:00 y fallback con `X-Data-Mode: snapshot`.

- [ ] Escribir prueba que genere snapshots, haga indisponible DuckDB y exija respuesta 200 desde snapshot.
- [ ] Confirmar RED por módulos ausentes.
- [ ] Implementar snapshots atómicos, scheduler en lifespan y fallback solo lectura.
- [ ] Ejecutar prueba focalizada y smoke offline real.

### Task 5: Dashboard web

**Files:**
- Create: `web/index.html`, `web/styles.css`, `web/app.js`
- Modify: `src/sipsa/api/main.py`
- Create/Test: `tests/test_dashboard.py`

**Interfaces:**
- Consume: `/v1/resumen-semanal`, `/v1/productos`, `/v1/tendencia/{producto_id}`.

- [ ] Escribir smoke HTTP para `/` y assets; confirmar RED con 404.
- [ ] Implementar semántica accesible, selectores, tarjetas, alertas, búsqueda y sparkline SVG sin estilos inline.
- [ ] Montar `StaticFiles` al final de rutas, ejecutar smoke y revisar visualmente desktop/móvil.

### Task 6: Bot de Telegram

**Files:**
- Create: `src/sipsa/telegram_bot.py`
- Modify: `src/sipsa/config.py`, `.env.example`, `pyproject.toml`, `src/sipsa/scheduler.py`
- Create/Test: `tests/test_telegram_bot.py`

**Interfaces:**
- Produces: comandos async `/start`, `/hoy`, `/precio`, `/alertas`; `python -m sipsa.telegram_bot`; push diario a `TELEGRAM_CHAT_IDS`.

- [ ] Escribir pruebas del texto de `/hoy`, resolución de producto y salida exitosa sin token; confirmar RED.
- [ ] Verificar `python-telegram-bot` instalado antes de intentar red.
- [ ] Implementar handlers delgados y envío diario opcional sin llamadas reales en tests.
- [ ] Ejecutar pruebas y smoke del proceso sin token.

### Task 7: README y verificación integral

**Files:**
- Create: `README.md`

**Interfaces:**
- Documenta comandos copiables para bootstrap/API+dashboard, MCP stdio/SSE y bot.

- [ ] Documentar configuración, esquema, fuentes/fallback, endpoints, snapshots, Telegram y troubleshooting de dependencias.
- [ ] Ejecutar suite completa sin caché, bootstrap seed doble, smoke REST real, inventario MCP, snapshot offline, raíz web y bot sin token.
- [ ] Revisar diff, imports/código muerto y requisitos del brief; reportar bloqueos reales sin ocultarlos.
