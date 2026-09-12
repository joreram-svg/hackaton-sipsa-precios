from datetime import date, timedelta

from .engine import FeatureEngine
from .repository import InMemoryPriceRepository


def main() -> None:
    today = date.today()
    rows = []
    for product, start, step in [("papa", 3000, -40), ("tomate", 3500, 60), ("arroz", 4200, 5)]:
        for offset in range(14):
            rows.append({"date": str(today - timedelta(days=13 - offset)), "city": "Bogotá", "product": product, "price": start + step * offset, "unit": "kg"})
    engine = FeatureEngine(InMemoryPriceRepository(rows), substitutions={"tomate": ["papa"]})
    print(engine.consumer_snapshot(city="Bogotá", as_of=today, basket=["papa", "tomate", "arroz"]))


if __name__ == "__main__":
    main()
