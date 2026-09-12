CREATE OR REPLACE VIEW v_ultima_semana AS
SELECT mercado_id, max(fecha) AS fecha
FROM fact_precio
GROUP BY mercado_id;

CREATE OR REPLACE VIEW v_variacion AS
WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY producto_id, mercado_id ORDER BY fecha DESC) AS rn
  FROM fact_precio
), values_by_period AS (
  SELECT producto_id, mercado_id,
    max(fecha) FILTER (rn = 1) AS fecha,
    max(precio_prom) FILTER (rn = 1) AS precio_actual,
    max(precio_prom) FILTER (rn = 2) AS precio_1w,
    max(precio_prom) FILTER (rn = 5) AS precio_4w,
    max(precio_prom) FILTER (rn = 53) AS precio_52w
  FROM ranked
  GROUP BY producto_id, mercado_id
)
SELECT *,
  CASE WHEN precio_1w > 0 THEN precio_actual / precio_1w - 1 END AS var_1w_pct,
  CASE WHEN precio_4w > 0 THEN precio_actual / precio_4w - 1 END AS var_4w_pct,
  CASE WHEN precio_52w > 0 THEN precio_actual / precio_52w - 1 END AS var_52w_pct
FROM values_by_period;

CREATE OR REPLACE VIEW v_percentil AS
WITH current_prices AS (
  SELECT f.* FROM fact_precio f
  JOIN v_ultima_semana u ON f.mercado_id = u.mercado_id AND f.fecha = u.fecha
)
SELECT c.producto_id, c.mercado_id,
  CASE WHEN count(h.precio_prom) <= 1 THEN 0.5
       ELSE (sum(CASE WHEN h.precio_prom <= c.precio_prom THEN 1 ELSE 0 END) - 1.0)
            / (count(h.precio_prom) - 1.0) END AS percentil_hist
FROM current_prices c
JOIN fact_precio h ON h.producto_id = c.producto_id AND h.mercado_id = c.mercado_id
  AND h.fecha BETWEEN c.fecha - INTERVAL 103 WEEK AND c.fecha
GROUP BY c.producto_id, c.mercado_id, c.precio_prom;

CREATE OR REPLACE VIEW v_tendencia AS
WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY producto_id, mercado_id ORDER BY fecha DESC) AS rn
  FROM fact_precio
), recent AS (
  SELECT * FROM ranked WHERE rn <= 8
)
SELECT producto_id, mercado_id,
  100 * regr_slope(precio_prom, epoch(fecha) / 604800.0) / nullif(avg(precio_prom), 0)
    AS pendiente_pct_sem
FROM recent
GROUP BY producto_id, mercado_id;

