import pandas as pd


def calculate_forecast(history: pd.DataFrame, horizonte_semanas: int = 2) -> dict:
    if not 1 <= horizonte_semanas <= 4:
        raise ValueError("horizonte_semanas debe estar entre 1 y 4")
    if len(history) < 4:
        raise ValueError("se requieren al menos 4 semanas")
    ordered = history.sort_values("fecha") if "fecha" in history else history
    price_column = "precio" if "precio" in ordered else "precio_prom"
    prices = ordered[price_column].astype(float).reset_index(drop=True)
    ma4 = float(prices.tail(4).mean())
    current = float(prices.iloc[-1])
    if len(prices) >= 53:
        current_last_year = float(prices.iloc[-53])
        target_index = max(0, len(prices) - 53 + horizonte_semanas)
        target_last_year = float(prices.iloc[target_index])
        var_52w = current / current_last_year - 1 if current_last_year else 0.0
        seasonal = target_last_year * (1 + var_52w)
    else:
        seasonal = ma4
    expected = 0.6 * ma4 + 0.4 * seasonal
    std12 = float(prices.tail(12).std(ddof=1)) if len(prices.tail(12)) > 1 else 0.0
    if pd.isna(std12):
        std12 = 0.0
    return {
        "precio_esperado": round(expected, 2),
        "banda_inf": round(max(0.0, expected - std12), 2),
        "banda_sup": round(expected + std12, 2),
        "metodo": "ma4+estacional",
    }


def forecast(producto_id: str, ciudad: str, horizonte_semanas: int = 2, repo=None) -> dict:
    if repo is None:
        from sipsa.db.repo import Repository

        repo = Repository()
    history = pd.DataFrame(repo.price_history(producto_id, ciudad))
    result = calculate_forecast(history, horizonte_semanas)
    current = float(history.sort_values("fecha").iloc[-1].precio)
    return {
        "producto_id": producto_id,
        "ciudad": ciudad,
        "horizonte_semanas": horizonte_semanas,
        "precio_actual": round(current, 2),
        **result,
        "var_esperada_pct": round(result["precio_esperado"] / current - 1, 4),
    }
