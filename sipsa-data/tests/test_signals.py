from datetime import date, timedelta

import pandas as pd
import pytest

from sipsa.analytics.forecast import calculate_forecast
from sipsa.analytics.signals import opportunity_signal


def test_score_aplica_formula_exacta_y_umbrales():
    """Detecta pesos, clips o umbrales distintos al contrato."""
    result = opportunity_signal(0.10, -0.075, -0.18, "restaurante")
    assert result["score"] == pytest.approx(82.98, abs=0.01)
    assert result["senal"] == "COMPRAR"

    assert opportunity_signal(1.0, 0.30, 0.15)["senal"] == "EVITAR"
    assert opportunity_signal(0.5, 0.0, 0.0)["senal"] == "NEUTRAL"


def test_perfiles_solo_escalan_y_renormalizan_pesos():
    """Detecta que un perfil altere la fórmula en vez de sus pesos."""
    consumidor = opportunity_signal(0.2, -0.12, 0.0, "consumidor")["score"]
    restaurante = opportunity_signal(0.2, -0.12, 0.0, "restaurante")["score"]
    mayorista = opportunity_signal(0.2, -0.12, 0.0, "mayorista")["score"]
    assert consumidor > restaurante
    assert mayorista > restaurante


def test_forecast_combina_ma4_estacional_y_banda_12_semanas():
    """Detecta cambios en la combinación 0.6/0.4 o en la banda."""
    start = date(2024, 1, 1)
    prices = [8.0] * 6 + [10.0, 8.0] + [10.0] * 45 + [9.0, 10.0, 11.0, 10.0]
    history = pd.DataFrame(
        {"fecha": [start + timedelta(weeks=i) for i in range(57)], "precio_prom": prices}
    )
    result = calculate_forecast(history, horizonte_semanas=2)

    assert result["precio_esperado"] == pytest.approx(11.0)
    assert result["banda_inf"] < result["precio_esperado"] < result["banda_sup"]
    assert result["metodo"] == "ma4+estacional"


def test_forecast_rechaza_horizonte_fuera_de_1_a_4():
    """Detecta ausencia de validación del horizonte contractual."""
    with pytest.raises(ValueError, match="1 y 4"):
        calculate_forecast(pd.DataFrame({"precio_prom": [1.0]}), 5)
