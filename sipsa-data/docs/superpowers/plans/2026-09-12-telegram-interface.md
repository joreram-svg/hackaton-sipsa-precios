# Telegram Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar un único bot de Telegram que permita autodeclararse como consumidor o negocio pequeño, persista preferencias por chat y funcione de punta a punta con fixtures sin enviar tráfico real durante las pruebas.

**Architecture:** Los handlers solo controlan conversación y presentación. `TelegramDataProvider` encapsula la fuente de datos y permite cambiar entre fixtures y la API sin modificar menús; `PreferenceStore` guarda perfil, ciudad y último menú en SQLite local. `telegram_bot.py` compone dependencias y arranca long polling únicamente cuando existe un token.

**Tech Stack:** Python 3.11+, `python-telegram-bot>=21,<23`, `httpx`, SQLite estándar, Pydantic Settings y pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-interfaces-telegram-dashboard-design.md`

## Global Constraints

- Trabajar únicamente en la rama `codex/web-dashboard` y su worktree.
- No añadir cálculos de precios, señales, recomendaciones, tendencias ni pronósticos.
- No hacer llamadas reales a Telegram o a servicios externos durante pruebas.
- No registrar ni imprimir `TELEGRAM_BOT_TOKEN`.
- El token real vive solo en `.env`, que ya está ignorado por Git.
- `Consumidor` y `Negocio pequeño` usan el mismo bot pero menús diferentes.
- No existe autenticación ni validación de perfil en esta versión.
- Todo dato simulado se identifica como `Modo demo · datos simulados`.
- Cada commit y cada push requieren autorización explícita del usuario.

---

### Task 1: Configuración segura y arranque controlado

**Files:**
- Modify: `.env.example`
- Modify: `pyproject.toml`
- Modify: `src/sipsa/config.py`
- Create: `src/sipsa/telegram_ui/__init__.py`
- Create: `src/sipsa/telegram_bot.py`
- Create/Test: `tests/test_telegram_ui.py`

**Interfaces:**
- Produces: `Settings.telegram_bot_token: str`, `Settings.telegram_state_path: Path`, `Settings.telegram_data_mode: Literal["demo", "api"]`, `Settings.telegram_api_base_url: str`.
- Produces: `build_application(settings: Settings, provider=None, store=None) -> Application`.
- Produces: `main() -> int`; sin token devuelve `0` y no crea una conexión.

- [ ] **Step 1: Escribir pruebas RED para configuración y ausencia de token**

```python
from pathlib import Path

from sipsa.config import Settings
from sipsa.telegram_bot import main


def test_telegram_settings_tienen_defaults_seguros(tmp_path: Path):
    settings = Settings(_env_file=None, telegram_state_path=tmp_path / "ui.sqlite")
    assert settings.telegram_bot_token == ""
    assert settings.telegram_data_mode == "demo"
    assert settings.telegram_api_base_url == "http://127.0.0.1:8000"


def test_bot_sin_token_sale_sin_error(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert main() == 0
    assert "TELEGRAM_BOT_TOKEN no configurado" in caplog.text
```

- [ ] **Step 2: Ejecutar las pruebas y comprobar RED**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: FAIL porque `sipsa.telegram_bot` y los campos de configuración no existen.

- [ ] **Step 3: Añadir dependencia y variables de entorno documentadas**

Añadir a `pyproject.toml`:

```toml
"python-telegram-bot>=21,<23",
```

Añadir a `.env.example` sin valores secretos:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_STATE_PATH=data/ui_state.sqlite
TELEGRAM_DATA_MODE=demo
TELEGRAM_API_BASE_URL=http://127.0.0.1:8000
```

Añadir a `Settings`:

```python
from typing import Literal

telegram_bot_token: str = ""
telegram_state_path: Path = PROJECT_ROOT / "data" / "ui_state.sqlite"
telegram_data_mode: Literal["demo", "api"] = "demo"
telegram_api_base_url: str = "http://127.0.0.1:8000"
```

- [ ] **Step 4: Implementar arranque sin token**

`src/sipsa/telegram_bot.py` debe exponer `main()` y no interpolar el token en logs:

```python
def main() -> int:
    settings = get_settings()
    if not settings.telegram_bot_token.strip():
        logger.warning("TELEGRAM_BOT_TOKEN no configurado; el bot no se iniciará")
        return 0
    application = build_application(settings)
    application.run_polling(drop_pending_updates=False)
    return 0
```

- [ ] **Step 5: Ejecutar prueba focalizada**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: PASS, sin conexión de red.

- [ ] **Step 6: Solicitar autorización antes del commit**

Proposed commit: `feat: add secure Telegram bot configuration`

---

### Task 2: Persistencia de perfil y menús diferenciados

**Files:**
- Create: `src/sipsa/telegram_ui/state.py`
- Create: `src/sipsa/telegram_ui/menus.py`
- Modify/Test: `tests/test_telegram_ui.py`

**Interfaces:**
- Produces: `UserPreferences(chat_id: int, profile: UserProfile | None, city: str, last_menu: str)`.
- Produces: `PreferenceStore.get(chat_id: int) -> UserPreferences` y `PreferenceStore.save(preferences: UserPreferences) -> None`.
- Produces: `profile_keyboard()`, `consumer_keyboard()` y `small_business_keyboard()`.

- [ ] **Step 1: Escribir pruebas RED de persistencia y separación de menús**

```python
def test_preferencias_sobreviven_a_reabrir_sqlite(tmp_path):
    path = tmp_path / "ui.sqlite"
    PreferenceStore(path).save(UserPreferences(42, UserProfile.SMALL_BUSINESS, "Cali", "home"))
    loaded = PreferenceStore(path).get(42)
    assert loaded.profile is UserProfile.SMALL_BUSINESS
    assert loaded.city == "Cali"


def test_menus_de_perfiles_son_diferentes():
    consumer = keyboard_texts(consumer_keyboard())
    business = keyboard_texts(small_business_keyboard())
    assert "Precios de hoy" in consumer
    assert "Resumen del negocio" not in consumer
    assert "Resumen del negocio" in business
    assert "Cambiar perfil" in consumer
    assert "Cambiar perfil" in business
```

- [ ] **Step 2: Ejecutar pruebas y comprobar RED**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: FAIL por módulos ausentes.

- [ ] **Step 3: Implementar estado SQLite mínimo**

Usar `sqlite3`, crear la tabla de forma idempotente y serializar perfiles como `consumer` y `small_business`. La conexión se abre por operación para evitar compartir conexiones entre callbacks async.

```sql
CREATE TABLE IF NOT EXISTS telegram_preferences (
  chat_id INTEGER PRIMARY KEY,
  profile TEXT,
  city TEXT NOT NULL,
  last_menu TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
```

- [ ] **Step 4: Implementar teclados inline**

Callbacks estables:

```text
profile:consumer
profile:small_business
consumer:today
consumer:search
consumer:compare
consumer:recent
business:summary
business:explore
business:watchlist
business:compare
business:preferences
business:history
common:city
common:profile
common:home
common:retry
```

- [ ] **Step 5: Ejecutar pruebas focalizadas**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 6: Solicitar autorización antes del commit**

Proposed commit: `feat: persist Telegram profiles and menus`

---

### Task 3: Proveedor intercambiable y fixtures

**Files:**
- Create: `src/sipsa/telegram_ui/data_provider.py`
- Create: `web/fixtures/ciudades.json`
- Create: `web/fixtures/productos.json`
- Create: `web/fixtures/resumen.json`
- Create: `web/fixtures/tendencia.json`
- Create: `web/fixtures/comparacion.json`
- Modify/Test: `tests/test_telegram_ui.py`
- Create/Test: `tests/test_ui_contract.py`

**Interfaces:**
- Produces: `UiPayload(text: str, demo: bool, metadata: dict[str, object])`.
- Produces: protocolo async `TelegramDataProvider` con `list_cities()`, `search_products(query)`, `summary(city, audience)`, `trend(product_id, city)` y `compare_cities(product_id)`.
- Produces: `FixtureTelegramDataProvider` y `ApiTelegramDataProvider`.

- [ ] **Step 1: Escribir prueba contractual RED**

```python
import asyncio
import json


def test_fixture_provider_marca_toda_respuesta_como_demo():
    provider = FixtureTelegramDataProvider(FIXTURE_ROOT)
    payload = asyncio.run(provider.summary("Bogotá", "small_business"))
    assert payload.demo is True
    assert payload.text
    assert payload.metadata["city"] == "Bogotá"


def test_fixtures_tienen_forma_minima():
    for name in ["ciudades", "productos", "resumen", "tendencia", "comparacion"]:
        data = json.loads((FIXTURE_ROOT / f"{name}.json").read_text(encoding="utf-8"))
        assert data["mode"] == "demo"
        assert data["data"]
```

- [ ] **Step 2: Ejecutar pruebas y comprobar RED**

Run: `python -m pytest tests/test_ui_contract.py tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: FAIL por proveedor y fixtures ausentes.

- [ ] **Step 3: Implementar fixtures compartidos**

Cada archivo debe incluir:

```json
{
  "mode": "demo",
  "generated_at": "2026-09-12T00:00:00-05:00",
  "data": []
}
```

Los elementos internos imitan el contrato REST aprobado; los valores son claramente ficticios y solo validan presentación.

- [ ] **Step 4: Implementar proveedores**

`FixtureTelegramDataProvider` lee archivos locales. `ApiTelegramDataProvider` usa `httpx.AsyncClient(base_url=..., timeout=5.0)` y convierte errores de red, estados no exitosos o JSON inválido en `DataUnavailable` sin ocultarlos con fixtures.

La correspondencia del perfil UI con el parámetro actual del backend vive en una constante de adaptación, no en los handlers:

```python
API_AUDIENCE = {"consumer": "consumidor", "small_business": "restaurante"}
```

- [ ] **Step 5: Ejecutar pruebas focalizadas**

Run: `python -m pytest tests/test_ui_contract.py tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: PASS, sin red.

- [ ] **Step 6: Solicitar autorización antes del commit**

Proposed commit: `feat: add swappable Telegram data providers`

---

### Task 4: Onboarding y enrutamiento conversacional

**Files:**
- Create: `src/sipsa/telegram_ui/handlers.py`
- Modify: `src/sipsa/telegram_bot.py`
- Modify/Test: `tests/test_telegram_ui.py`

**Interfaces:**
- Produces: handlers async `start`, `select_profile`, `select_city`, `handle_action`, `change_profile`, `show_home`.
- Consumes: `PreferenceStore` y `TelegramDataProvider` mediante `context.application.bot_data`.

- [ ] **Step 1: Escribir pruebas RED de recorridos**

```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


def make_update(callback_data=None):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=42),
        message=SimpleNamespace(reply_text=AsyncMock()),
        callback_query=SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        ),
    )


def make_context(store, provider):
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"store": store, "provider": provider})
    )


def test_start_pide_perfil_a_chat_nuevo(tmp_path):
    update = make_update()
    context = make_context(PreferenceStore(tmp_path / "ui.sqlite"), SimpleNamespace())
    asyncio.run(start(update, context))
    text = update.message.reply_text.await_args.args[0]
    assert "¿Cómo usarás el servicio?" in text


def test_cambiar_perfil_reemplaza_menu(tmp_path):
    store = PreferenceStore(tmp_path / "ui.sqlite")
    store.save(UserPreferences(42, UserProfile.CONSUMER, "Bogotá", "home"))
    update = make_update("profile:small_business")
    context = make_context(store, SimpleNamespace())
    asyncio.run(select_profile(update, context))
    assert store.get(42).profile is UserProfile.SMALL_BUSINESS
    text = update.callback_query.edit_message_text.await_args.args[0]
    assert "Resumen del negocio" in text
    assert "Precios de hoy" not in text
```

- [ ] **Step 2: Ejecutar pruebas y comprobar RED**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: FAIL por handlers ausentes.

- [ ] **Step 3: Implementar composición del bot**

`build_application()` registra:

```python
CommandHandler("start", start)
CommandHandler("inicio", show_home)
CommandHandler("perfil", change_profile)
CallbackQueryHandler(select_profile, pattern=r"^profile:")
CallbackQueryHandler(select_city, pattern=r"^city:")
CallbackQueryHandler(handle_action, pattern=r"^(consumer|business|common):")
```

Las acciones obtienen un `UiPayload` del proveedor y lo presentan. Cuando `payload.demo` es verdadero, anteponen `🧪 Modo demo · datos simulados`.

- [ ] **Step 4: Implementar degradación controlada**

`DataUnavailable` produce texto visible, conserva perfil/ciudad y presenta botones `Reintentar` y `Volver al menú`. Cualquier excepción inesperada se registra sin token, texto del usuario ni datos personales.

- [ ] **Step 5: Ejecutar pruebas focalizadas**

Run: `python -m pytest tests/test_telegram_ui.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 6: Solicitar autorización antes del commit**

Proposed commit: `feat: add adaptive Telegram conversation flow`

---

### Task 5: Verificación integral y guía de configuración

**Files:**
- Create: `README.md` if absent, otherwise modify it
- Modify: `.gitignore`
- Modify/Test: `tests/test_telegram_ui.py`
- Modify/Test: `tests/test_ui_contract.py`

**Interfaces:**
- Documents: creación manual del bot en `@BotFather`, configuración local del token, modo demo, modo API y arranque.

- [ ] **Step 1: Proteger archivos locales**

Añadir a `.gitignore`:

```gitignore
*.sqlite
*.sqlite3
```

Verificar:

Run: `git check-ignore -v sipsa-data/.env sipsa-data/data/ui_state.sqlite`

Expected: ambos archivos ignorados.

- [ ] **Step 2: Documentar configuración segura**

Comandos documentados:

```powershell
Copy-Item .env.example .env
# El usuario agrega TELEGRAM_BOT_TOKEN directamente en .env; nunca lo pega en el chat.
python -m sipsa.telegram_bot
```

El README debe explicar que el nombre visible es `Baskio` y que el username debe ser único y terminar en `bot`.

- [ ] **Step 3: Ejecutar suite sin red**

Run: `python -m pytest tests/test_telegram_ui.py tests/test_ui_contract.py -v -p no:cacheprovider`

Expected: todas las pruebas pasan y ninguna abre long polling.

- [ ] **Step 4: Ejecutar smoke sin token**

Run: `python -m sipsa.telegram_bot`

Expected: exit code `0` y aviso `TELEGRAM_BOT_TOKEN no configurado`.

- [ ] **Step 5: Ejecutar auditoría de secretos antes de cualquier commit**

Run: `git status --short && git diff --check && rg -n "[0-9]{8,10}:[A-Za-z0-9_-]{30,}" . --glob '!sipsa-data/.env'`

Expected: ninguna coincidencia de patrón de token y `sipsa-data/.env` ausente del estado de Git.

- [ ] **Step 6: Solicitar autorización antes del commit y del push**

Proposed commit: `docs: add Telegram bot setup and verification`
