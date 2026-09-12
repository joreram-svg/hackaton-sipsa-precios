from datetime import date, datetime
import json
from pathlib import Path
import re
import unicodedata

from sipsa.config import Settings, get_settings
from sipsa.db.repo import Repository
from sipsa.service import build_weekly_summary


PROFILES = ("consumidor", "restaurante", "mayorista")


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def snapshot_path(kind: str, ciudad: str, perfil: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.db_path).parent / "snapshot" / f"{kind}_{_slug(ciudad)}_{perfil}.json"


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"No serializable: {type(value).__name__}")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, default=_json_default), encoding="utf-8")
    temporary.replace(path)


def make_snapshot(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    repo = Repository(settings)
    files = []
    for ciudad in settings.city_names:
        for perfil in PROFILES:
            summary_path = snapshot_path("resumen", ciudad, perfil, settings)
            opportunities_path = snapshot_path("oportunidades", ciudad, perfil, settings)
            _write(summary_path, build_weekly_summary(repo, ciudad, perfil))
            _write(opportunities_path, repo.opportunities(ciudad, None, perfil, 10))
            files.extend([str(summary_path), str(opportunities_path)])
    return files


def load_snapshot(kind: str, ciudad: str, perfil: str, settings: Settings | None = None) -> dict:
    path = snapshot_path(kind, ciudad, perfil, settings)
    if not path.exists():
        raise OSError(f"Snapshot no disponible: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
