from datetime import date
from pathlib import Path
from uuid import uuid4

import pandas as pd

from scripts.load_real_data_to_supabase import prepare_price_rows, prepare_supply_rows


def test_prepare_price_rows_adapta_csv_real_y_reporta_no_mapeados():
    """Detecta columnas SIPSA mal adaptadas, ciudad sin normalizar o conteo de descarte incorrecto."""
    raw = pd.DataFrame([
        {"fecha": "2026-09-09", "ciudad": "BOGOTA, D.C.", "cod_producto": 1,
         "producto": "Papa pastusa", "precio_kg": 1000},
        {"fecha": "2026-09-10", "ciudad": "BOGOTÁ, D.C.", "cod_producto": 1,
         "producto": "Papa pastusa", "precio_kg": 1200},
        {"fecha": "2026-09-10", "ciudad": "CALI", "cod_producto": 999,
         "producto": "Producto imposible", "precio_kg": 900},
    ])

    unmapped_path = Path("data") / f"test-loader-price-{uuid4().hex}.csv"
    try:
        rows, unmapped = prepare_price_rows(raw, unmapped_path)
        assert rows.to_dict("records") == [{
            "fecha": date(2026, 9, 7), "producto_id": "papa_pastusa", "ciudad": "Bogotá",
            "precio": 1100.0, "fuente": "soap_dane",
        }]
        assert unmapped == 1
    finally:
        unmapped_path.unlink(missing_ok=True)


def test_prepare_supply_rows_adapta_fuente_y_suma_mercados():
    """Detecta ciudad_fuente conservada como mercado o toneladas mensuales sin agregar."""
    raw = pd.DataFrame([
        {"fecha": "2026-07-01", "ciudad_fuente": "Medellín, Central Mayorista de Antioquia",
         "producto": "Papa pastusa", "toneladas": 8},
        {"fecha": "2026-07-01", "ciudad_fuente": "MEDELLIN, Plaza Minorista",
         "producto": "Papa pastusa", "toneladas": 3},
    ])

    unmapped_path = Path("data") / f"test-loader-supply-{uuid4().hex}.csv"
    try:
        rows, unmapped = prepare_supply_rows(raw, unmapped_path)
        assert rows.to_dict("records") == [{
            "fecha": date(2026, 7, 1), "producto_id": "papa_pastusa", "ciudad": "Medellín",
            "toneladas": 11, "fuente": "soap_dane",
        }]
        assert unmapped == 0
    finally:
        unmapped_path.unlink(missing_ok=True)
