from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from sipsa.config import PROJECT_ROOT, Settings, get_settings
from sipsa.sources.seed import SeedAdapter


VIEW_NAMES = ("v_tendencia", "v_percentil", "v_variacion", "v_ultima_semana")


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}


def _migrate_legacy_market_schema(conn) -> None:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    if "fact_precio" not in tables or "mercado_id" not in _columns(conn, "fact_precio"):
        return
    for view in VIEW_NAMES:
        conn.execute(f"DROP VIEW IF EXISTS {view}")
    conn.execute("ALTER TABLE fact_precio RENAME TO fact_precio_legacy")
    conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "schema.sql").read_text(encoding="utf-8"))
    if "dim_mercado" in tables:
        city_expression = "coalesce(m.ciudad, f.mercado_id)"
        join = "LEFT JOIN dim_mercado m USING(mercado_id)"
    else:
        city_expression = "f.mercado_id"
        join = ""
    conn.execute(
        f"""
        INSERT INTO fact_precio(fecha, producto_id, ciudad, precio, fuente, ingested_at)
        SELECT f.fecha, f.producto_id, {city_expression}, avg(f.precio_prom),
               coalesce(arg_max(f.fuente, f.ingested_at), 'legacy'), max(f.ingested_at)
        FROM fact_precio_legacy f {join}
        GROUP BY f.fecha, f.producto_id, {city_expression}
        """
    )
    conn.execute("DROP TABLE fact_precio_legacy")
    conn.execute("DROP TABLE IF EXISTS dim_mercado")


def initialize_database(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(settings.db_path)) as conn:
        _migrate_legacy_market_schema(conn)
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "schema.sql").read_text(encoding="utf-8"))
        productos = pd.read_csv(PROJECT_ROOT / "src" / "sipsa" / "catalog" / "productos.csv")
        productos["alias"] = productos["alias"].fillna("").map(lambda value: value.split("|")).map(__import__("json").dumps)
        conn.register("productos_df", productos)
        conn.execute("INSERT OR REPLACE INTO dim_producto SELECT * FROM productos_df")
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "views.sql").read_text(encoding="utf-8"))


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
    normalized = raw.rename(
        columns={"producto_raw": "producto_id", "ciudad_raw": "ciudad", "precio_prom": "precio"}
    )
    rows = (
        normalized[["fecha", "producto_id", "ciudad", "precio", "fuente"]]
        .groupby(["fecha", "producto_id", "ciudad", "fuente"], as_index=False)["precio"]
        .mean()
    )
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(raw_dir / f"precios_{run_id}.parquet", index=False)
    with duckdb.connect(str(settings.db_path)) as conn:
        conn.register("incoming", rows)
        existing = conn.execute(
            "SELECT count(*) FROM fact_precio f JOIN incoming i USING(fecha, producto_id, ciudad)"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO fact_precio BY NAME SELECT * FROM incoming
            ON CONFLICT (fecha, producto_id, ciudad) DO UPDATE SET
              precio=excluded.precio, fuente=excluded.fuente, ingested_at=now()
            """
        )
        inserted = len(rows) - existing
        conn.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok', NULL)",
            [run_id, started, datetime.now(), adapter.name, inserted, existing, rows.fecha.min(), rows.fecha.max()],
        )
    return {"run_id": run_id, "status": "ok", "filas_insertadas": inserted, "filas_actualizadas": existing, "fuente": adapter.name}
