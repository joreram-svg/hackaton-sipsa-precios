"""Create/update one profile-specific recommendation text per city and date."""

from __future__ import annotations

import os
from collections import defaultdict

from abasto_ai.condensed import condensed_recommendation


SOURCES = {
    "consumer": ("recomendaciones_consumidor", "rec_condensada_consumidor"),
    "retailer": ("recomendaciones_tendero", "rec_condensada_tendero"),
    "restaurant": ("recomendaciones_restaurante", "rep_condensada_restaurante"),
}


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise SystemExit("Install the PostgreSQL extra: pip install -e '.[postgres]'") from exc

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        for profile, (source, target) in SOURCES.items():
            conn.execute(_schema(target))
            grouped = defaultdict(list)
            source_dates = {}
            rows = conn.execute(
                f"SELECT fecha, ciudad, tipo, estado, contenido, fuente_fecha FROM public.{source}"
            ).fetchall()
            for row in rows:
                key = (row["fecha"], row["ciudad"])
                grouped[key].append(row)
                source_dates[key] = max(source_dates.get(key, row["fuente_fecha"]), row["fuente_fecha"])
            for (as_of, city), recommendations in grouped.items():
                text = condensed_recommendation(profile, city=city, as_of=as_of, recommendations=recommendations)
                conn.execute(
                    f"""INSERT INTO public.{target} (fecha, ciudad, recomendacion, fuente_fecha)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, ciudad) DO UPDATE SET
                        recomendacion = EXCLUDED.recomendacion,
                        fuente_fecha = EXCLUDED.fuente_fecha,
                        updated_at = now()""",
                    (as_of, city, text, source_dates[(as_of, city)]),
                )
        conn.commit()


def _schema(table: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS public.{table} (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        fecha date NOT NULL,
        ciudad character varying(100) NOT NULL,
        recomendacion text NOT NULL,
        fuente_fecha date NOT NULL,
        created_at timestamp with time zone NOT NULL DEFAULT now(),
        updated_at timestamp with time zone NOT NULL DEFAULT now(),
        CONSTRAINT {table}_fecha_ciudad_key UNIQUE (fecha, ciudad)
    )
    """


if __name__ == "__main__":
    main()
