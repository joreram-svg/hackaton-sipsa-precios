from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import sqrt
from statistics import mean
from typing import Sequence

from .models import PriceObservation


@dataclass(frozen=True, slots=True)
class Forecast:
    horizon_days: int
    expected_price: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    trend: str
    signal: str

    def to_dict(self) -> dict:
        result = asdict(self)
        return {key: str(value) if isinstance(value, Decimal) else value for key, value in result.items()}


def forecast(observations: Sequence[PriceObservation], horizon_days: int) -> Forecast | None:
    """Small, explainable OLS projection; requires at least 3 dated observations."""
    if len(observations) < 3:
        return None
    latest_by_day: dict[date, list[float]] = {}
    for item in observations:
        latest_by_day.setdefault(item.date, []).append(float(item.price))
    points = sorted((day, mean(values)) for day, values in latest_by_day.items())[-28:]
    if len(points) < 3:
        return None
    start = points[0][0]
    xs = [(day - start).days for day, _ in points]
    ys = [price for _, price in points]
    x_bar, y_bar = mean(xs), mean(ys)
    denominator = sum((x - x_bar) ** 2 for x in xs)
    slope = 0.0 if denominator == 0 else sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys)) / denominator
    intercept = y_bar - slope * x_bar
    target_x = (points[-1][0] + timedelta(days=horizon_days) - start).days
    prediction = max(0.0, intercept + slope * target_x)
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    sigma = sqrt(sum(error**2 for error in residuals) / max(1, len(points) - 2))
    last_price = ys[-1]
    change = (prediction - last_price) / last_price if last_price else 0.0
    signal = "SUBIR" if change >= 0.03 else "BAJAR" if change <= -0.03 else "ESTABLE"
    trend = "alcista" if slope > 0 else "bajista" if slope < 0 else "plana"
    return Forecast(horizon_days, _money(prediction), _money(max(0.0, prediction - 1.96 * sigma)), _money(prediction + 1.96 * sigma), trend, signal)


def _money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))
