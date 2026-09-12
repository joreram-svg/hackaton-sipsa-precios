# Revisión de tablas de recomendaciones en Supabase

Fecha de revisión: 2026-09-12  
Alcance: inspección de `public.recomendaciones_restaurante`, `public.recomendaciones_consumidor` y `public.recomendaciones_tendero` contra `dim_producto`, `fact_precio` y `fact_abastecimiento`.

Todas las consultas se ejecutaron con `transaction_read_only = on`. Solo se usaron consultas de lectura y se cerró cada transacción con `ROLLBACK`.

## Resumen ejecutivo

| Tabla | Filas | Cobertura | Ciudades | Propósito observado |
|---|---:|---|---:|---|
| `recomendaciones_restaurante` | 200 | `fecha` y `fuente_fecha`: 2026-09-07 | 20 | Diez tipos de recomendación para restaurantes: ingredientes favorables/temporada y futuros casos de menú, platos, promociones, combos, sustituciones y simulación de costos. |
| `recomendaciones_consumidor` | 180 | `fecha` y `fuente_fecha`: 2026-09-07 | 20 | Nueve tipos para consumidores: productos baratos, caídas, oportunidades y compras antes de alzas; cuatro tipos de canasta/equivalencias/comparación aún requieren configuración. |
| `recomendaciones_tendero` | 160 | `fecha` y `fuente_fecha`: 2026-09-07 | 20 | Ocho tipos para tenderos: caídas, tendencias, alertas y ranking; abastecimiento está limitado por rezago de la fuente y otros casos requieren configuración. |

Las tres tablas contienen una fila por combinación de `fecha`, `ciudad` y `tipo`; su carga actual cubre las mismas 20 ciudades presentes en `fact_precio`. Todos los registros tienen `fecha = fuente_fecha`.

## `public.recomendaciones_restaurante`

### Esquema

| Pos. | Columna | Tipo | Nullable | Default / generación |
|---:|---|---|---|---|
| 1 | `id` | `bigint` | No | Identity `ALWAYS` |
| 2 | `fecha` | `date` | No | Sin default |
| 3 | `ciudad` | `varchar(100)` | No | Sin default |
| 4 | `tipo` | `varchar(100)` | No | Sin default |
| 5 | `estado` | `varchar(32)` | No | Sin default |
| 6 | `contenido` | `jsonb` | No | Sin default |
| 7 | `fuente_fecha` | `date` | No | Sin default |
| 8 | `created_at` | `timestamptz` | No | `now()` |
| 9 | `updated_at` | `timestamptz` | No | `now()` |

Restricciones: PK `id`; `UNIQUE (fecha, ciudad, tipo)`; `estado` limitado por `CHECK` a `disponible`, `limitada` o `requiere_configuracion`. No tiene foreign keys.

Conteo y contenido: 200 filas, diez tipos por cada una de las 20 ciudades. Por estado: 20 `disponible`, 20 `limitada` y 160 `requiere_configuracion`. Los elementos de `contenido.items` usan `ingrediente`, `producto_id`, `categoria`, `unidad`, `precio_actual`, `percentil_historico`, `tendencia_semanal_pct` y `variacion_1_semana_pct`. Hay 68 elementos y ocho productos distintos.

### Muestra de 3 filas

`contenido` se presenta de forma compacta: mensaje, total de elementos y hasta dos elementos reales.

| id | fecha / ciudad | tipo / estado | contenido (resumen real) | fuente_fecha | created_at / updated_at |
|---:|---|---|---|---|---|
| 1 | 2026-09-07 / Bucaramanga | `productos_temporada` / `limitada` | Mensaje: "Proxy de temporada: precio en el 25% histórico más bajo. Confirmar con calendario agrícola." 2 items: Banano (`banano`, frutas, kg, 2761.0, percentil 0.0874, tendencia 0.1057%, variación 0.0468%) y Zanahoria (`zanahoria`, verduras, kg, 1400.0, percentil 0.2136, tendencia -5.7593%, variación 0.0165%). | 2026-09-07 | 2026-09-12 19:44:55.728376+00 / igual |
| 2 | 2026-09-07 / Bucaramanga | `ingredientes_precio_favorable` / `disponible` | Mensaje: "Ingredientes con precio histórico bajo y sin alza semanal." 1 item: Aguacate (`aguacate`, frutas, kg, 8916.67, percentil 0.27, tendencia 0.1831%, variación -0.0093%). | 2026-09-07 | 2026-09-12 19:44:55.728376+00 / igual |
| 3 | 2026-09-07 / Bucaramanga | `platos_segun_costo_ingredientes` / `requiere_configuracion` | Mensaje: "Faltan recetas, cantidades, rendimiento y número de porciones." 0 items. | 2026-09-07 | 2026-09-12 19:44:55.728376+00 / igual |

## `public.recomendaciones_consumidor`

### Esquema

| Pos. | Columna | Tipo | Nullable | Default / generación |
|---:|---|---|---|---|
| 1 | `id` | `bigint` | No | Identity `ALWAYS` |
| 2 | `fecha` | `date` | No | Sin default |
| 3 | `ciudad` | `varchar(100)` | No | Sin default |
| 4 | `tipo` | `varchar(100)` | No | Sin default |
| 5 | `estado` | `varchar(32)` | No | Sin default |
| 6 | `contenido` | `jsonb` | No | Sin default |
| 7 | `fuente_fecha` | `date` | No | Sin default |
| 8 | `created_at` | `timestamptz` | No | `now()` |
| 9 | `updated_at` | `timestamptz` | No | `now()` |

Restricciones: PK `id`; `UNIQUE (fecha, ciudad, tipo)`; el mismo `CHECK` de tres estados. No tiene foreign keys.

Conteo y contenido: 180 filas, nueve tipos por cada una de las 20 ciudades. Por estado: 100 `disponible` y 80 `requiere_configuracion`. Los elementos de `contenido.items` usan `producto`, `producto_id`, `categoria`, `unidad`, `precio_actual`, `percentil_historico`, `tendencia_semanal_pct` y `variacion_1_semana_pct`. Hay 738 elementos y 23 productos distintos.

### Muestra de 3 filas

| id | fecha / ciudad | tipo / estado | contenido (resumen real) | fuente_fecha | created_at / updated_at |
|---:|---|---|---|---|---|
| 1 | 2026-09-07 / Bucaramanga | `10_productos_mas_baratos` / `disponible` | Mensaje: "Productos con menor percentil de precio histórico disponible." 10 items; primeros dos: Banano (`banano`, frutas, kg, 2761.0, percentil 0.0874, tendencia 0.1057%, variación 0.0468%) y Zanahoria (`zanahoria`, verduras, kg, 1400.0, percentil 0.2136, tendencia -5.7593%, variación 0.0165%). | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |
| 2 | 2026-09-07 / Bucaramanga | `productos_bajaron_semana` / `disponible` | Mensaje: "Productos con mayor caída frente a una semana." 9 items; primeros dos: Maracuyá (`maracuya`, frutas, kg, 5000.0, percentil 0.8447, tendencia 3.0953%, variación -0.1643%) y Cebolla cabezona (`cebolla_cabezona`, verduras, kg, 2566.67, percentil 0.8738, tendencia 0.9212%, variación -0.102%). | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |
| 3 | 2026-09-07 / Bucaramanga | `favorables_comprar` / `disponible` | Mensaje: "Precio históricamente bajo y sin alza semanal." 0 items. | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |

## `public.recomendaciones_tendero`

### Esquema

| Pos. | Columna | Tipo | Nullable | Default / generación |
|---:|---|---|---|---|
| 1 | `id` | `bigint` | No | Identity `ALWAYS` |
| 2 | `fecha` | `date` | No | Sin default |
| 3 | `ciudad` | `varchar(100)` | No | Sin default |
| 4 | `tipo` | `varchar(100)` | No | Sin default |
| 5 | `estado` | `varchar(32)` | No | Sin default |
| 6 | `contenido` | `jsonb` | No | Sin default |
| 7 | `fuente_fecha` | `date` | No | Sin default |
| 8 | `created_at` | `timestamptz` | No | `now()` |
| 9 | `updated_at` | `timestamptz` | No | `now()` |

Restricciones: PK `id`; `UNIQUE (fecha, ciudad, tipo)`; el mismo `CHECK` de tres estados. No tiene foreign keys.

Conteo y contenido: 160 filas, ocho tipos por cada una de las 20 ciudades. Por estado: 100 `disponible`, 20 `limitada` y 40 `requiere_configuracion`. Los elementos de `contenido.items` tienen la misma forma que en consumidor. Hay 631 elementos y 23 productos distintos.

### Muestra de 3 filas

| id | fecha / ciudad | tipo / estado | contenido (resumen real) | fuente_fecha | created_at / updated_at |
|---:|---|---|---|---|---|
| 1 | 2026-09-07 / Bucaramanga | `canasta_basica_favorable` / `requiere_configuracion` | Mensaje: "Falta definir la canasta básica y cantidades para el tendero." 0 items. | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |
| 2 | 2026-09-07 / Bucaramanga | `productos_caida_precio` / `disponible` | Mensaje: "Productos con mayor caída de precio semanal." 9 items; primeros dos: Maracuyá (`maracuya`, frutas, kg, 5000.0, percentil 0.8447, tendencia 3.0953%, variación -0.1643%) y Cebolla cabezona (`cebolla_cabezona`, verduras, kg, 2566.67, percentil 0.8738, tendencia 0.9212%, variación -0.102%). | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |
| 3 | 2026-09-07 / Bucaramanga | `productos_tendencia_favorable` / `disponible` | Mensaje: "Productos con tendencia semanal de precio descendente." 5 items; primeros dos: Cebolla larga (`cebolla_larga`, verduras, kg, 1844.67, percentil 0.3301, tendencia -6.5447%, variación 0.034%) y Zanahoria (`zanahoria`, verduras, kg, 1400.0, percentil 0.2136, tendencia -5.7593%, variación 0.0165%). | 2026-09-07 | 2026-09-12 19:40:36.679785+00 / igual |

## Compatibilidad y relación con el esquema SIPSA

- **Foreign keys:** ninguna de las tres tablas declara foreign keys. `producto_id` no es una columna relacional: vive dentro de cada objeto de `contenido.items`. Por tanto, PostgreSQL no puede imponer integridad referencial sobre esos IDs.
- **Productos:** se inspeccionaron los 1.437 elementos JSON de las tres tablas (68 + 738 + 631). Todos tienen `producto_id`; los 1.437 encuentran correspondencia en `dim_producto`. No hubo discrepancias de nombre/ingrediente, categoría ni unidad frente a la dimensión.
- **Precios:** los 1.437 elementos encuentran una fila en `fact_precio` con el mismo `producto_id`, `ciudad` y `fuente_fecha`. `precio_actual` coincide con `fact_precio.precio` al redondear ambos a dos decimales; hubo cero discrepancias.
- **Ciudad y fecha:** las 540 filas de recomendación encuentran datos en `fact_precio` para su par `ciudad`/`fuente_fecha`. `fecha` y `fuente_fecha` son `date`, como `fact_precio.fecha`; `ciudad` es `varchar(100)`, compatible con el `varchar` sin límite explícito de las tablas SIPSA. Las 20 ciudades usadas coinciden con las 20 de `fact_precio`.
- **Abastecimiento:** `fact_abastecimiento` llega hasta 2026-07-01, mientras las recomendaciones usan 2026-09-07. Por eso no hay coincidencias exactas por fecha con los items actuales. Las 20 filas `recomendacion_abastecimiento` de tendero están correctamente marcadas `limitada`, contienen cero items y explican el rezago de la fuente.
- **Forma del JSON:** todos los valores `contenido` son objetos y todos incluyen `items` como arreglo. Esta consistencia es real en la carga revisada, pero no está garantizada por una FK ni por un esquema JSON declarado en PostgreSQL.

## Conflictos, colisiones y coordinación requerida

No hay colisión de nombres de tabla con `dim_producto`, `fact_precio`, `fact_abastecimiento` o `ingest_log`, ni incompatibilidad actual de tipos en las claves lógicas compartidas. La restricción de longitud `varchar(100)` para `ciudad` es más estrecha que el `varchar` de SIPSA, aunque no causa problemas con los valores actuales.

El riesgo principal no está en los datos actuales, sino en el contrato entre componentes:

1. Las tablas fueron creadas directamente en la base y no están representadas en el esquema versionado del pipeline; esto es deriva de esquema y deja sin una fuente de verdad compartida su creación, restricciones y propiedad.
2. La lógica de recomendaciones depende de IDs, ciudades, fechas y precios de SIPSA mediante JSON, sin foreign keys. Un cambio de `producto_id`, normalización de ciudad o calendario de carga puede dejar recomendaciones huérfanas o desactualizadas sin que PostgreSQL lo impida.
3. Debe acordarse quién regenera las recomendaciones después de cada carga SIPSA, qué significa `fecha` frente a `fuente_fecha`, qué antigüedad máxima se acepta y cómo se versiona/valida la estructura de `contenido`.
4. Para abastecimiento, se necesita coordinar la actualización de `fact_abastecimiento` antes de habilitar esa recomendación como actual; la protección `limitada` observada es adecuada mientras persista el rezago.

Conclusión: la carga revisada es compatible y consistente con `dim_producto` y `fact_precio`, pero el acoplamiento es implícito y no protegido. La coordinación prioritaria es formalizar el contrato de regeneración y de esquema/propiedad entre el pipeline SIPSA y la lógica de recomendaciones.
