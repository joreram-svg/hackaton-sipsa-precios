from datetime import date
import importlib.util

import pandas as pd

from sipsa.sources.base import RAW_COLUMNS


WSDL_URL = "https://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService?WSDL"


class SoapDaneAdapter:
    """Consulta el servicio SOAP SIPSA con importación diferida de zeep."""

    name = "soap_dane"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def available(self) -> bool:
        return importlib.util.find_spec("zeep") is not None

    @staticmethod
    def _flatten(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("return", "items", "item", "result"):
                if key in value:
                    return SoapDaneAdapter._flatten(value[key])
            return [value]
        return []

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame:
        if not self.available():
            return pd.DataFrame(columns=RAW_COLUMNS)
        from requests import Session
        from zeep import Client, Settings as ZeepSettings
        from zeep.helpers import serialize_object
        from zeep.transports import Transport

        session = Session()
        transport = Transport(session=session, timeout=self.timeout, operation_timeout=self.timeout)
        client = Client(WSDL_URL, transport=transport, settings=ZeepSettings(strict=False))
        operation = None
        for name in ("promediosSipsaCiudad", "promediosSipsaSemanaMadr", "promediosSipsaParcial"):
            if hasattr(client.service, name):
                operation = getattr(client.service, name)
                break
        if operation is None:
            return pd.DataFrame(columns=RAW_COLUMNS)
        try:
            response = operation(fechaInicio=desde.isoformat(), fechaFin=hasta.isoformat())
        except TypeError:
            response = operation(desde.isoformat(), hasta.isoformat())
        serialized = serialize_object(response)
        rows = []
        for item in self._flatten(serialized):
            if not isinstance(item, dict):
                continue
            rows.append({
                "fecha": item.get("fecha") or item.get("fechaSemana"),
                "producto_raw": item.get("producto") or item.get("nombreProducto"),
                "mercado_raw": item.get("mercado") or item.get("nombreMercado"),
                "ciudad_raw": item.get("ciudad") or item.get("nombreCiudad"),
                "precio_prom": item.get("precioPromedio") or item.get("promedio"),
                "precio_min": item.get("precioMinimo"),
                "precio_max": item.get("precioMaximo"),
                "unidad_raw": item.get("unidad") or "kg",
                "fuente": self.name,
            })
        return pd.DataFrame(rows, columns=RAW_COLUMNS)

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame | None:
        return None
