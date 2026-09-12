from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from sipsa.config import PROJECT_ROOT, Settings, get_settings
from sipsa.sources.seed import SeedAdapter


def initialize_database(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(settings.db_path)) as conn:
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "schema.sql").read_text(encoding="utf-8"))
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "views.sql").read_text(encoding="utf-8"))
        productos = pd.read_csv(PROJECT_ROOT / "src" / "sipsa" / "catalog" / "productos.csv")
        productos["alias"] = productos["alias"].fillna("").map(lambda value: value.split("|")).map(__import__("json").dumps)
        mercados = pd.read_csv(PROJECT_ROOT / "src" / "sipsa" / "catalog" / "mercados.csv")
        conn.register("productos_df", productos)
        conn.register("mercados_df", mercados)
        conn.execute("INSERT OR REPLACE INTO dim_producto SELECT * FROM productos_df")
        conn.execute("INSERT OR REPLACE INTO dim_mercado SELECT * FROM mercados_df")


def run_ingest(source: str = "seed", settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    initialize_database(settings)
    run_id = str(uuid4())
    started = datetime.now()
    hasta = date.today()
    desde = hasta - timedelta(weeks=settings.hist_weeks - 1, days=6)
    if source not in {"seed", "auto"}:
        raise ValueError(f"Fuente no soportada todavía: {source}")
    adapter = SeedAdapter()
    raw = adapter.fetch_precios(desde, hasta)
    normalized = raw.rename(columns={"producto_raw": "producto_id", "mercado_raw": "mercado_id"})
    rows = normalized[["fecha", "producto_id", "mercado_id", "precio_prom", "precio_min", "precio_max", "fuente"]]
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(raw_dir / f"precios_{run_id}.parquet", index=False)
    with duckdb.connect(str(settings.db_path)) as conn:
        conn.register("incoming", rows)
        existing = conn.execute(
            "SELECT count(*) FROM fact_precio f JOIN incoming i USING(fecha, producto_id, mercado_id)"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO fact_precio BY NAME SELECT * FROM incoming
            ON CONFLICT (fecha, producto_id, mercado_id) DO UPDATE SET
              precio_prom=excluded.precio_prom, precio_min=excluded.precio_min,
              precio_max=excluded.precio_max, fuente=excluded.fuente, ingested_at=now()
            """
        )
        inserted = len(rows) - existing
        conn.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok', NULL)",
            [run_id, started, datetime.now(), adapter.name, inserted, existing, rows.fecha.min(), rows.fecha.max()],
        )
    return {"run_id": run_id, "status": "ok", "filas_insertadas": inserted, "filas_actualizadas": existing, "fuente": adapter.name}
