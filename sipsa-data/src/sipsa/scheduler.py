import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sipsa.config import Settings, get_settings
from sipsa.ingest.pipeline import run_ingest
from sipsa.snapshot import make_snapshot


LOGGER = logging.getLogger(__name__)


def refresh_data(settings: Settings | None = None) -> dict:
    """Ejecuta ingesta y snapshot como una sola tarea programada."""
    settings = settings or get_settings()
    ingest = run_ingest("auto", settings)
    files = make_snapshot(settings)
    from sipsa.telegram_bot import send_daily_push_sync

    telegram_sent = send_daily_push_sync(settings)
    LOGGER.info("Actualización SIPSA completada: %s", ingest["run_id"])
    return {"ingest": ingest, "snapshot_files": files, "telegram_sent": telegram_sent}


def create_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        refresh_data,
        CronTrigger(hour=6, minute=0, timezone=settings.tz),
        kwargs={"settings": settings},
        id="sipsa_daily_refresh",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
