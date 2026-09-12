from pathlib import Path
import logging
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sipsa.config import Settings


def test_telegram_settings_tienen_defaults_seguros(tmp_path: Path):
    settings = Settings(_env_file=None, telegram_state_path=tmp_path / "ui.sqlite")

    assert settings.telegram_bot_token == ""
    assert settings.telegram_data_mode == "demo"
    assert settings.telegram_api_base_url == "http://127.0.0.1:8000"
    assert settings.telegram_state_path == tmp_path / "ui.sqlite"


def test_bot_sin_token_sale_sin_error(monkeypatch, caplog):
    from sipsa import telegram_bot

    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: Settings(_env_file=None, telegram_bot_token=""),
    )
    caplog.set_level(logging.WARNING)

    assert telegram_bot.main() == 0
    assert "TELEGRAM_BOT_TOKEN no configurado" in caplog.text


def test_build_application_no_inicia_red_y_inyecta_dependencias(tmp_path: Path):
    from sipsa.telegram_bot import build_application

    settings = Settings(
        _env_file=None,
        telegram_bot_token="0:test",
        telegram_state_path=tmp_path / "ui.sqlite",
    )
    provider = object()
    store = object()

    application = build_application(settings, provider=provider, store=store)

    assert application.bot.token == settings.telegram_bot_token
    assert application.bot_data["provider"] is provider
    assert application.bot_data["store"] is store
    assert application.running is False


def test_preferencias_persisten_entre_instancias(tmp_path: Path):
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    state_path = tmp_path / "ui.sqlite"
    first_store = PreferenceStore(state_path)

    defaults = first_store.get(101)
    assert defaults.profile is None
    assert defaults.city == "Bogotá"
    assert defaults.last_menu == "onboarding"

    first_store.set_profile(101, UserProfile.CONSUMER)
    first_store.set_city(101, "Medellín")
    first_store.set_last_menu(101, "consumer:today")

    restored = PreferenceStore(state_path).get(101)
    assert restored.profile is UserProfile.CONSUMER
    assert restored.city == "Medellín"
    assert restored.last_menu == "consumer:today"


def test_menus_de_consumidor_y_negocio_son_diferentes():
    from sipsa.telegram_ui.menus import business_menu, consumer_menu, profile_menu

    def texts(markup):
        return [button.text for row in markup.inline_keyboard for button in row]

    def callbacks(markup):
        return [button.callback_data for row in markup.inline_keyboard for button in row]

    consumer = consumer_menu()
    business = business_menu()
    profiles = profile_menu()

    assert "Precios de hoy" in texts(consumer)
    assert "Resumen del negocio" not in texts(consumer)
    assert "Resumen del negocio" in texts(business)
    assert "Precios de hoy" not in texts(business)
    assert callbacks(profiles) == ["profile:consumer", "profile:small_business"]
    assert "common:profile" in callbacks(consumer)
    assert "common:profile" in callbacks(business)


def _make_update(callback_data=None, text=None):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=42),
        message=SimpleNamespace(text=text, reply_text=AsyncMock()),
        callback_query=SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        ),
    )


def _make_context(store, provider):
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"store": store, "provider": provider})
    )


def test_start_pide_perfil_a_chat_nuevo(tmp_path: Path):
    from sipsa.telegram_ui.handlers import start
    from sipsa.telegram_ui.state import PreferenceStore

    update = _make_update()
    context = _make_context(PreferenceStore(tmp_path / "ui.sqlite"), object())

    asyncio.run(start(update, context))

    text = update.message.reply_text.await_args.args[0]
    assert "¿Cómo usarás el servicio?" in text
    assert update.message.reply_text.await_args.kwargs["reply_markup"] is not None


def test_onboarding_y_home_presentan_la_marca_baskio(tmp_path: Path):
    from sipsa.telegram_ui.handlers import select_profile, start
    from sipsa.telegram_ui.state import PreferenceStore

    store = PreferenceStore(tmp_path / "ui.sqlite")
    context = _make_context(store, object())
    onboarding = _make_update()
    home_update = _make_update("profile:consumer")

    asyncio.run(start(onboarding, context))
    asyncio.run(select_profile(home_update, context))

    assert "Baskio" in onboarding.message.reply_text.await_args.args[0]
    assert "Baskio · Consumidor" in home_update.callback_query.edit_message_text.await_args.args[0]


def test_cambiar_perfil_reemplaza_menu(tmp_path: Path):
    from sipsa.telegram_ui.handlers import select_profile
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    store = PreferenceStore(tmp_path / "ui.sqlite")
    store.set_profile(42, UserProfile.CONSUMER)
    update = _make_update("profile:small_business")
    context = _make_context(store, object())

    asyncio.run(select_profile(update, context))

    assert store.get(42).profile is UserProfile.SMALL_BUSINESS
    text = update.callback_query.edit_message_text.await_args.args[0]
    assert "Resumen del negocio" in text
    assert "Precios de hoy" not in text


def test_accion_demo_muestra_etiqueta_y_conserva_navegacion(tmp_path: Path):
    from sipsa.telegram_ui.data_provider import UiPayload
    from sipsa.telegram_ui.handlers import handle_action
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    store = PreferenceStore(tmp_path / "ui.sqlite")
    store.set_profile(42, UserProfile.CONSUMER)
    provider = SimpleNamespace(summary=AsyncMock(return_value=UiPayload("Contenido", True)))
    update = _make_update("consumer:today")

    asyncio.run(handle_action(update, _make_context(store, provider)))

    text = update.callback_query.edit_message_text.await_args.args[0]
    assert text.startswith("🧪 Modo demo · datos simulados")
    callbacks = [
        button.callback_data
        for row in update.callback_query.edit_message_text.await_args.kwargs[
            "reply_markup"
        ].inline_keyboard
        for button in row
    ]
    assert "common:home" in callbacks


def test_error_de_ciudades_conserva_la_accion_para_reintentar(tmp_path: Path):
    from sipsa.telegram_ui.data_provider import DataUnavailable
    from sipsa.telegram_ui.handlers import handle_action
    from sipsa.telegram_ui.state import PreferenceStore, UserProfile

    store = PreferenceStore(tmp_path / "ui.sqlite")
    store.set_profile(42, UserProfile.CONSUMER)
    provider = SimpleNamespace(
        list_cities=AsyncMock(side_effect=DataUnavailable("sin datos"))
    )
    update = _make_update("common:city")

    asyncio.run(handle_action(update, _make_context(store, provider)))

    assert store.get(42).last_menu == "common:city"
    callbacks = [
        button.callback_data
        for row in update.callback_query.edit_message_text.await_args.kwargs[
            "reply_markup"
        ].inline_keyboard
        for button in row
    ]
    assert "common:retry" in callbacks
