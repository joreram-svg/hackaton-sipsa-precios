"""Fuentes intercambiables para la presentación del bot."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx


API_AUDIENCE = {"consumer": "consumidor", "small_business": "restaurante"}


class DataUnavailable(RuntimeError):
    """La fuente seleccionada no pudo responder con datos utilizables."""


@dataclass(frozen=True, slots=True)
class UiPayload:
    text: str
    demo: bool
    metadata: dict[str, object] = field(default_factory=dict)


class TelegramDataProvider(Protocol):
    async def list_cities(self) -> UiPayload: ...

    async def search_products(self, query: str) -> UiPayload: ...

    async def summary(self, city: str, audience: str) -> UiPayload: ...

    async def trend(self, product_id: str, city: str) -> UiPayload: ...

    async def compare_cities(self, product_id: str) -> UiPayload: ...


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


class FixtureTelegramDataProvider:
    """Proveedor local para validar la interfaz sin depender del backend."""

    def __init__(self, fixture_root: Path | str):
        self.fixture_root = Path(fixture_root)

    def _data(self, name: str) -> list[dict[str, Any]]:
        try:
            document = json.loads(
                (self.fixture_root / f"{name}.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise DataUnavailable(f"Fixture no disponible: {name}") from error
        if document.get("mode") != "demo" or not isinstance(document.get("data"), list):
            raise DataUnavailable(f"Fixture inválido: {name}")
        return document["data"]

    async def list_cities(self) -> UiPayload:
        cities = self._data("ciudades")
        text = "Ciudades disponibles\n" + "\n".join(
            f"• {city['name']}" for city in cities
        )
        return UiPayload(text=text, demo=True, metadata={"cities": cities})

    async def search_products(self, query: str) -> UiPayload:
        needle = _normalized(query.strip())
        products = [
            product
            for product in self._data("productos")
            if needle and needle in _normalized(product["name"])
        ]
        if products:
            text = "Productos encontrados\n" + "\n".join(
                f"• {product['name']} · {product['unit']}" for product in products
            )
        else:
            text = "No encontramos productos con esa búsqueda."
        return UiPayload(
            text=text,
            demo=True,
            metadata={"query": query, "products": products},
        )

    async def summary(self, city: str, audience: str) -> UiPayload:
        entry = next(
            (
                item
                for item in self._data("resumen")
                if item["city"] == city and item["audience"] == audience
            ),
            None,
        )
        if entry is None:
            raise DataUnavailable("No existe un resumen demo para esta selección")
        text = f"{entry['title']}\n" + "\n".join(f"• {line}" for line in entry["lines"])
        return UiPayload(
            text=text,
            demo=True,
            metadata={"city": city, "audience": audience},
        )

    async def trend(self, product_id: str, city: str) -> UiPayload:
        entry = next(
            (
                item
                for item in self._data("tendencia")
                if item["product_id"] == product_id and item["city"] == city
            ),
            None,
        )
        if entry is None:
            raise DataUnavailable("No existe una tendencia demo para esta selección")
        text = f"{entry['title']}\n" + "\n".join(f"• {line}" for line in entry["lines"])
        return UiPayload(text=text, demo=True, metadata={"city": city, "product_id": product_id})

    async def compare_cities(self, product_id: str) -> UiPayload:
        entry = next(
            (item for item in self._data("comparacion") if item["product_id"] == product_id),
            None,
        )
        if entry is None:
            raise DataUnavailable("No existe una comparación demo para esta selección")
        text = f"{entry['title']}\n" + "\n".join(f"• {line}" for line in entry["lines"])
        return UiPayload(text=text, demo=True, metadata={"product_id": product_id})


class ApiTelegramDataProvider:
    """Adaptador HTTP estricto: los errores no se sustituyen por datos demo."""

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def _request(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> UiPayload:
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise DataUnavailable("La fuente de datos no está disponible") from error

        if not isinstance(payload, dict):
            raise DataUnavailable("La API devolvió un formato no reconocido")
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise DataUnavailable("La API no devolvió contenido presentable")
        metadata = payload.get("metadata", {})
        return UiPayload(
            text=text,
            demo=False,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    async def list_cities(self) -> UiPayload:
        return await self._request("/v1/ciudades")

    async def search_products(self, query: str) -> UiPayload:
        return await self._request("/v1/productos", params={"q": query})

    async def summary(self, city: str, audience: str) -> UiPayload:
        return await self._request(
            "/v1/resumen",
            params={"ciudad": city, "perfil": API_AUDIENCE[audience]},
        )

    async def trend(self, product_id: str, city: str) -> UiPayload:
        return await self._request(
            f"/v1/tendencia/{product_id}", params={"ciudad": city}
        )

    async def compare_cities(self, product_id: str) -> UiPayload:
        return await self._request(f"/v1/comparacion/{product_id}")
