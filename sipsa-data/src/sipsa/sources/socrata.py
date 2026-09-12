from datetime import date

import httpx
import pandas as pd

from sipsa.sources.base import RAW_COLUMNS


class SocrataAdapter:
    """Pagina un dataset Socrata configurable y adapta columnas SIPSA comunes."""

    name = "socrata"

    def __init__(self, dataset_id: str, timeout: float = 30.0):
        self.dataset_id = dataset_id.strip()
        self.timeout = timeout
        self.url = f"https://www.datos.gov.co/resource/{self.dataset_id}.json"

    def available(self) -> bool:
        return bool(self.dataset_id)

    @staticmethod
    def _value(row: dict, *names: str):
        for name in names:
            if name in row and row[name] not in (None, ""):
                return row[name]
        return None

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame:
        rows = []
        offset = 0
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            while True:
                response = client.get(self.url, params={"$limit": 50000, "$offset": offset})
                response.raise_for_status()
                page = response.json()
                if not page:
                    break
                for item in page:
                    rows.append({
                        "fecha": self._value(item, "fecha", "fecha_captura", "fecha_semana"),
                        "producto_raw": self._value(item, "producto", "nombre_producto"),
                        "mercado_raw": self._value(item, "mercado", "plaza", "mercado_mayorista"),
                        "ciudad_raw": self._value(item, "ciudad", "municipio"),
                        "precio_prom": self._value(item, "precio_promedio", "precio_prom", "precio"),
                        "precio_min": self._value(item, "precio_minimo", "precio_min"),
                        "precio_max": self._value(item, "precio_maximo", "precio_max"),
                        "unidad_raw": self._value(item, "unidad", "unidad_medida") or "kg",
                        "fuente": self.name,
                    })
                offset += len(page)
                if len(page) < 50000:
                    break
        frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
        if not frame.empty:
            dates = pd.to_datetime(frame["fecha"], errors="coerce").dt.date
            frame = frame[(dates >= desde) & (dates <= hasta)].copy()
        return frame

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None:
        return None
