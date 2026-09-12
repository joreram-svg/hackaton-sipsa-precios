import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from sipsa.config import PROJECT_ROOT, Settings, get_settings
from sipsa.ingest.normalize import normalize_prices
from sipsa.sources.excel_dane import ExcelDaneAdapter
from sipsa.sources.seed import SeedAdapter
from sipsa.sources.soap_dane import SoapDaneAdapter
from sipsa.sources.socrata import SocrataAdapter


VIEW_NAMES = ("v_tendencia", "v_percentil", "v_variacion", "v_ultima_semana")
LOGGER = logging.getLogger(__name__)


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


def _configured_adapters(settings: Settings) -> list:
    factories = {
        "excel_dane": lambda: ExcelDaneAdapter(Path(settings.db_path).parent / "raw"),
        "soap_dane": SoapDaneAdapter,
        "socrata": lambda: SocrataAdapter(settings.socrata_dataset_id),
        "seed": SeedAdapter,
    }
    return [factories[name]() for name in settings.source_names if name in factories]


def _select_rows(source: str, settings: Settings, desde: date, hasta: date, adapters: list | None):
    seed_raw = SeedAdapter().fetch_precios(desde, hasta)
    seed_rows = normalize_prices(seed_raw)
    if source == "seed":
        return seed_rows, seed_raw, "seed", []

    errors = []
    for adapter in adapters if adapters is not None else _configured_adapters(settings):
        if adapter.name == "seed":
            continue
        try:
            if not adapter.available():
                errors.append(f"{adapter.name}: no disponible")
                continue
            raw = adapter.fetch_precios(desde, hasta)
            real_rows = normalize_prices(raw)
            real_rows = real_rows[real_rows["ciudad"].isin(settings.city_names)]
            if real_rows.empty:
                errors.append(f"{adapter.name}: sin filas normalizadas")
                continue
            combined = pd.concat([real_rows, seed_rows], ignore_index=True)
            combined = combined.drop_duplicates(["fecha", "producto_id", "ciudad"], keep="first")
            return combined, raw, adapter.name, errors
        except Exception as exc:  # cada fuente externa debe degradar a la siguiente
            LOGGER.warning("Fuente %s no disponible: %s", adapter.name, exc)
            errors.append(f"{adapter.name}: {type(exc).__name__}: {exc}")
    return seed_rows, seed_raw, "seed", errors


def run_ingest(
    source: str = "seed",
    settings: Settings | None = None,
    adapters: list | None = None,
) -> dict:
    settings = settings or get_settings()
    initialize_database(settings)
    run_id = str(uuid4())
    started = datetime.now()
    hasta = date.today()
    desde = hasta - timedelta(weeks=settings.hist_weeks - 1, days=6)
    if source not in {"seed", "auto"}:
        raise ValueError(f"Fuente no soportada: {source}")
    rows, raw, active_source, errors = _select_rows(source, settings, desde, hasta, adapters)
    raw_dir = Path(settings.db_path).parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"precios_{run_id}.parquet"
    raw.to_parquet(raw_file, index=False)
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
            [run_id, started, datetime.now(), active_source, inserted, existing, rows.fecha.min(), rows.fecha.max()],
        )
    return {
        "run_id": run_id,
        "status": "ok",
        "filas_insertadas": inserted,
        "filas_actualizadas": existing,
        "fuente": active_source,
        "source_errors": errors,
        "raw_file": str(raw_file),
    }
