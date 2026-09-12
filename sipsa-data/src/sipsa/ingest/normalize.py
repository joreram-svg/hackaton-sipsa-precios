from difflib import get_close_matches
from pathlib import Path
import re
import unicodedata

import pandas as pd

from sipsa.config import PROJECT_ROOT


UNIDAD_FACTOR = {
    "kg": 1.0,
    "kilo": 1.0,
    "lb": 0.5,
    "libra": 0.5,
    "arroba": 12.5,
    "@": 12.5,
    "bulto": 50.0,
}


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text)


def _catalog_aliases(catalog_path: Path | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    path = catalog_path or PROJECT_ROOT / "src" / "sipsa" / "catalog" / "productos.csv"
    catalog = pd.read_csv(path)
    aliases: dict[str, str] = {}
    for row in catalog.itertuples():
        values = [row.producto_id, row.nombre, *str(row.alias).split("|")]
        for value in values:
            aliases[_plain(value)] = row.producto_id
    return catalog, aliases


def match_producto(nombre_raw: str, catalog_path: Path | None = None) -> str | None:
    """Mapea un nombre SIPSA al identificador maestro usando alias y similitud."""
    _, aliases = _catalog_aliases(catalog_path)
    candidate = _plain(nombre_raw)
    if candidate in aliases:
        return aliases[candidate]
    close = get_close_matches(candidate, aliases.keys(), n=1, cutoff=0.85)
    return aliases[close[0]] if close else None


def normalize_prices(
    raw: pd.DataFrame,
    catalog_path: Path | None = None,
    unmapped_path: Path | None = None,
) -> pd.DataFrame:
    """Normaliza el RAW a una fila semanal COP/kg por producto y ciudad."""
    output_columns = ["fecha", "producto_id", "ciudad", "precio", "fuente"]
    if raw.empty:
        return pd.DataFrame(columns=output_columns)
    _, aliases = _catalog_aliases(catalog_path)
    data = raw.copy()
    normalized_names = data["producto_raw"].map(_plain)
    data["producto_id"] = normalized_names.map(aliases)
    missing = data["producto_id"].isna()
    if missing.any():
        keys = list(aliases)
        for index in data.index[missing]:
            close = get_close_matches(normalized_names.loc[index], keys, n=1, cutoff=0.85)
            if close:
                data.at[index, "producto_id"] = aliases[close[0]]
    unmapped = data[data["producto_id"].isna()].copy()
    if not unmapped.empty:
        path = unmapped_path or PROJECT_ROOT / "data" / "raw" / "unmapped.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        unmapped[["fecha", "producto_raw", "mercado_raw", "ciudad_raw", "unidad_raw", "fuente"]].to_csv(
            path, mode="a", header=not path.exists(), index=False
        )
    data = data[data["producto_id"].notna()].copy()
    data["unidad_normalizada"] = data["unidad_raw"].map(_plain)
    data["factor"] = data["unidad_normalizada"].map(UNIDAD_FACTOR)
    data = data[data["factor"].notna()].copy()
    data["precio"] = pd.to_numeric(data["precio_prom"], errors="coerce") / data["factor"]
    data = data[data["precio"].notna() & (data["precio"] > 0)].copy()
    dates = pd.to_datetime(data["fecha"], errors="coerce")
    data["fecha"] = (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.date
    data["ciudad"] = data["ciudad_raw"].astype(str).str.strip()
    result = (
        data.groupby(["fecha", "producto_id", "ciudad", "fuente"], as_index=False)["precio"]
        .mean()
        .loc[:, output_columns]
    )
    result["precio"] = result["precio"].round(2)
    return result.sort_values(["fecha", "producto_id", "ciudad"]).reset_index(drop=True)
