import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pandas as pd
from dotenv import load_dotenv
import psycopg2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sipsa.ingest.normalize import map_product_ids, normalize_abastecimiento, normalize_prices
from sipsa.db.postgres import copy_upsert, upsert_catalog


PRICE_CSV = ROOT / "data" / "raw" / "sipsa_precios_ciudad_real_2020_2026.csv"
SUPPLY_CSV = ROOT / "data" / "raw" / "sipsa_abastecimiento_real.csv"
UNMAPPED_CSV = ROOT / "data" / "raw" / "unmapped.csv"
SCHEMA_SQL = ROOT / "src" / "sipsa" / "db" / "schema_postgres.sql"


def prepare_price_rows(raw: pd.DataFrame, unmapped_path: Path = UNMAPPED_CSV) -> tuple[pd.DataFrame, int]:
    """Adapta las columnas del CSV de precios al normalizador común."""
    required = {"fecha", "ciudad", "producto", "precio_kg"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Faltan columnas en CSV de precios: {sorted(missing)}")
    product_ids = map_product_ids(raw["producto"])
    adapted = pd.DataFrame({
        "fecha": raw["fecha"],
        "producto_raw": raw["producto"],
        "mercado_raw": raw["ciudad"],
        "ciudad_raw": raw["ciudad"],
        "precio_prom": raw["precio_kg"],
        "precio_min": None,
        "precio_max": None,
        "unidad_raw": "kg",
        "fuente": "soap_dane",
    })
    return normalize_prices(adapted, unmapped_path=unmapped_path), int(product_ids.isna().sum())


def prepare_supply_rows(raw: pd.DataFrame, unmapped_path: Path = UNMAPPED_CSV) -> tuple[pd.DataFrame, int]:
    """Adapta abastecimiento SIPSA y agrega sus mercados al nivel de ciudad."""
    required = {"fecha", "ciudad_fuente", "producto", "toneladas"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Faltan columnas en CSV de abastecimiento: {sorted(missing)}")
    product_ids = map_product_ids(raw["producto"])
    adapted = pd.DataFrame({
        "fecha": raw["fecha"],
        "producto_raw": raw["producto"],
        "ciudad_raw": raw["ciudad_fuente"],
        "toneladas": raw["toneladas"],
        "fuente": "soap_dane",
    })
    return normalize_abastecimiento(adapted, unmapped_path=unmapped_path), int(product_ids.isna().sum())


def load_real_data(
    price_csv: Path = PRICE_CSV,
    supply_csv: Path = SUPPLY_CSV,
    unmapped_csv: Path = UNMAPPED_CSV,
) -> dict:
    """Normaliza ambos CSV y los carga de forma idempotente en Supabase."""
    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL no está configurada en .env")
    started = datetime.now()
    prices, unmapped_prices = prepare_price_rows(pd.read_csv(price_csv), unmapped_csv)
    supply, unmapped_supply = prepare_supply_rows(pd.read_csv(supply_csv), unmapped_csv)
    run_id = str(uuid4())

    with psycopg2.connect(url, connect_timeout=15, application_name="sipsa_real_loader") as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
            upsert_catalog(cursor)
            price_stats = copy_upsert(
                cursor,
                prices,
                table="fact_precio",
                key_columns=["fecha", "producto_id", "ciudad"],
                update_columns=["precio", "fuente"],
            )
            supply_stats = copy_upsert(
                cursor,
                supply,
                table="fact_abastecimiento",
                key_columns=["fecha", "producto_id", "ciudad"],
                update_columns=["toneladas", "fuente"],
            )
            cursor.execute(
                """INSERT INTO ingest_log(run_id,started_at,finished_at,fuente,filas_insertadas,
                   filas_actualizadas,semanas_min,semanas_max,status,error)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'ok',NULL)""",
                (
                    run_id,
                    started,
                    datetime.now(),
                    "csv_real",
                    price_stats["inserted"] + supply_stats["inserted"],
                    price_stats["updated"] + supply_stats["updated"],
                    prices["fecha"].min(),
                    prices["fecha"].max(),
                ),
            )
            cursor.execute("SELECT count(*),min(fecha),max(fecha),count(DISTINCT ciudad) FROM fact_precio")
            price_final = cursor.fetchone()
            cursor.execute("SELECT count(*),min(fecha),max(fecha),count(DISTINCT ciudad) FROM fact_abastecimiento")
            supply_final = cursor.fetchone()

    return {
        "run_id": run_id,
        "fact_precio": price_stats,
        "fact_abastecimiento": supply_stats,
        "unmapped": {"precios": unmapped_prices, "abastecimiento": unmapped_supply},
        "final": {
            "fact_precio": {
                "rows": price_final[0], "min_date": price_final[1],
                "max_date": price_final[2], "cities": price_final[3],
            },
            "fact_abastecimiento": {
                "rows": supply_final[0], "min_date": supply_final[1],
                "max_date": supply_final[2], "cities": supply_final[3],
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga los CSV reales SIPSA en Supabase")
    parser.parse_args()
    result = load_real_data()
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
