from datetime import date
from pathlib import Path
from uuid import uuid4

import duckdb

from sipsa.config import Settings
from sipsa.ingest.pipeline import initialize_database
from sipsa.sources.seed import SeedAdapter


def test_seed_cubre_catalogo_ciudades_y_104_semanas():
    """Detecta una semilla incompleta, no semanal o no determinista."""
    adapter = SeedAdapter()
    first = adapter.fetch_precios(date(2024, 1, 1), date(2025, 12, 28))
    second = adapter.fetch_precios(date(2024, 1, 1), date(2025, 12, 28))

    assert len(first) == 104 * 40 * 3
    assert first["fecha"].nunique() == 104
    assert first["producto_raw"].nunique() == 40
    assert first["ciudad_raw"].nunique() == 3
    assert set(first["fuente"]) == {"seed"}
    assert all(value.weekday() == 0 for value in first["fecha"].unique())
    assert first.equals(second)


def test_initialize_database_migra_mercados_a_precio_promedio_por_ciudad():
    """Detecta pérdida de datos o conservación accidental de la dimensión mercado."""
    db_path = Path("data") / f"test-legacy-{uuid4().hex}.duckdb"
    try:
        with duckdb.connect(str(db_path)) as conn:
            conn.execute("CREATE TABLE dim_mercado(mercado_id VARCHAR, nombre VARCHAR, ciudad VARCHAR)")
            conn.execute("INSERT INTO dim_mercado VALUES ('m1','Uno','Bogotá'),('m2','Dos','Bogotá')")
            conn.execute("""CREATE TABLE fact_precio(
                fecha DATE, producto_id VARCHAR, mercado_id VARCHAR, precio_prom DOUBLE,
                precio_min DOUBLE, precio_max DOUBLE, fuente VARCHAR, ingested_at TIMESTAMP
            )""")
            conn.execute("""INSERT INTO fact_precio VALUES
                ('2026-09-07','papa_pastusa','m1',2000,1900,2100,'seed',now()),
                ('2026-09-07','papa_pastusa','m2',2400,2300,2500,'seed',now())
            """)

        initialize_database(Settings(db_path=db_path))

        with duckdb.connect(str(db_path), read_only=True) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info('fact_precio')").fetchall()]
            row = conn.execute("SELECT fecha,producto_id,ciudad,precio,fuente FROM fact_precio").fetchone()
            tables = {item[0] for item in conn.execute("SHOW TABLES").fetchall()}
        assert columns == ["fecha", "producto_id", "ciudad", "precio", "fuente", "ingested_at"]
        assert row[:4] == (date(2026, 9, 7), "papa_pastusa", "Bogotá", 2200.0)
        assert "dim_mercado" not in tables
    finally:
        db_path.unlink(missing_ok=True)
