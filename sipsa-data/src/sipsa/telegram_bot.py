"""Punto de entrada del bot de Telegram de Baskio."""

from __future__ import annotations

import logging
from typing import Any

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from sipsa.config import PROJECT_ROOT, Settings, get_settings
from sipsa.telegram_ui.data_provider import (
    ApiTelegramDataProvider,
    FixtureTelegramDataProvider,
)
from sipsa.telegram_ui.handlers import (
    change_profile,
    handle_action,
    search_message,
    select_city,
    select_profile,
    show_home,
    start,
)
from sipsa.telegram_ui.state import PreferenceStore


logger = logging.getLogger(__name__)


def build_application(
    settings: Settings,
    provider: Any = None,
    store: Any = None,
) -> Application:
    """Compone el bot sin abrir conexiones ni iniciar long polling."""
    if provider is None:
        if settings.telegram_data_mode == "demo":
            provider = FixtureTelegramDataProvider(PROJECT_ROOT / "web" / "fixtures")
        else:
            provider = ApiTelegramDataProvider(settings.telegram_api_base_url)
    if store is None:
        store = PreferenceStore(settings.telegram_state_path)
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["provider"] = provider
    application.bot_data["store"] = store
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("inicio", show_home))
    application.add_handler(CommandHandler("perfil", change_profile))
    application.add_handler(CallbackQueryHandler(select_profile, pattern=r"^profile:"))
    application.add_handler(CallbackQueryHandler(select_city, pattern=r"^city:"))
    application.add_handler(
        CallbackQueryHandler(handle_action, pattern=r"^(consumer|business|common):")
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))
    return application


def main() -> int:
    """Inicia el bot cuando existe un token y degrada de forma segura sin él."""
    settings = get_settings()
    if not settings.telegram_bot_token.strip():
        logger.warning("TELEGRAM_BOT_TOKEN no configurado; el bot no se iniciará")
        return 0

    application = build_application(settings)
    application.run_polling(drop_pending_updates=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
