from datetime import date
import unittest

from abasto_ai.condensed import condensed_recommendation


def row(kind, items, status="disponible"):
    return {"tipo": kind, "estado": status, "contenido": {"items": items}}


class CondensedRecommendationTests(unittest.TestCase):
    def test_consumer_summary_is_actionable_and_profile_specific(self):
        text = condensed_recommendation(
            "consumer",
            city="Bogotá",
            as_of=date(2026, 9, 7),
            recommendations=[
                row("favorables_comprar", [{"producto": "Banano"}, {"producto": "Zanahoria"}]),
                row("comprar_antes_de_subir", [{"producto": "Limón Tahití"}]),
            ],
        )
        self.assertIn("Banano y Zanahoria", text)
        self.assertIn("Limón Tahití", text)
        self.assertIn("canasta", text)

    def test_retailer_and_restaurant_use_their_own_language(self):
        retailer = condensed_recommendation(
            "retailer", city="Cali", as_of=date(2026, 9, 7),
            recommendations=[row("ranking_oportunidades", [{"producto": "Papa"}])],
        )
        restaurant = condensed_recommendation(
            "restaurant", city="Cali", as_of=date(2026, 9, 7),
            recommendations=[row("ingredientes_precio_favorable", [{"ingrediente": "Tomate"}])],
        )
        self.assertIn("tienda", retailer)
        self.assertIn("cocina", restaurant)
        self.assertIn("Tomate", restaurant)
        self.assertNotIn("en;", retailer)
        self.assertNotIn("en;", restaurant)

    def test_unavailable_rows_do_not_invent_products(self):
        text = condensed_recommendation(
            "restaurant", city="Tunja", as_of=date(2026, 9, 7),
            recommendations=[row("menu_del_dia", [{"ingrediente": "Inventado"}], "requiere_configuracion")],
        )
        self.assertNotIn("Inventado", text)
        self.assertIn("Aún no hay señales", text)
