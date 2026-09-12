from datetime import date

from sipsa.sources.seed import SeedAdapter


def test_seed_cubre_catalogo_mercados_y_104_semanas():
    """Detecta una semilla incompleta, no semanal o no determinista."""
    adapter = SeedAdapter()
    first = adapter.fetch_precios(date(2024, 1, 1), date(2025, 12, 28))
    second = adapter.fetch_precios(date(2024, 1, 1), date(2025, 12, 28))

    assert len(first) == 104 * 40 * 5
    assert first["fecha"].nunique() == 104
    assert first["producto_raw"].nunique() == 40
    assert first["mercado_raw"].nunique() == 5
    assert set(first["fuente"]) == {"seed"}
    assert all(value.weekday() == 0 for value in first["fecha"].unique())
    assert first.equals(second)
