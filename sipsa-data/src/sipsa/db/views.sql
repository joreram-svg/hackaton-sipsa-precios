CREATE OR REPLACE VIEW v_ultima_semana AS
SELECT ciudad, max(fecha) AS fecha
FROM fact_precio
GROUP BY ciudad;

CREATE OR REPLACE VIEW v_variacion AS
WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY producto_id, ciudad ORDER BY fecha DESC) AS rn
  FROM fact_precio
), values_by_period AS (
  SELECT producto_id, ciudad,
    max(fecha) FILTER (rn = 1) AS fecha,
    max(precio) FILTER (rn = 1) AS precio_actual,
    max(precio) FILTER (rn = 2) AS precio_1w,
    max(precio) FILTER (rn = 5) AS precio_4w,
    max(precio) FILTER (rn = 53) AS precio_52w
  FROM ranked
  GROUP BY producto_id, ciudad
)
SELECT *,
  CASE WHEN precio_1w > 0 THEN precio_actual / precio_1w - 1 END AS var_1w_pct,
  CASE WHEN precio_4w > 0 THEN precio_actual / precio_4w - 1 END AS var_4w_pct,
  CASE WHEN precio_52w > 0 THEN precio_actual / precio_52w - 1 END AS var_52w_pct
FROM values_by_period;

CREATE OR REPLACE VIEW v_percentil AS
WITH current_prices AS (
  SELECT f.* FROM fact_precio f
  JOIN v_ultima_semana u ON f.ciudad = u.ciudad AND f.fecha = u.fecha
)
SELECT c.producto_id, c.ciudad,
  CASE WHEN count(h.precio) <= 1 THEN 0.5
       ELSE (sum(CASE WHEN h.precio <= c.precio THEN 1 ELSE 0 END) - 1.0)
            / (count(h.precio) - 1.0) END AS percentil_hist
FROM current_prices c
JOIN fact_precio h ON h.producto_id = c.producto_id AND h.ciudad = c.ciudad
  AND h.fecha BETWEEN c.fecha - INTERVAL 103 WEEK AND c.fecha
GROUP BY c.producto_id, c.ciudad, c.precio;

CREATE OR REPLACE VIEW v_tendencia AS
WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY producto_id, ciudad ORDER BY fecha DESC) AS rn
  FROM fact_precio
), recent AS (
  SELECT * FROM ranked WHERE rn <= 8
)
SELECT producto_id, ciudad,
  100 * regr_slope(precio, epoch(fecha) / 604800.0) / nullif(avg(precio), 0)
    AS pendiente_pct_sem
FROM recent
GROUP BY producto_id, ciudad;
