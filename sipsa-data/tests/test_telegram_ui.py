import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sipsa.config import Settings


def _button_callbacks(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]


def _make_update(callback_data=None, text=None):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=42),
        effective_message=SimpleNamespace(text=text, reply_text=AsyncMock()),
        message=SimpleNamespace(text=text, reply_text=AsyncMock()),
        callback_query=SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        ),
    )


def _make_context(store, provider, recommendations_provider):
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "store": store,
                "provider": provider,
                "recommendations_provider": recommendations_provider,
            }
        )
    )


def test_preferencias_persisten_los_tres_perfiles_entre_instancias(tmp_path: Path):
    """Detecta que tendero no sea serializable o que una reapertura pierda la selección."""
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    state_path = tmp_path / "telegram.sqlite"
    store = PreferenceStore(state_path)
    assert store.get(42).profile is None
    assert store.get(42).city == "Bogotá"

    store.set_profile(42, UserProfile.TENDERO)
    store.set_city(42, "Medellín")

    restored = PreferenceStore(state_path).get(42)
    assert restored.profile is UserProfile.TENDERO
    assert restored.city == "Medellín"


def test_menu_de_perfiles_y_homes_exponen_tendero_y_recomendaciones():
    """Detecta que el tercer perfil o la entrada a recomendaciones desaparezcan."""
    from sipsa.telegram_ui.menus import (
        consumer_menu,
        profile_menu,
        restaurant_menu,
        tendero_menu,
    )

    assert _button_callbacks(profile_menu()) == [
        "profile:consumer",
        "profile:small_business",
        "profile:tendero",
    ]
    for menu in (consumer_menu(), restaurant_menu(), tendero_menu()):
        callbacks = _button_callbacks(menu)
        assert "common:recommendations" in callbacks
        assert "common:city" in callbacks
        assert "common:profile" in callbacks


def test_recomendaciones_en_duckdb_degradan_con_mensaje_explicito():
    """Detecta intentos de consultar tablas remotas cuando el modo local está activo."""
    from sipsa.telegram_ui.data_provider import SupabaseRecommendationsProvider

    settings = Settings(_env_file=None, db_backend="duckdb")
    provider = SupabaseRecommendationsProvider(settings, connect=lambda _: (_ for _ in ()).throw(AssertionError("no conectar")))

    payload = asyncio.run(provider.recommendations("consumer", "Bogotá"))

    assert payload.demo is False
    assert payload.text == "Las recomendaciones no están disponibles en modo local."
    assert payload.metadata == {"profile": "consumer", "city": "Bogotá", "available": False}


class _RecommendationCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _RecommendationConnection:
    def __init__(self, rows):
        self.cursor_instance = _RecommendationCursor(rows)
        self.read_only = None
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def set_session(self, readonly):
        self.read_only = readonly

    def close(self):
        self.closed = True


def test_recomendaciones_tendero_consultan_tabla_fija_y_filtran_items_por_ciudad():
    """Detecta tabla equivocada, SQL inyectable o mezcla de recomendaciones entre ciudades."""
    from sipsa.telegram_ui.data_provider import SupabaseRecommendationsProvider

    rows = [
        (
            "2026-09-07",
            "productos_caida_precio",
            "disponible",
            {
                "mensaje": "Productos con mayor caída semanal.",
                "items": [
                    {"producto_id": "papa_pastusa", "producto": "Papa pastusa", "ciudad": "Bogotá", "precio_actual": 2400},
                    {"producto_id": "banano", "producto": "Banano", "ciudad": "Medellín", "precio_actual": 2800},
                ],
            },
            "2026-09-07",
        )
    ]
    connection = _RecommendationConnection(rows)
    settings = Settings(
        _env_file=None,
        db_backend="postgres",
        supabase_db_url="postgresql://user:secret@host/db",
    )
    provider = SupabaseRecommendationsProvider(settings, connect=lambda _: connection)

    payload = asyncio.run(provider.recommendations("tendero", "Bogotá"))

    sql, params = connection.cursor_instance.executed
    assert "FROM recomendaciones_tendero" in sql
    assert params == ("Bogotá", "Bogotá")
    assert "Papa pastusa" in payload.text
    assert "Banano" not in payload.text
    assert payload.metadata["table"] == "recomendaciones_tendero"
    assert connection.read_only is True
    assert connection.closed is True


def test_seleccionar_tendero_y_pedir_recomendaciones_usa_preferencias(tmp_path: Path):
    """Detecta que el handler ignore el perfil/ciudad persistidos al consultar recomendaciones."""
    from sipsa.telegram_ui.data_provider import UiPayload
    from sipsa.telegram_ui.handlers import recommendations_command, select_profile
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    store = PreferenceStore(tmp_path / "telegram.sqlite")
    recommendations_provider = SimpleNamespace(
        recommendations=AsyncMock(return_value=UiPayload("Recomendación personalizada"))
    )
    context = _make_context(store, object(), recommendations_provider)

    asyncio.run(select_profile(_make_update("profile:tendero"), context))
    store.set_city(42, "Cali")
    update = _make_update()
    asyncio.run(recommendations_command(update, context))

    assert store.get(42).profile is UserProfile.TENDERO
    recommendations_provider.recommendations.assert_awaited_once_with("tendero", "Cali")
    assert update.effective_message.reply_text.await_args.args[0] == "Recomendación personalizada"


def test_settings_de_telegram_tienen_defaults_seguros(tmp_path: Path):
    """Detecta rutas de estado globales o URLs de API no configurables."""
    settings = Settings(_env_file=None, telegram_state_path=tmp_path / "state.sqlite")

    assert settings.telegram_api_base_url == "http://127.0.0.1:8000"
    assert settings.telegram_state_path == tmp_path / "state.sqlite"
