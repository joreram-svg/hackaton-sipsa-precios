import asyncio
import logging
import unicodedata

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from sipsa.config import Settings, get_settings
from sipsa.db.repo import Repository
from sipsa.ingest.normalize import match_producto
from sipsa.service import build_weekly_summary


LOGGER = logging.getLogger(__name__)
PROFILES = {"consumidor", "restaurante", "mayorista"}


def _plain(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _resolve_city(value: str | None, repo: Repository) -> str:
    cities = [item["ciudad"] for item in repo.list_cities()]
    if not cities:
        return "Bogotá"
    if not value:
        return "Bogotá" if "Bogotá" in cities else cities[0]
    lookup = {_plain(city): city for city in cities}
    if _plain(value) not in lookup:
        raise LookupError(f"Ciudad no disponible: {value}")
    return lookup[_plain(value)]


def summary_text(repo: Repository, ciudad: str = "Bogotá", perfil: str = "consumidor") -> str:
    """Devuelve exactamente el texto que compone el servicio REST."""
    return build_weekly_summary(repo, ciudad, perfil)["texto"]


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Hola. Soy SIPSA Data. Usa /hoy [ciudad] [perfil], "
            "/precio <producto> o /alertas [ciudad]."
        )


async def hoy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    repo = Repository()
    args = list(context.args)
    perfil = args.pop().lower() if args and args[-1].lower() in PROFILES else "consumidor"
    try:
        ciudad = _resolve_city(" ".join(args) if args else None, repo)
        text = summary_text(repo, ciudad, perfil)
    except LookupError as exc:
        text = str(exc)
    if update.effective_message:
        await update.effective_message.reply_text(text)


async def precio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /precio <producto>")
        return
    producto_id = match_producto(" ".join(context.args))
    if not producto_id:
        await update.effective_message.reply_text("Producto no encontrado. Prueba con el nombre completo.")
        return
    repo = Repository()
    trend = repo.trend(producto_id, _resolve_city(None, repo), 12)
    current = trend["serie"][-1]["precio"]
    await update.effective_message.reply_text(
        f"{producto_id.replace('_', ' ').title()}: ${current:,.0f} COP/kg. "
        f"1 semana {float(trend['var_1w_pct'] or 0):+.1%}; "
        f"4 semanas {float(trend['var_4w_pct'] or 0):+.1%}."
    )


async def alertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    repo = Repository()
    try:
        ciudad = _resolve_city(" ".join(context.args) if context.args else None, repo)
        alerts = repo.alerts(ciudad, 15, "1w")["alertas"]
        if alerts:
            lines = [
                f"{'↑' if item['direccion'] == 'SUBE' else '↓'} {item['nombre']}: {item['var_pct']:+.1%}"
                for item in alerts
            ]
            text = f"Alertas SIPSA {ciudad}:\n" + "\n".join(lines)
        else:
            text = f"Sin alertas superiores a 15% en {ciudad}."
    except LookupError as exc:
        text = str(exc)
    await update.effective_message.reply_text(text)


def build_application(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("hoy", hoy_command))
    application.add_handler(CommandHandler("precio", precio_command))
    application.add_handler(CommandHandler("alertas", alertas_command))
    return application


async def send_daily_push(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id_values:
        LOGGER.info("Push Telegram omitido: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_IDS")
        return 0
    repo = Repository(settings)
    city = settings.city_names[0] if settings.city_names else "Bogotá"
    text = summary_text(repo, city, "consumidor")
    sent = 0
    async with Bot(settings.telegram_bot_token) as bot:
        for chat_id in settings.telegram_chat_id_values:
            await bot.send_message(chat_id=chat_id, text=text)
            sent += 1
    return sent


def send_daily_push_sync(settings: Settings | None = None) -> int:
    return asyncio.run(send_daily_push(settings))


def main(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not settings.telegram_bot_token:
        LOGGER.warning("TELEGRAM_BOT_TOKEN no está configurado; el bot no se inicia")
        return 0
    build_application(settings).run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
