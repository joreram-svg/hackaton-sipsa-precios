import asyncio
import json
from pathlib import Path

from sipsa.telegram_ui.data_provider import FixtureTelegramDataProvider


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "web" / "fixtures"


def test_fixture_provider_marca_toda_respuesta_como_demo():
    provider = FixtureTelegramDataProvider(FIXTURE_ROOT)

    payload = asyncio.run(provider.summary("Bogotá", "small_business"))

    assert payload.demo is True
    assert payload.text
    assert payload.metadata["city"] == "Bogotá"
    assert payload.metadata["audience"] == "small_business"


def test_fixtures_tienen_forma_minima():
    for name in ["ciudades", "productos", "resumen", "tendencia", "comparacion"]:
        data = json.loads(
            (FIXTURE_ROOT / f"{name}.json").read_text(encoding="utf-8")
        )
        assert data["mode"] == "demo"
        assert data["data"]


def test_busqueda_demo_es_tolerante_a_mayusculas_y_acentos():
    provider = FixtureTelegramDataProvider(FIXTURE_ROOT)

    payload = asyncio.run(provider.search_products("platano"))

    assert payload.demo is True
    assert "Plátano" in payload.text
