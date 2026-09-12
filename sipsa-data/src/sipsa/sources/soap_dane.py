from collections.abc import Callable
from datetime import date, datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from sipsa.config import PROJECT_ROOT
from sipsa.sources.base import RAW_COLUMNS


SERVICE_URL = "https://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService"
WSDL_URL = f"{SERVICE_URL}?WSDL"
SUPPLY_COLUMNS = ["fecha", "producto_raw", "ciudad_raw", "toneladas", "fuente"]


class SoapDaneAdapter:
    """Consulta el histórico SIPSA, lo filtra localmente y limita cada descarga a una diaria."""

    name = "soap_dane"

    def __init__(
        self,
        timeout: float = 120.0,
        cache_dir: Path | None = None,
        client_factory: Callable | None = None,
    ):
        self.timeout = timeout
        self.cache_dir = cache_dir or PROJECT_ROOT / "data" / "raw"
        self.client_factory = client_factory

    def available(self) -> bool:
        return self.client_factory is not None or importlib.util.find_spec("zeep") is not None

    def _create_client(self):
        if self.client_factory is not None:
            return self.client_factory()
        from requests import Session
        from zeep import Client, Settings as ZeepSettings
        from zeep.transports import Transport

        session = Session()
        transport = Transport(session=session, timeout=self.timeout, operation_timeout=self.timeout)
        client = Client(WSDL_URL, transport=transport, settings=ZeepSettings(strict=False, xml_huge_tree=True))
        return SimpleNamespace(service=self._bind_soap12(client))

    @staticmethod
    def _bind_soap12(client):
        from zeep.wsdl.bindings.soap import Soap12Binding

        binding = next(
            (item for item in client.wsdl.bindings.values() if isinstance(item, Soap12Binding)),
            None,
        )
        if binding is None:
            raise RuntimeError("El WSDL SIPSA no publicó un binding SOAP 1.2")
        return client.create_service(binding.name, SERVICE_URL)

    @staticmethod
    def _flatten(value):
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, dict):
            for key in ("return", "items", "item", "result"):
                if key in value:
                    return SoapDaneAdapter._flatten(value[key])
            return [value]
        return []

    @staticmethod
    def _serialize(response):
        if isinstance(response, (dict, list, tuple)):
            return response
        from zeep.helpers import serialize_object

        return serialize_object(response)

    @staticmethod
    def _filter_dates(frame: pd.DataFrame, desde: date, hasta: date) -> pd.DataFrame:
        if frame.empty:
            return frame
        frame = frame.copy()
        frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce").dt.date
        return frame[frame["fecha"].between(desde, hasta)].reset_index(drop=True)

    @staticmethod
    def _cache_is_today(path: Path) -> bool:
        return path.exists() and datetime.fromtimestamp(path.stat().st_mtime).date() == date.today()

    def _load_or_fetch(self, cache_name: str, operation_name: str, parser: Callable) -> pd.DataFrame:
        cache_path = self.cache_dir / cache_name
        if self._cache_is_today(cache_path):
            return pd.read_parquet(cache_path)
        client = self._create_client()
        operation = getattr(client.service, operation_name)
        response = operation()
        frame = parser(self._serialize(response))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache_path, index=False)
        return frame

    def _parse_prices(self, serialized) -> pd.DataFrame:
        rows = []
        for item in self._flatten(serialized):
            if not isinstance(item, dict):
                continue
            rows.append({
                "fecha": item.get("fechaCaptura"),
                "producto_raw": item.get("producto"),
                "mercado_raw": item.get("ciudad"),
                "ciudad_raw": item.get("ciudad"),
                "precio_prom": item.get("precioPromedio"),
                "precio_min": None,
                "precio_max": None,
                "unidad_raw": "kg",
                "fuente": self.name,
            })
        return pd.DataFrame(rows, columns=RAW_COLUMNS)

    def _parse_supply(self, serialized) -> pd.DataFrame:
        rows = []
        for item in self._flatten(serialized):
            if not isinstance(item, dict):
                continue
            rows.append({
                "fecha": item.get("fechaMesIni"),
                "producto_raw": item.get("artiNombre"),
                "ciudad_raw": item.get("fuenNombre"),
                "toneladas": item.get("cantidadTon"),
                "fuente": self.name,
            })
        return pd.DataFrame(rows, columns=SUPPLY_COLUMNS)

    def fetch_precios(self, desde: date, hasta: date) -> pd.DataFrame:
        if not self.available():
            return pd.DataFrame(columns=RAW_COLUMNS)
        frame = self._load_or_fetch(
            "soap_precios_cache.parquet", "promediosSipsaCiudad", self._parse_prices
        )
        return self._filter_dates(frame, desde, hasta)

    def fetch_abastecimiento(self, desde: date, hasta: date) -> pd.DataFrame:
        if not self.available():
            return pd.DataFrame(columns=SUPPLY_COLUMNS)
        frame = self._load_or_fetch(
            "soap_abastecimiento_cache.parquet", "promedioAbasSipsaMesMadr", self._parse_supply
        )
        return self._filter_dates(frame, desde, hasta)
