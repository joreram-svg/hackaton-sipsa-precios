import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from sipsa.config import PROJECT_ROOT, Settings, get_settings
from sipsa.db.backend import open_database
from sipsa.db.postgres import copy_upsert, upsert_catalog
from sipsa.ingest.normalize import normalize_abastecimiento, normalize_prices
from sipsa.sources.excel_dane import ExcelDaneAdapter
from sipsa.sources.seed import SeedAdapter
from sipsa.sources.soap_dane import SUPPLY_COLUMNS, SoapDaneAdapter
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
    if settings.db_backend == "postgres":
        with open_database(settings) as database:
            database.execute(
                (PROJECT_ROOT / "src" / "sipsa" / "db" / "schema_postgres.sql").read_text(encoding="utf-8")
            )
            cursor = database.connection.cursor()
            try:
                upsert_catalog(cursor)
            finally:
                cursor.close()
        return

    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(settings.db_path)) as conn:
        _migrate_legacy_market_schema(conn)
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "schema.sql").read_text(encoding="utf-8"))
        productos = pd.read_csv(PROJECT_ROOT / "src" / "sipsa" / "catalog" / "productos.csv")
        productos["alias"] = productos["alias"].fillna("").map(lambda value: value.split("|")).map(json.dumps)
        conn.register("productos_df", productos)
        conn.execute("INSERT OR REPLACE INTO dim_producto SELECT * FROM productos_df")
        conn.execute((PROJECT_ROOT / "src" / "sipsa" / "db" / "views.sql").read_text(encoding="utf-8"))


def _configured_adapters(settings: Settings) -> list:
    factories = {
        "excel_dane": lambda: ExcelDaneAdapter(Path(settings.db_path).parent / "raw"),
        "soap_dane": lambda: SoapDaneAdapter(cache_dir=PROJECT_ROOT / "data" / "raw"),
        "socrata": lambda: SocrataAdapter(settings.socrata_dataset_id),
        "seed": SeedAdapter,
    }
    return [factories[name]() for name in settings.source_names if name in factories]


def _select_rows(
    source: str,
    settings: Settings,
    desde: date,
    hasta: date,
    adapters: list | None,
    has_existing: bool,
):
    seed_raw = SeedAdapter().fetch_precios(desde, hasta)
    seed_rows = normalize_prices(seed_raw)
    if source == "seed":
        return seed_rows, seed_raw, "seed", [], None

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
            if real_rows.empty:
                if adapter.name == "soap_dane" and has_existing:
                    return real_rows, raw, adapter.name, errors, adapter
                errors.append(f"{adapter.name}: sin filas normalizadas")
                continue
            combined = pd.concat([real_rows, seed_rows], ignore_index=True)
            combined = combined.drop_duplicates(["fecha", "producto_id", "ciudad"], keep="first")
            return combined, raw, adapter.name, errors, adapter
        except Exception as exc:  # cada fuente externa debe degradar a la siguiente
            LOGGER.warning("Fuente %s no disponible: %s", adapter.name, exc)
            errors.append(f"{adapter.name}: {type(exc).__name__}: {exc}")
    return seed_rows, seed_raw, "seed", errors, None


def _scalar(settings: Settings, sql: str, params: list | None = None):
    with open_database(settings, read_only=True) as database:
        row = database.execute(sql, params or []).fetchone()
    return row[0] if row else None


def _latest_success_date(settings: Settings) -> date | None:
    return _scalar(
        settings,
        """SELECT max(semanas_max) FROM ingest_log
        WHERE status='ok' AND fuente IN ('soap_dane','csv_real')""",
    )


def _latest_fact_date(settings: Settings, table: str) -> date | None:
    if table not in {"fact_precio", "fact_abastecimiento"}:
        raise ValueError("Tabla de hechos no permitida")
    return _scalar(settings, f"SELECT max(fecha) FROM {table}")


def _raw_date_range(raw: pd.DataFrame) -> tuple[date | None, date | None]:
    if raw.empty or "fecha" not in raw:
        return None, None
    values = pd.to_datetime(raw["fecha"], errors="coerce").dropna()
    if values.empty:
        return None, None
    return values.min().date(), values.max().date()


def _upsert_duckdb(conn, rows: pd.DataFrame, supply: pd.DataFrame) -> tuple[dict, dict]:
    price_stats = {"inserted": 0, "updated": 0, "total": len(rows)}
    if not rows.empty:
        conn.register("incoming_prices", rows)
        existing = conn.execute(
            "SELECT count(*) FROM fact_precio f JOIN incoming_prices i USING(fecha, producto_id, ciudad)"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO fact_precio BY NAME SELECT * FROM incoming_prices
            ON CONFLICT (fecha, producto_id, ciudad) DO UPDATE SET
              precio=excluded.precio, fuente=excluded.fuente, ingested_at=now()"""
        )
        price_stats = {"inserted": len(rows) - existing, "updated": existing, "total": len(rows)}

    supply_stats = {"inserted": 0, "updated": 0, "total": len(supply)}
    if not supply.empty:
        conn.register("incoming_supply", supply)
        existing = conn.execute(
            "SELECT count(*) FROM fact_abastecimiento f JOIN incoming_supply i USING(fecha, producto_id, ciudad)"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO fact_abastecimiento BY NAME SELECT * FROM incoming_supply
            ON CONFLICT (fecha, producto_id, ciudad) DO UPDATE SET
              toneladas=excluded.toneladas, fuente=excluded.fuente"""
        )
        supply_stats = {"inserted": len(supply) - existing, "updated": existing, "total": len(supply)}
    return price_stats, supply_stats


def _write_ingest(
    settings: Settings,
    rows: pd.DataFrame,
    supply: pd.DataFrame,
    log_values: list,
) -> tuple[dict, dict]:
    if settings.db_backend == "postgres":
        with open_database(settings) as database:
            cursor = database.connection.cursor()
            try:
                price_stats = copy_upsert(
                    cursor,
                    rows,
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
            finally:
                cursor.close()
            database.execute(
                "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok', NULL)",
                [
                    *log_values[:4],
                    price_stats["inserted"],
                    price_stats["updated"],
                    *log_values[4:],
                ],
            )
        return price_stats, supply_stats

    with duckdb.connect(str(settings.db_path)) as conn:
        price_stats, supply_stats = _upsert_duckdb(conn, rows, supply)
        conn.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok', NULL)",
            [
                *log_values[:4],
                price_stats["inserted"],
                price_stats["updated"],
                *log_values[4:],
            ],
        )
    return price_stats, supply_stats


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
    if source == "auto":
        latest_log = _latest_success_date(settings)
        if latest_log is not None:
            desde = max(desde, latest_log + timedelta(days=1))
    has_existing = bool(_scalar(settings, "SELECT EXISTS(SELECT 1 FROM fact_precio LIMIT 1)"))
    rows, raw, active_source, errors, active_adapter = _select_rows(
        source, settings, desde, hasta, adapters, has_existing
    )

    raw_dir = Path(settings.db_path).parent / "raw" if settings.db_backend == "duckdb" else PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"precios_{run_id}.parquet"
    raw.to_parquet(raw_file, index=False)

    supply_raw = pd.DataFrame(columns=SUPPLY_COLUMNS)
    supply = pd.DataFrame(columns=["fecha", "producto_id", "ciudad", "toneladas", "fuente"])
    raw_supply_file = None
    if active_adapter is not None:
        supply_since = _latest_fact_date(settings, "fact_abastecimiento")
        supply_since = supply_since + timedelta(days=1) if supply_since else desde
        supply_raw = active_adapter.fetch_abastecimiento(supply_since, hasta)
        if supply_raw is not None and not supply_raw.empty:
            supply = normalize_abastecimiento(supply_raw)
            raw_supply_file = raw_dir / f"abastecimiento_{run_id}.parquet"
            supply_raw.to_parquet(raw_supply_file, index=False)

    weeks_min, weeks_max = _raw_date_range(raw)
    price_stats, supply_stats = _write_ingest(
        settings,
        rows,
        supply,
        [run_id, started, datetime.now(), active_source, weeks_min, weeks_max],
    )
    return {
        "run_id": run_id,
        "status": "ok",
        "filas_insertadas": price_stats["inserted"],
        "filas_actualizadas": price_stats["updated"],
        "filas_abastecimiento_insertadas": supply_stats["inserted"],
        "filas_abastecimiento_actualizadas": supply_stats["updated"],
        "fuente": active_source,
        "source_errors": errors,
        "raw_file": str(raw_file),
        "raw_supply_file": str(raw_supply_file) if raw_supply_file else None,
    }
