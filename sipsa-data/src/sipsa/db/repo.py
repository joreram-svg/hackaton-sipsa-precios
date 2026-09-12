from pathlib import Path
from typing import Any

import pandas as pd

from sipsa.analytics.forecast import forecast
from sipsa.analytics.signals import opportunity_signal, reason_for
from sipsa.config import PROJECT_ROOT, Settings, get_settings


class Repository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _connect(self):
        import duckdb

        return duckdb.connect(str(self.settings.db_path), read_only=True)

    @staticmethod
    def _rows(cursor) -> list[dict[str, Any]]:
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def list_products(self, categoria: str | None = None) -> list[dict]:
        sql = "SELECT producto_id,nombre,categoria,unidad_base FROM dim_producto"
        params: list[Any] = []
        if categoria:
            sql += " WHERE categoria = ?"
            params.append(categoria)
        with self._connect() as conn:
            return self._rows(conn.execute(sql + " ORDER BY nombre", params))

    def list_markets(self, ciudad: str | None = None) -> list[dict]:
        sql = "SELECT mercado_id,nombre,ciudad FROM dim_mercado"
        params: list[Any] = []
        if ciudad:
            sql += " WHERE ciudad = ?"
            params.append(ciudad)
        with self._connect() as conn:
            return self._rows(conn.execute(sql + " ORDER BY ciudad,nombre", params))

    def default_market(self, city: str = "Bogotá") -> str:
        markets = self.list_markets(city)
        if not markets:
            raise LookupError(f"No existe mercado para {city}")
        return markets[0]["mercado_id"]

    def price_history(self, producto_id: str, mercado_id: str, desde=None, hasta=None, semanas=None) -> list[dict]:
        sql = "SELECT fecha,precio_prom,precio_min,precio_max,fuente FROM fact_precio WHERE producto_id=? AND mercado_id=?"
        params: list[Any] = [producto_id, mercado_id]
        if desde:
            sql += " AND fecha >= ?"
            params.append(desde)
        if hasta:
            sql += " AND fecha <= ?"
            params.append(hasta)
        sql += " ORDER BY fecha"
        if semanas:
            sql = f"SELECT * FROM ({sql}) q ORDER BY fecha DESC LIMIT {int(semanas)}"
        with self._connect() as conn:
            rows = self._rows(conn.execute(sql, params))
        return sorted(rows, key=lambda row: row["fecha"])

    def analytics(self, city: str, categoria: str | None = None) -> list[dict]:
        sql = """
        SELECT v.*, p.nombre, p.categoria, q.percentil_hist, t.pendiente_pct_sem
        FROM v_variacion v
        JOIN dim_producto p USING(producto_id)
        JOIN dim_mercado m USING(mercado_id)
        JOIN v_percentil q USING(producto_id,mercado_id)
        JOIN v_tendencia t USING(producto_id,mercado_id)
        WHERE m.ciudad = ?
        """
        params: list[Any] = [city]
        if categoria:
            sql += " AND p.categoria = ?"
            params.append(categoria)
        with self._connect() as conn:
            return self._rows(conn.execute(sql, params))

    def opportunities(self, city="Bogotá", categoria=None, perfil="consumidor", top=10, ascending=False) -> dict:
        rows = self.analytics(city, categoria)
        items = []
        for row in rows:
            calculated = opportunity_signal(
                row["percentil_hist"], row["var_1w_pct"] or 0, row["var_4w_pct"] or 0, perfil
            )
            item = {
                key: row[key]
                for key in (
                    "producto_id", "nombre", "categoria", "mercado_id", "precio_actual",
                    "precio_1w", "precio_4w", "var_1w_pct", "var_4w_pct", "percentil_hist"
                )
            }
            item.update(calculated)
            item["razon"] = reason_for(row["var_4w_pct"] or 0, row["percentil_hist"])
            items.append(item)
        items.sort(key=lambda item: item["score"], reverse=not ascending)
        selected = items[: max(1, min(int(top), 100))]
        if perfil == "mayorista":
            for item in selected:
                expected = forecast(item["producto_id"], item["mercado_id"], 2, self)
                item["razon"] += f"; pronóstico {expected['var_esperada_pct'] * 100:+.0f}%"
        latest = max((row["fecha"] for row in rows), default=None)
        return {"fecha": latest, "ciudad": city, "perfil": perfil, "items": selected}

    def trend(self, producto_id: str, mercado_id: str | None = None, semanas: int = 12) -> dict:
        mercado_id = mercado_id or self.default_market()
        history = self.price_history(producto_id, mercado_id, semanas=semanas)
        with self._connect() as conn:
            rows = self._rows(conn.execute(
                """SELECT v.var_1w_pct,v.var_4w_pct,v.var_52w_pct,p.percentil_hist,t.pendiente_pct_sem
                FROM v_variacion v JOIN v_percentil p USING(producto_id,mercado_id)
                JOIN v_tendencia t USING(producto_id,mercado_id)
                WHERE v.producto_id=? AND v.mercado_id=?""", [producto_id, mercado_id]
            ))
        if not rows:
            raise LookupError(f"Producto sin datos: {producto_id}")
        return {"producto_id": producto_id, "mercado_id": mercado_id,
                "serie": [{"fecha": r["fecha"], "precio_prom": r["precio_prom"]} for r in history], **rows[0]}

    def alerts(self, city="Bogotá", threshold=15.0, window="1w") -> dict:
        key = "var_1w_pct" if window == "1w" else "var_4w_pct"
        items = []
        rows = self.analytics(city)
        for row in rows:
            variation = float(row[key] or 0)
            if abs(variation * 100) >= threshold:
                items.append({"producto_id": row["producto_id"], "nombre": row["nombre"],
                              "mercado_id": row["mercado_id"], "var_pct": variation,
                              "direccion": "SUBE" if variation > 0 else "BAJA",
                              "precio_actual": row["precio_actual"]})
        items.sort(key=lambda item: abs(item["var_pct"]), reverse=True)
        return {"fecha": max((row["fecha"] for row in rows), default=None), "alertas": items}

    def compare(self, producto_id: str) -> list[dict]:
        with self._connect() as conn:
            return self._rows(conn.execute(
                """SELECT v.mercado_id,m.ciudad,v.precio_actual,v.var_1w_pct
                FROM v_variacion v JOIN dim_mercado m USING(mercado_id)
                WHERE producto_id=? ORDER BY precio_actual""", [producto_id]
            ))

    def health(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("""SELECT max(fecha),count(DISTINCT fecha),
                100.0*avg(CASE WHEN fuente='seed' THEN 1 ELSE 0 END),count(DISTINCT producto_id),
                count(DISTINCT mercado_id) FROM fact_precio""").fetchone()
            source = conn.execute("SELECT fuente FROM ingest_log WHERE status='ok' ORDER BY finished_at DESC LIMIT 1").fetchone()
        return {"status": "ok", "fuente_activa": source[0] if source else "sin_datos",
                "ultima_fecha": row[0], "semanas_disponibles": row[1], "pct_seed": round(row[2] or 0, 2),
                "productos": row[3], "mercados": row[4]}
