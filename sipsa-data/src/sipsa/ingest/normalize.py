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

CITY_NAMES = {
    "armenia": "Armenia",
    "barranquilla": "Barranquilla",
    "bogota": "Bogotá",
    "bogota d.c.": "Bogotá",
    "bucaramanga": "Bucaramanga",
    "cali": "Cali",
    "cartagena": "Cartagena de Indias",
    "cartagena de indias": "Cartagena de Indias",
    "cucuta": "Cúcuta",
    "san jose de cucuta": "Cúcuta",
    "florencia": "Florencia",
    "ibague": "Ibagué",
    "ipiales": "Ipiales",
    "manizales": "Manizales",
    "medellin": "Medellín",
    "monteria": "Montería",
    "neiva": "Neiva",
    "pasto": "Pasto",
    "pereira": "Pereira",
    "popayan": "Popayán",
    "santa marta": "Santa Marta",
    "sincelejo": "Sincelejo",
    "tibasosa": "Tibasosa",
    "tunja": "Tunja",
    "valledupar": "Valledupar",
    "villavicencio": "Villavicencio",
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


def normalize_city(value: object) -> str:
    """Normaliza ciudad y elimina el nombre de mercado conservando ciudades nuevas."""
    if pd.isna(value):
        return ""
    city = str(value).strip()
    city = city.split(",", 1)[0]
    city = re.sub(r"\s*\([^)]*\)\s*$", "", city).strip()
    key = _plain(city)
    return CITY_NAMES.get(key, city.title())


def _map_product_ids(data: pd.DataFrame, aliases: dict[str, str]) -> pd.Series:
    normalized_names = data["producto_raw"].map(_plain)
    product_ids = normalized_names.map(aliases)
    missing = product_ids.isna()
    if missing.any():
        keys = list(aliases)
        fuzzy: dict[str, str | None] = {}
        for candidate in normalized_names[missing].unique():
            close = get_close_matches(candidate, keys, n=1, cutoff=0.85)
            if close:
                fuzzy[candidate] = aliases[close[0]]
        product_ids = product_ids.fillna(normalized_names.map(fuzzy))
    return product_ids


def map_product_ids(values: pd.Series, catalog_path: Path | None = None) -> pd.Series:
    """Mapea una serie de nombres con las mismas reglas usadas por las ingestas."""
    _, aliases = _catalog_aliases(catalog_path)
    return _map_product_ids(pd.DataFrame({"producto_raw": values}), aliases)


def _write_unmapped(data: pd.DataFrame, path: Path) -> None:
    if data.empty:
        return
    columns = ["fecha", "producto_raw", "mercado_raw", "ciudad_raw", "unidad_raw", "fuente"]
    audit = data.reindex(columns=columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        audit = pd.concat(
            [pd.read_csv(path, dtype=str, keep_default_na=False), audit],
            ignore_index=True,
        )
    audit.drop_duplicates().to_csv(path, index=False)


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
    data["producto_id"] = _map_product_ids(data, aliases)
    unmapped = data[data["producto_id"].isna()].copy()
    if not unmapped.empty:
        path = unmapped_path or PROJECT_ROOT / "data" / "raw" / "unmapped.csv"
        _write_unmapped(unmapped, path)
    data = data[data["producto_id"].notna()].copy()
    data["unidad_normalizada"] = data["unidad_raw"].map(_plain)
    data["factor"] = data["unidad_normalizada"].map(UNIDAD_FACTOR)
    data = data[data["factor"].notna()].copy()
    data["precio"] = pd.to_numeric(data["precio_prom"], errors="coerce") / data["factor"]
    data = data[data["precio"].notna() & (data["precio"] > 0)].copy()
    dates = pd.to_datetime(data["fecha"], errors="coerce")
    data["fecha"] = (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.date
    data["ciudad"] = data["ciudad_raw"].map(normalize_city)
    data = data[data["ciudad"] != ""].copy()
    result = (
        data.groupby(["fecha", "producto_id", "ciudad", "fuente"], as_index=False)["precio"]
        .mean()
        .loc[:, output_columns]
    )
    result["precio"] = result["precio"].round(2)
    return result.sort_values(["fecha", "producto_id", "ciudad"]).reset_index(drop=True)


def normalize_abastecimiento(
    raw: pd.DataFrame,
    catalog_path: Path | None = None,
    unmapped_path: Path | None = None,
) -> pd.DataFrame:
    """Normaliza abastecimiento mensual y agrega los mercados a nivel ciudad."""
    output_columns = ["fecha", "producto_id", "ciudad", "toneladas", "fuente"]
    if raw.empty:
        return pd.DataFrame(columns=output_columns)
    _, aliases = _catalog_aliases(catalog_path)
    data = raw.copy()
    data["producto_id"] = _map_product_ids(data, aliases)
    unmapped = data[data["producto_id"].isna()].copy()
    if not unmapped.empty:
        path = unmapped_path or PROJECT_ROOT / "data" / "raw" / "unmapped.csv"
        _write_unmapped(unmapped, path)
    data = data[data["producto_id"].notna()].copy()
    data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce").dt.date
    data["ciudad"] = data["ciudad_raw"].map(normalize_city)
    data["toneladas"] = pd.to_numeric(data["toneladas"], errors="coerce")
    data = data[
        data["fecha"].notna()
        & (data["ciudad"] != "")
        & data["toneladas"].notna()
        & (data["toneladas"] > 0)
    ].copy()
    result = (
        data.groupby(["fecha", "producto_id", "ciudad", "fuente"], as_index=False)["toneladas"]
        .sum()
        .loc[:, output_columns]
    )
    result["toneladas"] = result["toneladas"].round(6)
    return result.sort_values(["fecha", "producto_id", "ciudad"]).reset_index(drop=True)
