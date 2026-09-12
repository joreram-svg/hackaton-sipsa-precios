"""Pulls the last-year weekly dataset from Supabase for the Baskio dashboard."""
import os
from collections import defaultdict
from datetime import timedelta

import psycopg

FIX = {
    "Bogot�": "Bogotá", "Medell�n": "Medellín", "C�ucuta": "Cúcuta",
    "Az�car": "Azúcar", "Fr�jol": "Fríjol", "Br�coli": "Brócoli",
}


def _fx(s):
    if s is None:
        return s
    return FIX.get(s, s.replace("�", "?"))


def get_dsn() -> str:
    dsn = os.environ.get("BASKIO_DSN") or os.environ.get("SUPABASE_DSN")
    if not dsn:
        raise RuntimeError(
            "Missing DB connection string. Set BASKIO_DSN (or SUPABASE_DSN) env var, "
            "e.g. postgresql://user:pass@host:5432/postgres"
        )
    return dsn


def fetch_dataset(dsn: str | None = None) -> dict:
    """Returns {meta, products:[{id, nombre, categoria, unidad, series, supply, cities}]}."""
    dsn = dsn or get_dsn()

    with psycopg.connect(dsn, connect_timeout=20) as conn:
        cur = conn.cursor()
        cur.execute("select max(fecha) from public.fact_precio")
        max_date = cur.fetchone()[0]
        if max_date is None:
            raise RuntimeError("fact_precio is empty — nothing to build a dashboard from")
        start_date = max_date - timedelta(days=370)

        cur.execute(
            "select producto_id, nombre, categoria, unidad_base from public.dim_producto order by producto_id"
        )
        productos = {
            r[0]: {"id": r[0], "nombre": _fx(r[1]), "categoria": _fx(r[2]), "unidad": r[3]}
            for r in cur.fetchall()
        }

        cur.execute(
            """
            select producto_id, fecha, avg(precio) from public.fact_precio
            where fecha >= %s
            group by producto_id, fecha
            order by producto_id, fecha
            """,
            (start_date,),
        )
        series = defaultdict(list)
        for pid, fecha, precio in cur.fetchall():
            series[pid].append((fecha.isoformat(), round(float(precio), 2)))

        cur.execute(
            """
            select producto_id, fecha, sum(toneladas) from public.fact_abastecimiento
            where fecha >= %s
            group by producto_id, fecha
            order by producto_id, fecha
            """,
            (start_date,),
        )
        supply = defaultdict(list)
        for pid, fecha, ton in cur.fetchall():
            supply[pid].append((fecha.isoformat(), round(float(ton), 1)))

        cur.execute(
            """
            select producto_id, ciudad, precio from public.fact_precio
            where fecha = %s
            order by producto_id, ciudad
            """,
            (max_date,),
        )
        latest_by_city = defaultdict(list)
        for pid, ciudad, precio in cur.fetchall():
            latest_by_city[pid].append({"ciudad": _fx(ciudad), "precio": round(float(precio), 2)})

    products_out = []
    for pid, meta in productos.items():
        pts = series.get(pid, [])
        if len(pts) < 2:
            continue
        products_out.append(
            {
                **meta,
                "series": pts,
                "supply": supply.get(pid, []),
                "cities": latest_by_city.get(pid, []),
            }
        )
    products_out.sort(key=lambda p: (p["categoria"] or "", p["nombre"] or ""))

    return {
        "meta": {
            "max_date": max_date.isoformat(),
            "start_date": start_date.isoformat(),
            "n_products": len(products_out),
        },
        "products": products_out,
    }
