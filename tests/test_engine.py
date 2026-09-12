from datetime import date, timedelta
import unittest

from abasto_ai.engine import FeatureEngine
from abasto_ai.models import PriceObservation
from abasto_ai.repository import InMemoryPriceRepository


def rows():
    today = date(2026, 9, 12)
    data = []
    for product, base, step in [("papa", 3000, -50), ("tomate", 2000, 80), ("yuca", 2500, -10)]:
        for offset in range(14):
            data.append({"fecha": str(today - timedelta(days=13 - offset)), "ciudad": "Bogotá", "producto": product, "precio": base + offset * step, "unidad": "kg", "central": "Corabastos"})
    return data


def engine():
    return FeatureEngine(InMemoryPriceRepository(rows()), substitutions={"tomate": ["papa", "yuca"]})


class FeatureEngineTests(unittest.TestCase):
    def test_spanish_schema_is_normalized(self):
        item = PriceObservation.from_row(rows()[0])
        self.assertEqual(item.city, "Bogotá")
        self.assertEqual(item.unit, "kg")

    def test_consumer_features_include_actionable_sections(self):
        snapshot = engine().consumer_snapshot(city="Bogotá", as_of=date(2026, 9, 12), basket=["papa", "tomate"])
        self.assertTrue(snapshot["cheap_today"])
        self.assertEqual(snapshot["weekly_price_drops"][0]["product"], "papa")
        self.assertEqual(snapshot["daily_basket"]["total"], "5390")
        self.assertEqual(snapshot["weekly_basket"]["complete_days"], 7)

    def test_forecast_and_alert_detect_price_rise(self):
        snapshot = engine().consumer_snapshot(city="Bogotá", as_of=date(2026, 9, 12))
        tomate = next(item for item in snapshot["buy_before_rise"] if item["product"] == "tomate")
        self.assertEqual(tomate["forecast_7d"]["signal"], "SUBIR")
        self.assertTrue(any(item["product"] == "tomate" for item in snapshot["alerts"]))

    def test_substitutes_and_index(self):
        alternatives = engine().substitutes(city="Bogotá", product="tomate", as_of=date(2026, 9, 12))
        self.assertEqual([item["product"] for item in alternatives], ["papa", "yuca"])
        self.assertEqual(alternatives[0]["estimated_saving"], "690")
        index = engine().abasto_index(city="Bogotá", as_of=date(2026, 9, 12))
        self.assertIsNotNone(index)
        self.assertNotEqual(index["value"], 0)

    def test_market_comparison(self):
        result = engine().compare_markets(city="Bogotá", product="papa", as_of=date(2026, 9, 12))
        self.assertEqual(result, [{"market": "Corabastos", "price": "2350", "unit": "kg", "date": "2026-09-12"}])
