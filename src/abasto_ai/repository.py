from __future__ import annotations

from datetime import date
import os
from typing import Iterable, Protocol

from .models import PriceObservation


class PriceRepository(Protocol):
    def observations(self, *, city: str | None = None, as_of: date | None = None) -> list[PriceObservation]: ...


class InMemoryPriceRepository:
    def __init__(self, rows: Iterable[PriceObservation | dict]):
        self._items = [item if isinstance(item, PriceObservation) else PriceObservation.from_row(item) for item in rows]

    def observations(self, *, city: str | None = None, as_of: date | None = None) -> list[PriceObservation]:
        return [
            item for item in self._items
            if (city is None or item.city.casefold() == city.casefold()) and (as_of is None or item.date <= as_of)
        ]


class SupabasePriceRepository:
    """Lazy Supabase adapter so the core package has no mandatory external dependency."""

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        table: str | None = None,
        city_column: str | None = None,
        date_column: str | None = None,
    ):
        self.url = url or os.environ.get("SUPABASE_URL")
        self.key = key or os.environ.get("SUPABASE_KEY")
        self.table = table or os.environ.get("SUPABASE_PRICE_TABLE", "food_prices")
        self.city_column = city_column or os.environ.get("SUPABASE_CITY_COLUMN", "city")
        self.date_column = date_column or os.environ.get("SUPABASE_DATE_COLUMN", "date")
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")

    def observations(self, *, city: str | None = None, as_of: date | None = None) -> list[PriceObservation]:
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Install the Supabase extra: pip install -e '.[supabase]'") from exc
        query = create_client(self.url, self.key).table(self.table).select("*")
        if city:
            query = query.eq(self.city_column, city)
        if as_of:
            query = query.lte(self.date_column, as_of.isoformat())
        response = query.execute()
        return [PriceObservation.from_row(row) for row in response.data]
