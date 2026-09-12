from datetime import date, timedelta
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import httpx
import pandas as pd

from sipsa.config import PROJECT_ROOT
from sipsa.sources.base import RAW_COLUMNS


PAGE_URL = "https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/mayoristas-boletin-semanal-1/boletin-mayorista-semanal-2026"


def _key(value: object) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _find_column(columns, *needles: str):
    for column in columns:
        normalized = _key(column)
        if any(needle in normalized for needle in needles):
            return column
    return None


class ExcelDaneAdapter:
    """Descubre y lee anexos semanales XLS/XLSX publicados por el DANE."""

    name = "excel_dane"

    def __init__(self, raw_dir: Path | None = None, timeout: float = 30.0):
        self.raw_dir = raw_dir or PROJECT_ROOT / "data" / "raw"
        self.timeout = timeout
        self._urls: list[str] | None = None

    def discover_urls(self) -> list[str]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(PAGE_URL)
            response.raise_for_status()
        hrefs = re.findall(r"href=[\"']([^\"']+\.(?:xlsx?|XLSX?)(?:\?[^\"']*)?)[\"']", response.text)
        urls = list(dict.fromkeys(urljoin(PAGE_URL, href.replace("&amp;", "&")) for href in hrefs))
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        (self.raw_dir / "sources.json").write_text(
            json.dumps({"excel_dane": urls, "discovered_at": pd.Timestamp.utcnow().isoformat()}, indent=2),
            encoding="utf-8",
        )
        self._urls = urls
        return urls

    def available(self) -> bool:
        try:
            return bool(self.discover_urls())
        except (httpx.HTTPError, OSError):
            return False

    def _read_workbook(self, content: bytes, week: date) -> pd.DataFrame:
        rows = []
        workbook = pd.ExcelFile(BytesIO(content))
        for sheet in workbook.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet)
            product = _find_column(frame.columns, "producto", "articulo")
            market = _find_column(frame.columns, "mercado", "plaza")
            city = _find_column(frame.columns, "ciudad")
            average = _find_column(frame.columns, "promedio", "medio")
            minimum = _find_column(frame.columns, "minimo")
            maximum = _find_column(frame.columns, "maximo")
            if product is None or average is None or (market is None and city is None):
                continue
            for item in frame.to_dict("records"):
                market_value = str(item.get(market, "")) if market else str(item.get(city, ""))
                city_value = str(item.get(city, "")) if city else market_value.split(",")[0]
                rows.append({
                    "fecha": week,
                    "producto_raw": item.get(product),
                    "mercado_raw": market_value,
                    "ciudad_raw": city_value,
                    "precio_prom": item.get(average),
                    "precio_min": item.get(minimum) if minimum else None,
                    "precio_max": item.get(maximum) if maximum else None,
                    "unidad_raw": "kg",
                    "fuente": self.name,
                })
        return pd.DataFrame(rows, columns=RAW_COLUMNS)

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame:
        urls = self._urls if self._urls is not None else self.discover_urls()
        last_monday = hasta - timedelta(days=hasta.weekday())
        frames = []
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for index, url in enumerate(urls):
                week = last_monday - timedelta(weeks=index)
                if week < desde:
                    break
                response = client.get(url)
                response.raise_for_status()
                frames.append(self._read_workbook(response.content, week))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RAW_COLUMNS)

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None:
        return None
