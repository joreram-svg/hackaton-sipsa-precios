from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, pstdev
from typing import Iterable

from .forecast import forecast
from .models import PriceObservation
from .repository import PriceRepository


class FeatureEngine:
    """Query-oriented feature layer shared by consumer, retailer and restaurant surfaces."""

    def __init__(self, repository: PriceRepository, *, substitutions: dict[str, list[str]] | None = None, weekly_alert_threshold: Decimal = Decimal("0.08")):
        self.repository = repository
        self.substitutions = {key.casefold(): [item.casefold() for item in values] for key, values in (substitutions or {}).items()}
        self.weekly_alert_threshold = weekly_alert_threshold

    def consumer_snapshot(self, *, city: str, as_of: date, basket: Iterable[str] = ()) -> dict:
        metrics = self._metrics(city, as_of)
        return {
            "cheap_today": self._rank(metrics, "relative_price", 10),
            "weekly_price_drops": self._rank(metrics, "weekly_change", 10),
            "favorable_to_buy": self._rank([item for item in metrics if item["score"] > 0], "score", 10, reverse=True),
            "buy_before_rise": self._rank([item for item in metrics if item["forecast_signal"] == "SUBIR"], "forecast_change", 10, reverse=True),
            "daily_basket": self.basket(city=city, products=basket, as_of=as_of),
            "weekly_basket": self.weekly_basket(city=city, products=basket, as_of=as_of),
            "alerts": self.alerts(city=city, as_of=as_of),
        }

    def retailer_snapshot(self, *, city: str, as_of: date, basket: Iterable[str] = ()) -> dict:
        metrics = self._metrics(city, as_of)
        opportunities = self._rank([item for item in metrics if item["score"] > 0], "score", 20, reverse=True)
        return {"favorable_basic_basket": self.basket(city=city, products=basket, as_of=as_of), "price_drops": self._rank(metrics, "weekly_change", 20), "buying_opportunities": opportunities, "replenishment": opportunities[:10], "alerts": self.alerts(city=city, as_of=as_of)}

    def restaurant_snapshot(self, *, city: str, as_of: date, ingredients: Iterable[str], recipes: dict[str, dict[str, float]] | None = None) -> dict:
        metrics = self._metrics(city, as_of)
        requested = {item.casefold() for item in ingredients}
        favorable = self._rank([item for item in metrics if item["product"].casefold() in requested and item["score"] > 0], "score", 20, reverse=True)
        menu_costs = self.menu_costs(city=city, recipes=recipes or {}, as_of=as_of)
        return {
            "favorable_ingredients": favorable,
            "seasonal_products": self.seasonal_products(city=city, as_of=as_of, products=ingredients),
            "ingredient_substitutions": {item["product"]: self.substitutes(city=city, product=item["product"], as_of=as_of) for item in favorable},
            "menu_costs": menu_costs,
            "menu_recommendations": sorted([item for item in menu_costs if not item["missing_ingredients"]], key=lambda item: Decimal(item["estimated_ingredient_cost"])),
        }

    def basket(self, *, city: str, products: Iterable[str], as_of: date) -> dict:
        latest = self._latest(self.repository.observations(city=city, as_of=as_of))
        lines, missing = [], []
        for product in products:
            choices = [item for item in latest.values() if item.product.casefold() == product.casefold()]
            if not choices:
                missing.append(product)
                continue
            selected = min(choices, key=lambda item: item.price)
            lines.append({"product": selected.product, "price": str(selected.price), "unit": selected.unit, "market": selected.market})
        total = sum((Decimal(line["price"]) for line in lines), Decimal("0"))
        return {"city": city, "as_of": as_of.isoformat(), "items": lines, "total": str(total), "missing_products": missing}

    def compare_cities(self, *, product: str, cities: Iterable[str], as_of: date, unit: str | None = None) -> list[dict]:
        result = []
        for city in cities:
            choices = [item for item in self._latest(self.repository.observations(city=city, as_of=as_of)).values() if item.product.casefold() == product.casefold() and (unit is None or item.unit.casefold() == unit.casefold())]
            if choices:
                item = min(choices, key=lambda candidate: candidate.price)
                result.append({"city": city, "price": str(item.price), "unit": item.unit, "market": item.market})
        return sorted(result, key=lambda item: Decimal(item["price"]))

    def compare_markets(self, *, city: str, product: str, as_of: date) -> list[dict]:
        """Latest available price by market, lowest first, for a comparable unit."""
        latest = self._latest(self.repository.observations(city=city, as_of=as_of))
        choices = [item for item in latest.values() if item.product.casefold() == product.casefold()]
        return [
            {"market": item.market, "price": str(item.price), "unit": item.unit, "date": item.date.isoformat()}
            for item in sorted(choices, key=lambda item: item.price)
        ]

    def weekly_basket(self, *, city: str, products: Iterable[str], as_of: date) -> dict:
        """Seven daily basket snapshots plus their average cost; quantities belong in recipe/basket configuration."""
        product_list = list(products)
        days = [self.basket(city=city, products=product_list, as_of=as_of - timedelta(days=offset)) for offset in range(6, -1, -1)]
        valid_totals = [Decimal(day["total"]) for day in days if not day["missing_products"]]
        return {
            "city": city,
            "ending": as_of.isoformat(),
            "daily": days,
            "average_daily_cost": str(sum(valid_totals, Decimal("0")) / len(valid_totals)) if valid_totals else None,
            "complete_days": len(valid_totals),
        }

    def substitutes(self, *, city: str, product: str, as_of: date) -> list[dict]:
        candidates = self.substitutions.get(product.casefold(), [])
        latest = self._latest(self.repository.observations(city=city, as_of=as_of))
        original = [item for item in latest.values() if item.product.casefold() == product.casefold()]
        reference = min(original, key=lambda item: item.price).price if original else None
        matches = [item for item in latest.values() if item.product.casefold() in candidates and (reference is None or item.unit.casefold() == min(original, key=lambda item: item.price).unit.casefold())]
        return [{"product": item.product, "price": str(item.price), "unit": item.unit, "market": item.market, "estimated_saving": str(max(Decimal("0"), reference - item.price)) if reference is not None else None} for item in sorted(matches, key=lambda item: item.price)]

    def price_history(self, *, city: str, product: str, as_of: date, days: int = 90) -> list[dict]:
        """Chart-ready daily average series, preserving the units as a separate dimension."""
        grouped: dict[tuple[date, str], list[Decimal]] = defaultdict(list)
        start = as_of - timedelta(days=days)
        for item in self.repository.observations(city=city, as_of=as_of):
            if item.product.casefold() == product.casefold() and item.date >= start:
                grouped[(item.date, item.unit)].append(item.price)
        return [
            {"date": day.isoformat(), "unit": unit, "average_price": str(sum(prices, Decimal("0")) / len(prices))}
            for (day, unit), prices in sorted(grouped.items())
        ]

    def seasonal_products(self, *, city: str, as_of: date, products: Iterable[str] = ()) -> list[dict]:
        """Seasonality proxy: current price at least 5% below its 90-day product average."""
        requested = {product.casefold() for product in products}
        result = []
        for item in self._metrics(city, as_of):
            if requested and item["product"].casefold() not in requested:
                continue
            if item["relative_price"] <= 0.95:
                result.append({**item, "reason": "precio actual al menos 5% por debajo del promedio de 28 observaciones"})
        return self._rank(result, "relative_price", 20)

    def alerts(self, *, city: str, as_of: date) -> list[dict]:
        metrics = self._metrics(city, as_of)
        return [item for item in metrics if abs(item["weekly_change"]) >= float(self.weekly_alert_threshold) or item["forecast_signal"] == "SUBIR"]

    def abasto_index(self, *, city: str, as_of: date, category: str | None = None, lookback_days: int = 90) -> dict | None:
        observations = self.repository.observations(city=city, as_of=as_of)
        if category:
            observations = [item for item in observations if (item.category or "").casefold() == category.casefold()]
        latest = self._latest(observations)
        baseline_start = as_of - timedelta(days=lookback_days)
        values = [item.price for item in observations if baseline_start <= item.date < as_of]
        if not latest or not values:
            return None
        current = mean(float(item.price) for item in latest.values())
        baseline = mean(float(value) for value in values)
        return {"city": city, "category": category, "as_of": as_of.isoformat(), "value": round((current / baseline - 1) * 100, 2), "label": "presión vs. promedio histórico (%)"}

    def investor_rankings(self, *, city: str, as_of: date) -> dict:
        metrics = self._metrics(city, as_of)
        return {"volatility": self._rank(metrics, "volatility", 20, reverse=True), "growth": self._rank(metrics, "weekly_change", 20, reverse=True), "stability": self._rank(metrics, "volatility", 20)}

    def menu_costs(self, *, city: str, recipes: dict[str, dict[str, float]], as_of: date) -> list[dict]:
        latest = self._latest(self.repository.observations(city=city, as_of=as_of))
        response = []
        for recipe, ingredients in recipes.items():
            total, missing = Decimal("0"), []
            for ingredient, quantity in ingredients.items():
                options = [item for item in latest.values() if item.product.casefold() == ingredient.casefold()]
                if not options:
                    missing.append(ingredient)
                else:
                    total += min(options, key=lambda item: item.price).price * Decimal(str(quantity))
            response.append({"recipe": recipe, "estimated_ingredient_cost": str(total), "missing_ingredients": missing})
        return response

    def _metrics(self, city: str, as_of: date) -> list[dict]:
        grouped: dict[tuple[str, str, str], list[PriceObservation]] = defaultdict(list)
        for item in self.repository.observations(city=city, as_of=as_of):
            grouped[item.key].append(item)
        metrics = []
        for series in grouped.values():
            series.sort(key=lambda item: item.date)
            current = series[-1]
            week_old = self._nearest(series, as_of - timedelta(days=7))
            history = [float(item.price) for item in series[-28:]]
            average = mean(history)
            weekly_change = 0.0 if not week_old or not week_old.price else float((current.price - week_old.price) / week_old.price)
            projection = forecast(series, 7)
            forecast_change = 0.0 if not projection or not current.price else float((projection.expected_price - current.price) / current.price)
            relative_price = float(current.price) / average if average else 1.0
            score = -weekly_change - max(0.0, relative_price - 1) # lower and falling is attractive
            metrics.append({"product": current.product, "category": current.category, "price": str(current.price), "unit": current.unit, "market": current.market, "date": current.date.isoformat(), "weekly_change": round(weekly_change, 4), "relative_price": round(relative_price, 4), "volatility": round(pstdev(history) / average, 4) if len(history) > 1 and average else 0.0, "score": round(score, 4), "forecast_signal": projection.signal if projection else "SIN_DATOS", "forecast_change": round(forecast_change, 4), "forecast_7d": projection.to_dict() if projection else None, "forecast_30d": forecast(series, 30).to_dict() if len(series) >= 3 else None})
        return metrics

    @staticmethod
    def _latest(observations: Iterable[PriceObservation]) -> dict[tuple[str, str, str, str | None], PriceObservation]:
        latest = {}
        for item in observations:
            key = (*item.key, item.market.casefold() if item.market else None)
            if key not in latest or item.date > latest[key].date:
                latest[key] = item
        return latest

    @staticmethod
    def _nearest(series: list[PriceObservation], target: date) -> PriceObservation | None:
        eligible = [item for item in series if item.date <= target]
        return eligible[-1] if eligible else None

    @staticmethod
    def _rank(items: list[dict], field: str, limit: int, reverse: bool = False) -> list[dict]:
        return sorted(items, key=lambda item: item[field], reverse=reverse)[:limit]
