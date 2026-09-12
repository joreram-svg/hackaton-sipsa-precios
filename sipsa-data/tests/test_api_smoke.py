from datetime import date, timedelta
import importlib
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sipsa.api.main import app, get_repo


class FakeRepository:
    item = {
        "producto_id": "papa_pastusa", "nombre": "Papa pastusa", "categoria": "tuberculos",
        "ciudad": "Bogotá", "precio_actual": 2400.0, "precio_1w": 2500.0,
        "precio_4w": 2800.0, "var_1w_pct": -0.04, "var_4w_pct": -0.1429,
        "percentil_hist": 0.12, "score": 82.0, "senal": "COMPRAR",
        "razon": "14% más barata que hace un mes y en el 12% más bajo de 2 años",
    }

    def health(self):
        return {"status": "ok", "fuente_activa": "seed", "ultima_fecha": date(2026, 9, 7),
                "semanas_disponibles": 104, "pct_seed": 100.0, "productos": 40, "ciudades": 3}

    def list_products(self, categoria=None):
        return [{"producto_id": "papa_pastusa", "nombre": "Papa pastusa", "categoria": "tuberculos", "unidad_base": "kg"}]

    def list_cities(self):
        return [{"ciudad": "Bogotá"}]

    def price_history(self, producto_id, ciudad="Bogotá", desde=None, hasta=None, semanas=None):
        start = date(2025, 8, 4)
        rows = [{"fecha": start + timedelta(weeks=i), "precio_prom": 2200.0 + i * 5,
                 "precio_min": 2100.0, "precio_max": 2400.0, "fuente": "seed"} for i in range(58)]
        return rows[-semanas:] if semanas else rows

    def opportunities(self, city="Bogotá", categoria=None, perfil="consumidor", top=10, ascending=False):
        item = {**self.item, "senal": "EVITAR" if ascending else "COMPRAR"}
        return {"fecha": date(2026, 9, 7), "ciudad": city, "perfil": perfil, "items": [item] * min(top, 5)}

    def trend(self, producto_id, ciudad="Bogotá", semanas=12):
        return {"producto_id": producto_id, "ciudad": ciudad,
                "serie": [{"fecha": date(2026, 9, 7), "precio_prom": 2400.0}],
                "var_1w_pct": -0.04, "var_4w_pct": -0.1429, "var_52w_pct": 0.03,
                "percentil_hist": 0.12, "pendiente_pct_sem": -1.2}

    def alerts(self, city="Bogotá", threshold=15, window="1w"):
        return {"fecha": date(2026, 9, 7), "alertas": [{"producto_id": "tomate_chonto", "nombre": "Tomate chonto",
                "ciudad": city, "var_pct": 0.18, "direccion": "SUBE", "precio_actual": 4200.0}]}

    def compare(self, producto_id):
        return [{"ciudad": "Bogotá", "precio_actual": 2400.0, "var_1w_pct": -0.04}]


def test_todos_los_get_contractuales_responden_200():
    """Detecta rutas faltantes, parámetros incompatibles o respuestas inválidas."""
    app.dependency_overrides[get_repo] = lambda: FakeRepository()
    client = TestClient(app)
    urls = [
        "/v1/health", "/v1/productos", "/v1/ciudades",
        "/v1/precios?producto_id=papa_pastusa",
        "/v1/oportunidades", "/v1/evitar",
        "/v1/tendencia/papa_pastusa", "/v1/forecast/papa_pastusa",
        "/v1/alertas", "/v1/resumen-semanal", "/v1/comparar?producto_id=papa_pastusa",
    ]
    try:
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200, (url, response.text)
            assert response.headers["content-type"].startswith("application/json")
    finally:
        app.dependency_overrides.clear()


def test_resumen_es_legible_corto_y_contiene_cinco_items_por_lado():
    """Detecta un resumen no apto para Telegram o listas incompletas."""
    app.dependency_overrides[get_repo] = lambda: FakeRepository()
    try:
        payload = TestClient(app).get("/v1/resumen-semanal?ciudad=Bogot%C3%A1&perfil=restaurante").json()
        assert len(payload["top_comprar"]) == len(payload["top_evitar"]) == 5
        assert len(payload["texto"]) <= 600
        assert "↑" in payload["texto"] and "↓" in payload["texto"]
        assert "**" not in payload["texto"]
    finally:
        app.dependency_overrides.clear()


def test_errores_de_validacion_siguen_convencion_bad_request():
    """Detecta que FastAPI exponga su error 422 en vez del contrato común."""
    app.dependency_overrides[get_repo] = lambda: FakeRepository()
    try:
        response = TestClient(app).get("/v1/forecast/papa_pastusa?horizonte=9")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"
    finally:
        app.dependency_overrides.clear()


def test_mcp_registra_ocho_tools_y_mejores_precios_responde(monkeypatch):
    """Detecta herramientas MCP omitidas o desacopladas de la lógica interna."""
    class FakeFastMCP:
        def __init__(self, _name):
            self.tools = {}

        def tool(self, function):
            self.tools[function.__name__] = function
            return function

    monkeypatch.setitem(sys.modules, "fastmcp", SimpleNamespace(FastMCP=FakeFastMCP))
    sys.modules.pop("sipsa.mcp.server", None)
    server = importlib.import_module("sipsa.mcp.server")
    expected = {
        "listar_productos", "mejores_precios", "productos_a_evitar", "tendencia_producto",
        "pronostico_producto", "alertas_precio", "resumen_semanal", "comparar_ciudades",
    }
    assert set(server.mcp.tools) == expected
    monkeypatch.setattr(server, "get_repository", lambda: FakeRepository())
    assert server.mejores_precios()["items"][0]["producto_id"] == "papa_pastusa"
