from datetime import date
from typing import Protocol

import pandas as pd


RAW_COLUMNS = [
    "fecha",
    "producto_raw",
    "mercado_raw",
    "ciudad_raw",
    "precio_prom",
    "precio_min",
    "precio_max",
    "unidad_raw",
    "fuente",
]


class SourceAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame: ...

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None: ...

