from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from sipsa.sources.base import RAW_COLUMNS


CATALOG_DIR = Path(__file__).resolve().parents[1] / "catalog"


class SeedAdapter:
    """Genera 104 semanas deterministas y realistas para toda la demo."""

    name = "seed"

    def available(self) -> bool:
        return True

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame:
        productos = pd.read_csv(CATALOG_DIR / "productos.csv")
        mercados = pd.read_csv(CATALOG_DIR / "mercados.csv")
        ultimo_lunes = hasta - timedelta(days=hasta.weekday())
        primer_lunes = ultimo_lunes - timedelta(weeks=103)
        fechas = [primer_lunes + timedelta(weeks=index) for index in range(104)]
        fechas = [fecha for fecha in fechas if desde <= fecha <= hasta]
        rng = np.random.default_rng(42)
        category_base = {
            "tuberculos": 2600,
            "verduras": 3300,
            "frutas": 4200,
            "granos": 6500,
            "procesados": 7200,
            "carnes": 18000,
            "lacteos": 8000,
        }
        marked = {"papa_pastusa": 0.30, "tomate_chonto": 0.34, "cebolla_cabezona": 0.28, "cebolla_larga": 0.26}
        market_factor = {
            "bogota_corabastos": 1.00,
            "medellin_cma": 1.04,
            "cali_cavasa": 0.98,
            "barranquilla_granabastos": 1.10,
            "bucaramanga_centroabastos": 0.96,
        }
        rows: list[dict] = []
        for product_index, producto in productos.iterrows():
            base = category_base[producto.categoria] * (0.78 + (product_index % 9) * 0.055)
            amplitude = marked.get(producto.producto_id, 0.10)
            phase = (product_index % 13) / 13 * 2 * np.pi
            trend = ((product_index % 7) - 3) * 0.0007
            for week_index, fecha in enumerate(fechas):
                seasonal = 1 + amplitude * np.sin(2 * np.pi * week_index / 26 + phase)
                yearly = 1 + 0.045 * np.sin(2 * np.pi * week_index / 52 + phase / 2)
                for _, mercado in mercados.iterrows():
                    noise = rng.normal(0, 0.025)
                    value = max(500.0, base * seasonal * yearly * (1 + trend * week_index) * market_factor[mercado.mercado_id] * (1 + noise))
                    rows.append(
                        {
                            "fecha": fecha,
                            "producto_raw": producto.producto_id,
                            "mercado_raw": mercado.mercado_id,
                            "ciudad_raw": mercado.ciudad,
                            "precio_prom": round(value, 2),
                            "precio_min": round(value * 0.93, 2),
                            "precio_max": round(value * 1.07, 2),
                            "unidad_raw": "kg",
                            "fuente": self.name,
                        }
                    )
        return pd.DataFrame(rows, columns=RAW_COLUMNS)

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None:
        return None

