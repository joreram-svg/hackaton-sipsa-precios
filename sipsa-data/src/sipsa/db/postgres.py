from io import StringIO
from pathlib import Path
import re

import pandas as pd
from psycopg2.extras import Json, execute_values

from sipsa.config import PROJECT_ROOT


IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
CATALOG_CSV = PROJECT_ROOT / "src" / "sipsa" / "catalog" / "productos.csv"


def _validated_identifiers(values: list[str]) -> str:
    if not values or any(not IDENTIFIER.fullmatch(value) for value in values):
        raise ValueError("Identificador SQL no permitido")
    return ",".join(values)


def copy_upsert(
    cursor,
    frame: pd.DataFrame,
    *,
    table: str,
    key_columns: list[str],
    update_columns: list[str],
) -> dict[str, int]:
    """Carga por COPY a staging temporal y hace upsert en la transacción activa."""
    if not IDENTIFIER.fullmatch(table):
        raise ValueError("Tabla SQL no permitida")
    columns = list(frame.columns)
    column_sql = _validated_identifiers(columns)
    key_sql = _validated_identifiers(key_columns)
    stage = f"incoming_{table}"
    if frame.empty:
        return {"inserted": 0, "updated": 0, "total": 0}

    cursor.execute(f"CREATE TEMP TABLE {stage} (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
    buffer = StringIO()
    frame.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)
    cursor.copy_expert(
        f"COPY {stage} ({column_sql}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
        buffer,
    )
    join = " AND ".join(f"target.{name}=incoming.{name}" for name in key_columns)
    cursor.execute(f"SELECT count(*) FROM {table} target JOIN {stage} incoming ON {join}")
    updated = int(cursor.fetchone()[0])
    assignments = ",".join(f"{name}=excluded.{name}" for name in update_columns)
    if table == "fact_precio":
        assignments += ",ingested_at=now()"
    cursor.execute(
        f"INSERT INTO {table} ({column_sql}) SELECT {column_sql} FROM {stage} "
        f"ON CONFLICT ({key_sql}) DO UPDATE SET {assignments}"
    )
    total = len(frame)
    return {"inserted": total - updated, "updated": updated, "total": total}


def upsert_catalog(cursor, catalog_path: Path = CATALOG_CSV) -> None:
    """Sincroniza el catálogo maestro sin eliminar productos existentes."""
    catalog = pd.read_csv(catalog_path).fillna({"alias": ""})
    values = [
        (
            row.producto_id,
            row.nombre,
            row.categoria,
            row.unidad_base,
            Json(str(row.alias).split("|")),
        )
        for row in catalog.itertuples(index=False)
    ]
    execute_values(
        cursor,
        """INSERT INTO dim_producto(producto_id,nombre,categoria,unidad_base,alias) VALUES %s
        ON CONFLICT (producto_id) DO UPDATE SET nombre=excluded.nombre,
          categoria=excluded.categoria, unidad_base=excluded.unidad_base, alias=excluded.alias""",
        values,
        page_size=1000,
    )
