"""Profile-aware, deterministic summaries of materialized recommendations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any


Recommendation = Mapping[str, Any]


def condensed_recommendation(profile: str, *, city: str, as_of: date, recommendations: Iterable[Recommendation]) -> str:
    """Return one concise, actionable message for a city/profile/date.

    This intentionally uses the recommendations already materialized in the
    database instead of a language model: output is reproducible and every
    product named can be traced to a source recommendation.
    """
    by_type = {str(item["tipo"]): item for item in recommendations}
    if profile == "consumer":
        return _consumer(city, as_of, by_type)
    if profile == "retailer":
        return _retailer(city, as_of, by_type)
    if profile == "restaurant":
        return _restaurant(city, as_of, by_type)
    raise ValueError(f"Unsupported profile: {profile}")


def _consumer(city: str, as_of: date, rows: Mapping[str, Recommendation]) -> str:
    favorable = _names(rows.get("favorables_comprar")) or _names(rows.get("10_productos_mas_baratos"))
    drops = _names(rows.get("productos_bajaron_semana"))
    rising = _names(rows.get("comprar_antes_de_subir"))
    parts = [f"Con datos del {as_of.isoformat()}, en {city} tu compra rinde más"]
    if favorable:
        parts.append(f"prioriza {_join(favorable)}")
    if drops:
        parts.append(f"aprovecha las caídas de {_join(drops)}")
    if rising:
        parts.append(f"y adelanta {_join(rising)} antes de nuevas alzas")
    return _finish(parts, "Compra con calma, compara y arma tu canasta alrededor de estas oportunidades.")


def _retailer(city: str, as_of: date, rows: Mapping[str, Recommendation]) -> str:
    opportunities = _names(rows.get("ranking_oportunidades")) or _names(rows.get("productos_caida_precio"))
    falling = _names(rows.get("productos_tendencia_favorable"))
    rising = _names(rows.get("productos_podrian_encarecerse"))
    parts = [f"Para tu tienda en {city}, con datos del {as_of.isoformat()}"]
    if opportunities:
        parts.append(f"enfoca el abastecimiento en {_join(opportunities)}")
    if falling:
        parts.append(f"con seguimiento favorable en {_join(falling)}")
    if rising:
        parts.append(f"y protege inventario de {_join(rising)}, que muestra presión de precio")
    return _finish(parts, "Prioriza rotación, compras graduales y revisión de margen antes de reponer.")


def _restaurant(city: str, as_of: date, rows: Mapping[str, Recommendation]) -> str:
    favorable = _names(rows.get("ingredientes_precio_favorable"))
    seasonal = _names(rows.get("productos_temporada"))
    parts = [f"Para la cocina en {city}, con datos del {as_of.isoformat()}"]
    if favorable:
        parts.append(f"destacan {_join(favorable)}")
    if seasonal:
        parts.append(f"y en ingredientes de temporada como {_join(seasonal)}")
    return _finish(parts, "Úsalos como protagonistas de la semana; al cargar recetas y porciones podrás simular costo, menú y promociones.")


def _names(row: Recommendation | None, limit: int = 3) -> list[str]:
    if not row or row.get("estado") not in {"disponible", "limitada"}:
        return []
    content = row.get("contenido") or {}
    items = content.get("items", []) if isinstance(content, Mapping) else []
    names = []
    for item in items:
        name = item.get("producto") or item.get("ingrediente")
        if name and str(name) not in names:
            names.append(str(name))
        if len(names) == limit:
            break
    return names


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} y {names[1]}"
    return f"{', '.join(names[:-1])} y {names[-1]}"


def _finish(parts: list[str], fallback: str) -> str:
    meaningful = [part.rstrip(". ") for part in parts]
    if len(meaningful) == 1:
        return f"{meaningful[0]}. Aún no hay señales accionables suficientes; {fallback.lower()}"
    return f"{'; '.join(meaningful)}. {fallback}"
