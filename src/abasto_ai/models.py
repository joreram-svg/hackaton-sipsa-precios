from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """A normalized food price observation from any data source."""

    date: date
    city: str
    product: str
    price: Decimal
    market: str | None = None
    category: str | None = None
    unit: str = "unidad"
    product_id: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.city.casefold(), self.product_id or self.product.casefold(), self.unit.casefold())

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "PriceObservation":
        def value(*names: str, required: bool = False, default: Any = None) -> Any:
            for name in names:
                if row.get(name) not in (None, ""):
                    return row[name]
            if required:
                raise ValueError(f"Missing required price field: {names[0]}")
            return default

        raw_date = value("date", "fecha", required=True)
        parsed_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date)[:10])
        raw_price = value("price", "precio", required=True)
        price = Decimal(str(raw_price))
        if price < 0:
            raise ValueError("Price cannot be negative")
        return cls(
            date=parsed_date,
            city=str(value("city", "ciudad", required=True)).strip(),
            product=str(value("product", "producto", required=True)).strip(),
            price=price,
            market=_text(value("market", "central", "mercado")),
            category=_text(value("category", "categoria", "categoría")),
            unit=str(value("unit", "unidad", default="unidad")).strip(),
            product_id=_text(value("product_id", "producto_id")),
        )


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value).strip()
