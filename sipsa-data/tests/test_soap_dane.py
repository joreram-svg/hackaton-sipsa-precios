from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from zeep.wsdl.bindings.soap import Soap12Binding

from sipsa.sources.soap_dane import SERVICE_URL, SoapDaneAdapter


class FakeSoapService:
    def __init__(self):
        self.price_calls = 0
        self.supply_calls = 0

    def promediosSipsaCiudad(self):
        self.price_calls += 1
        return [
            {"ciudad": "BOGOTÁ, D.C.", "producto": "Papa pastusa", "precioPromedio": 2000,
             "fechaCaptura": "2026-09-08", "codProducto": 1, "regId": 10},
            {"ciudad": "CALI", "producto": "Papa pastusa", "precioPromedio": 2100,
             "fechaCaptura": "2026-09-10", "codProducto": 1, "regId": 11},
        ]

    def promedioAbasSipsaMesMadr(self):
        self.supply_calls += 1
        return [
            {"artiId": 1, "artiNombre": "Papa pastusa", "cantidadTon": 12.5,
             "fechaMesIni": "2026-07-01", "fuenNombre": "Cali, Cavasa", "futiId": 20}
        ]


class FakeClient:
    def __init__(self, service):
        self.service = service


def test_soap_selecciona_binding_12_y_endpoint_confirmado():
    """Detecta que zeep use accidentalmente un puerto SOAP 1.1 del WSDL."""
    binding = object.__new__(Soap12Binding)
    binding.name = "soap12-binding"

    class BindingClient:
        wsdl = SimpleNamespace(bindings={"soap12": binding})

        def __init__(self):
            self.created = None

        def create_service(self, name, address):
            self.created = (name, address)
            return "soap12-service"

    client = BindingClient()

    service = SoapDaneAdapter._bind_soap12(client)

    assert service == "soap12-service"
    assert client.created == ("soap12-binding", SERVICE_URL)


def test_soap_llama_sin_parametros_filtra_fechas_y_cachea_un_dia():
    """Detecta firmas SOAP antiguas, falta de filtro incremental o descargas repetidas el mismo día."""
    cache_dir = Path("data") / f"test-soap-cache-{uuid4().hex}"
    service = FakeSoapService()
    adapter = SoapDaneAdapter(cache_dir=cache_dir, client_factory=lambda: FakeClient(service))
    try:
        prices = adapter.fetch_precios(date(2026, 9, 9), date(2026, 9, 11))
        cached = adapter.fetch_precios(date(2026, 9, 8), date(2026, 9, 8))
        supply = adapter.fetch_abastecimiento(date(2026, 7, 1), date(2026, 7, 31))

        assert prices[["fecha", "producto_raw", "ciudad_raw", "precio_prom"]].to_dict("records") == [{
            "fecha": date(2026, 9, 10), "producto_raw": "Papa pastusa",
            "ciudad_raw": "CALI", "precio_prom": 2100,
        }]
        assert cached["fecha"].tolist() == [date(2026, 9, 8)]
        assert supply[["fecha", "producto_raw", "ciudad_raw", "toneladas"]].to_dict("records") == [{
            "fecha": date(2026, 7, 1), "producto_raw": "Papa pastusa",
            "ciudad_raw": "Cali, Cavasa", "toneladas": 12.5,
        }]
        assert service.price_calls == 1
        assert service.supply_calls == 1
    finally:
        for name in ("soap_precios_cache.parquet", "soap_abastecimiento_cache.parquet"):
            (cache_dir / name).unlink(missing_ok=True)
        cache_dir.rmdir()
