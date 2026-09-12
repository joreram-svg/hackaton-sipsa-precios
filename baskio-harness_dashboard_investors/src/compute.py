"""Derives per-product metrics, market insights and price forecasts from the raw dataset."""
import math
import statistics
from collections import defaultdict


def _back(prices, n):
    idx = len(prices) - 1 - n
    return prices[idx] if idx >= 0 else None


def _pct(cur, ref):
    if ref is None or ref == 0:
        return None
    return round((cur / ref - 1) * 100, 2)


def _linreg(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n)) or 1e-9
    slope = num / den
    intercept = my - slope * mx
    resid = [ys[i] - (intercept + slope * xs[i]) for i in range(n)]
    sse = sum(r * r for r in resid)
    dof = max(n - 2, 1)
    resid_std = math.sqrt(sse / dof)
    return slope, intercept, resid_std


def enrich_products(dataset: dict) -> dict:
    """Adds per-product change/volatility/trend/forecast fields in place, returns dataset."""
    for p in dataset["products"]:
        pts = p["series"]
        prices = [v for _, v in pts]
        n = len(prices)
        current = prices[-1]

        p1w, p4w, p52w = _back(prices, 1), _back(prices, 4), prices[0]
        chg_1w, chg_4w, chg_1y = _pct(current, p1w), _pct(current, p4w), _pct(current, p52w)

        rets = [(prices[i] / prices[i - 1] - 1) * 100 for i in range(1, n) if prices[i - 1]]
        vol = round(statistics.pstdev(rets), 2) if len(rets) > 1 else 0.0

        xs_full = list(range(n))
        slope, _, _ = _linreg(xs_full, prices)
        mean_y = sum(prices) / n
        trend_pct_week = round((slope / mean_y) * 100, 3) if mean_y else 0.0

        yr_min, yr_max = round(min(prices), 2), round(max(prices), 2)
        pos_in_range = round((current - yr_min) / (yr_max - yr_min), 3) if yr_max > yr_min else 0.5

        # --- forecast: linear regression over the most recent 12 points ---
        window = pts[-min(12, n):]
        wxs = list(range(len(window)))
        wys = [v for _, v in window]
        wslope, wintercept, resid_std = _linreg(wxs, wys)
        last_x = len(window) - 1
        last_price = wys[-1]

        step_7, step_30 = 1, 4.3
        f7 = max(wintercept + wslope * (last_x + step_7), 0)
        f30 = max(wintercept + wslope * (last_x + step_30), 0)
        z = 1.645
        ci7 = resid_std * z * math.sqrt(1 + step_7 / len(window))
        ci30 = resid_std * z * math.sqrt(1 + step_30 / len(window))

        pct_slope_week = (wslope / last_price * 100) if last_price else 0
        if pct_slope_week > 0.6:
            trend_label = "alcista"
        elif pct_slope_week < -0.6:
            trend_label = "bajista"
        else:
            trend_label = "estable"

        chg7_pct = (f7 / last_price - 1) * 100 if last_price else 0
        if chg7_pct > 1.5:
            signal = "SUBIR"
        elif chg7_pct < -1.5:
            signal = "BAJAR"
        else:
            signal = "ESTABLE"

        p.update(
            current=current,
            chg_1w=chg_1w,
            chg_4w=chg_4w,
            chg_1y=chg_1y,
            volatility=vol,
            trend_pct_week=trend_pct_week,
            yr_min=yr_min,
            yr_max=yr_max,
            pos_in_range=pos_in_range,
            n_points=n,
            forecast={
                "f7": round(f7, 2),
                "f7_low": round(max(f7 - ci7, 0), 2),
                "f7_high": round(f7 + ci7, 2),
                "f30": round(f30, 2),
                "f30_low": round(max(f30 - ci30, 0), 2),
                "f30_high": round(f30 + ci30, 2),
                "trend_label": trend_label,
                "slope_pct_week": round(pct_slope_week, 2),
                "signal": signal,
                "chg7_pct": round(chg7_pct, 2),
                "window_weeks": len(window),
            },
        )

    dataset["products"].sort(key=lambda p: (p["categoria"] or "", p["nombre"] or ""))
    return dataset


def compute_insights(dataset: dict) -> dict:
    prods = dataset["products"]
    valid = [p for p in prods if p.get("chg_1y") is not None]

    def pick(p):
        return {
            "id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"],
            "chg_1y": p["chg_1y"], "chg_4w": p["chg_4w"], "chg_1w": p["chg_1w"],
            "volatility": p["volatility"], "trend_pct_week": p["trend_pct_week"],
            "current": p["current"], "unidad": p["unidad"], "pos_in_range": p["pos_in_range"],
        }

    gainers = sorted(valid, key=lambda p: -p["chg_1y"])[:5]
    losers = sorted(valid, key=lambda p: p["chg_1y"])[:5]
    volatile = sorted(prods, key=lambda p: -p["volatility"])[:5]
    stable = sorted(prods, key=lambda p: p["volatility"])[:5]

    cat_stats = defaultdict(list)
    for p in valid:
        cat_stats[p["categoria"]].append(p["chg_1y"])
    cat_perf = sorted(
        [{"categoria": c, "avg_chg_1y": round(sum(v) / len(v), 2), "n": len(v)} for c, v in cat_stats.items()],
        key=lambda x: -x["avg_chg_1y"],
    )

    up = sum(1 for p in valid if p["chg_1y"] > 0)
    down = sum(1 for p in valid if p["chg_1y"] < 0)
    flat = len(valid) - up - down
    avg_mkt = round(sum(p["chg_1y"] for p in valid) / len(valid), 2) if valid else 0.0

    dataset["insights"] = {
        "top_gainers": [pick(p) for p in gainers],
        "top_losers": [pick(p) for p in losers],
        "most_volatile": [pick(p) for p in volatile],
        "most_stable": [pick(p) for p in stable],
        "category_performance": cat_perf,
        "market_breadth": {"up": up, "down": down, "flat": flat, "avg_chg_1y": avg_mkt, "n": len(valid)},
    }
    return dataset


def build_full_dataset(raw_dataset: dict) -> dict:
    enrich_products(raw_dataset)
    compute_insights(raw_dataset)
    return raw_dataset
