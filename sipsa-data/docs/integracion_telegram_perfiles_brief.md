# Integración: Telegram con cambio de perfil/ciudad + tablas de recomendaciones — Brief autónomo

Ejecutor: Codex. Documento autónomo, no tienes historial de conversación previo. Trabaja en `C:\Users\Categorymanager\Desktop\JORE\Phyton\Hackaton` (rama `main`, NO en el worktree `.worktrees/web-dashboard`).

## Contexto

- `main` ya tiene: backend completo (DuckDB + Postgres/Supabase intercambiable vía `DB_BACKEND`), API REST, MCP, dashboard web funcional en `sipsa-data/web/`, un `telegram_bot.py` simple (comandos `/start`, `/hoy`, `/precio`, `/alertas`), scheduler diario.
- Existe una rama paralela `codex/web-dashboard` (worktree en `C:\Users\Categorymanager\Desktop\JORE\Phyton\Hackaton\.worktrees\web-dashboard`) que diverge de un punto muy anterior de `main` y construyó ahí un paquete **`sipsa/telegram_ui/`** (`state.py`, `data_provider.py`, `handlers.py`, `menus.py`) con: persistencia de preferencias por chat (SQLite), cambio de perfil de usuario, cambio de ciudad, y dos proveedores de datos intercambiables (`FixtureTelegramDataProvider` para demo, `ApiTelegramDataProvider` para producción vía HTTP a nuestra API).
- **NO hagas un `git merge` directo de esa rama** — reescribió los mismos archivos que `main` (telegram_bot.py, tests, web/) con una arquitectura distinta y anterior; un merge automático va a generar conflictos peores que portar el código a mano. En vez de eso, **inspecciona** los archivos de esa rama (léelos directamente del worktree, es de solo lectura para ti, no modifiques nada ahí) y **porta/adapta** el paquete `telegram_ui/` (los 4 archivos: `state.py`, `data_provider.py`, `handlers.py`, `menus.py`, más sus tests `test_telegram_ui.py`/`test_ui_contract.py`) hacia `main`, reemplazando/integrando con el `telegram_bot.py` actual de `main` (consérvalo o fusiónalo, tu criterio, pero el resultado final debe tener toda la funcionalidad de cambio de perfil/ciudad).
- Ya auditamos las 3 tablas de recomendaciones en Supabase (ver `sipsa-data/docs/revision_tablas_recomendaciones.md` para el detalle completo): `public.recomendaciones_consumidor` (180 filas), `public.recomendaciones_restaurante` (200 filas), `public.recomendaciones_tendero` (160 filas). Cada fila tiene una columna JSON `contenido` con `items[]`, cada item con `producto_id` (existe en `dim_producto`), `ciudad`, y contenido de recomendación. No tienen foreign keys formales pero la integridad referencial contra `dim_producto`/`fact_precio` ya fue verificada al 100%.

## Objetivo funcional (lo que pide el usuario)

Un usuario de Telegram debe poder:
1. Elegir/cambiar su **perfil**: `consumidor`, `restaurante`, o **`tendero`** (este tercer perfil falta en el código de la rama — el enum `UserProfile` en `state.py` solo tiene `CONSUMER` y `SMALL_BUSINESS`; agrégale `TENDERO = "tendero"`).
2. Elegir/cambiar su **ciudad** (de las 20 ciudades reales que ya tenemos en `fact_precio`/Supabase, ver `config.py::ciudades`).
3. Recibir recomendaciones **específicas a su perfil + ciudad**, extraídas de la tabla `recomendaciones_<perfil>` correspondiente en Supabase, filtrando los `items` del JSON por la ciudad elegida.
4. Los comandos existentes (`/hoy`, `/precio`, `/alertas`) de `main` deben seguir funcionando (siguen sirviendo del REST/MCP existente); lo nuevo es el flujo de selección de perfil/ciudad + recomendaciones personalizadas.

## Tareas

1. **Lee primero** (sin modificar) los archivos de la rama en el worktree:
   - `.worktrees/web-dashboard/sipsa-data/src/sipsa/telegram_ui/state.py`
   - `.worktrees/web-dashboard/sipsa-data/src/sipsa/telegram_ui/data_provider.py`
   - `.worktrees/web-dashboard/sipsa-data/src/sipsa/telegram_ui/handlers.py`
   - `.worktrees/web-dashboard/sipsa-data/src/sipsa/telegram_ui/menus.py`
   - `.worktrees/web-dashboard/sipsa-data/tests/test_telegram_ui.py`
   - `.worktrees/web-dashboard/sipsa-data/tests/test_ui_contract.py`
   - También lee `sipsa-data/src/sipsa/telegram_bot.py` actual de `main` y `sipsa-data/src/sipsa/api/main.py` (rutas reales) para saber qué contrato de API ya existe.

2. **Porta** el paquete `telegram_ui/` a `main` en `sipsa-data/src/sipsa/telegram_ui/`, con estos cambios:
   - Agrega `TENDERO = "tendero"` al enum `UserProfile` en `state.py`, y su mapeo correspondiente donde se use (ej. `API_AUDIENCE` en `data_provider.py`: agrega `"tendero": "mayorista"` o el nombre de perfil que use nuestra API/MCP — revisa `sipsa/analytics/signals.py` o `api/models.py` para el nombre exacto del perfil `mayorista`/`tendero` que ya usamos en el resto del sistema, y sé consistente).
   - Corrige las rutas de `ApiTelegramDataProvider` para que coincidan con las reales de `main` (`/v1/resumen-semanal` en vez de `/v1/resumen`, `/v1/comparar` en vez de `/v1/comparacion/{id}`, revisa el resto contra `api/main.py`).

3. **Nuevo proveedor de recomendaciones reales**: añade una clase (ej. `SupabaseRecomendacionesProvider` o un método nuevo en el provider existente) que, dado `perfil` (consumidor/restaurante/tendero) y `ciudad`, consulte la tabla `recomendaciones_<perfil>` en Supabase (usa `SUPABASE_DB_URL` de `.env`, psycopg2 ya instalado) y devuelva los `items` del JSON `contenido` filtrados por esa ciudad, formateados como texto legible para Telegram (similar al `UiPayload.text` que ya usa el resto del sistema). Si `DB_BACKEND=duckdb` (sin Supabase disponible), degrada con un mensaje claro de "recomendaciones no disponibles en modo local" en vez de fallar feo.

4. **Integra** este flujo en `handlers.py`/`telegram_bot.py`: un comando (ej. `/perfil` para elegir perfil, `/ciudad` para elegir ciudad, y que `/recomendaciones` o el menú principal muestre las recomendaciones del perfil+ciudad actual del usuario, usando `PreferenceStore` para recordar la selección entre mensajes).

5. **Tests**: adapta/porta `test_telegram_ui.py` y `test_ui_contract.py` a `main`, agrega un test para el perfil `tendero` y para el proveedor de recomendaciones reales (puedes mockear la conexión a Postgres en el test, no necesitas pegarle a Supabase real en cada test run). Corre `pytest tests/ -q` completo y confirma que todo pasa (no debe romper nada existente).

6. **No toques** `sipsa-data/web/` (el dashboard actual de `main` ya está verificado y funcionando) ni el worktree `.worktrees/web-dashboard` (es de solo lectura para esta tarea).

7. Actualiza `sipsa-data/README.md` con la sección de comandos nuevos de Telegram (`/perfil`, `/ciudad`, cómo ver recomendaciones).

No hagas commit ni push. Al terminar, reporta en texto plano: qué se portó, cómo quedó el mapeo de perfiles (los 3), cómo se conecta a las tablas reales de recomendaciones, estado de los tests, y comandos exactos para probar el bot con cambio de perfil/ciudad.
