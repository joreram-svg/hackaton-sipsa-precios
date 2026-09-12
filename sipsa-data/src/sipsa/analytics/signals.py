from typing import Literal


Profile = Literal["consumidor", "restaurante", "mayorista"]
PROFILE_MULTIPLIERS = {
    "consumidor": (1.0, 1.0, 1.5),
    "restaurante": (1.0, 1.5, 1.0),
    "mayorista": (1.5, 1.0, 1.0),
}


def _clip(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def opportunity_signal(
    percentil_hist: float,
    var_1w_pct: float,
    var_4w_pct: float,
    perfil: Profile = "consumidor",
) -> dict[str, float | str]:
    if perfil not in PROFILE_MULTIPLIERS:
        raise ValueError("perfil debe ser consumidor, restaurante o mayorista")
    multipliers = PROFILE_MULTIPLIERS[perfil]
    raw_weights = [0.45 * multipliers[0], 0.35 * multipliers[1], 0.20 * multipliers[2]]
    total = sum(raw_weights)
    weights = [weight / total for weight in raw_weights]
    components = [
        1 - _clip(float(percentil_hist), 0, 1),
        0.5 + _clip(-float(var_4w_pct) / 0.30, -1, 1) / 2,
        0.5 + _clip(-float(var_1w_pct) / 0.15, -1, 1) / 2,
    ]
    score = round(100 * _clip(sum(w * c for w, c in zip(weights, components)), 0, 1), 2)
    signal = "COMPRAR" if score >= 65 else "EVITAR" if score <= 35 else "NEUTRAL"
    return {"score": score, "senal": signal}


def reason_for(var_4w_pct: float, percentil_hist: float) -> str:
    direction = "más barata" if var_4w_pct < 0 else "más cara"
    percentile = max(1, min(100, round(percentil_hist * 100)))
    return (
        f"{abs(var_4w_pct) * 100:.0f}% {direction} que hace un mes y "
        f"en el {percentile}% {'más bajo' if percentil_hist <= 0.5 else 'más alto'} de 2 años"
    )

