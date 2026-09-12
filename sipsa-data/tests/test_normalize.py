from datetime import date
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from sipsa.config import Settings
from sipsa.ingest.pipeline import initialize_database, run_ingest
from sipsa.ingest.normalize import normalize_prices
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


def test_normalize_mapea_unidades_agrega_mercados_y_registra_no_mapeados():
    """Detecta precios sin convertir, duplicación por mercado o pérdida de no mapeados."""
    unmapped_path = Path("data") / f"test-unmapped-{uuid4().hex}.csv"
    raw = pd.DataFrame([
        {"fecha": date(2026, 9, 9), "producto_raw": "Pápa Pastusa", "mercado_raw": "m1",
         "ciudad_raw": "Bogotá", "precio_prom": 1000, "precio_min": None, "precio_max": None,
         "unidad_raw": "kg", "fuente": "test"},
        {"fecha": date(2026, 9, 9), "producto_raw": "papa negra", "mercado_raw": "m2",
         "ciudad_raw": "Bogotá", "precio_prom": 600, "precio_min": None, "precio_max": None,
         "unidad_raw": "lb", "fuente": "test"},
        {"fecha": date(2026, 9, 9), "producto_raw": "Producto imposible", "mercado_raw": "m3",
         "ciudad_raw": "Bogotá", "precio_prom": 999, "precio_min": None, "precio_max": None,
         "unidad_raw": "kg", "fuente": "test"},
    ])
    try:
        result = normalize_prices(raw, unmapped_path=unmapped_path)
        assert result.to_dict("records") == [{
            "fecha": date(2026, 9, 7), "producto_id": "papa_pastusa", "ciudad": "Bogotá",
            "precio": 1100.0, "fuente": "test",
        }]
        assert pd.read_csv(unmapped_path)["producto_raw"].tolist() == ["Producto imposible"]
    finally:
        unmapped_path.unlink(missing_ok=True)


def test_auto_conserva_filas_reales_y_completa_huecos_con_seed():
    """Detecta que el fallback reemplace datos reales o deje el histórico incompleto."""
    class ShortRealAdapter:
        name = "real_test"

        def available(self):
            return True

        def fetch_precios(self, desde, hasta):
            monday = hasta - pd.Timedelta(days=hasta.weekday())
            rows = []
            for weeks, price in ((0, 1234), (1, 1200)):
                rows.append({
                    "fecha": monday - pd.Timedelta(weeks=weeks), "producto_raw": "papa pastusa",
                    "mercado_raw": "m1", "ciudad_raw": "Bogotá", "precio_prom": price,
                    "precio_min": None, "precio_max": None, "unidad_raw": "kg", "fuente": self.name,
                })
            return pd.DataFrame(rows)

        def fetch_abastecimiento(self, desde, hasta):
            return None

    db_path = Path("data") / f"test-auto-{uuid4().hex}.duckdb"
    try:
        result = run_ingest("auto", Settings(db_path=db_path), adapters=[ShortRealAdapter()])
        with duckdb.connect(str(db_path), read_only=True) as conn:
            counts = dict(conn.execute("SELECT fuente,count(*) FROM fact_precio GROUP BY fuente").fetchall())
        assert result["fuente"] == "real_test"
        assert counts["real_test"] == 2
        assert counts["seed"] == 104 * 40 * 3 - 2
    finally:
        Path(result["raw_file"]).unlink(missing_ok=True) if "result" in locals() else None
        db_path.unlink(missing_ok=True)
