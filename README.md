# Abasto AI — Feature Harness

Motor de producto para convertir observaciones de precios de alimentos en recomendaciones explicables. Está pensado como el núcleo del MVP: no contiene un dashboard ni modelos de ML pesados.

## Qué incluye

- consumidores: ofertas, caídas semanales, compras favorables/urgentes, sustitutos, canastas y comparación por ciudad;
- tenderos: ranking de abastecimiento, canasta básica y alertas de cambio;
- restaurantes: ingredientes favorables, sustituciones y costo/sugerencia de menú;
- analítica: histórico, índice Abasto, rankings de volatilidad y crecimiento;
- pronóstico base a 7/30 días con señal `SUBIR`, `BAJAR` o `ESTABLE` e intervalo de confianza;
- adaptador de Supabase y repositorio en memoria para desarrollo y pruebas.

## Contrato mínimo de entrada

Una fila por observación, con estas columnas/campos:

```json
{
  "date": "2026-09-12",
  "city": "Bogotá",
  "product": "papa pastusa",
  "price": 2400
}
```

Campos opcionales: `market`, `category`, `unit`, `product_id`. Los precios solo se comparan dentro de la misma unidad; si no llega `unit`, se usa `unidad`.

## Puesta en marcha

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m abasto_ai.demo
```

Para Supabase, instala el extra y define las variables de `.env.example` en el entorno. La tabla debe poder seleccionarse y usar los nombres de columnas del contrato mínimo (o sus alias en español: `fecha`, `ciudad`, `producto`, `precio`, `central`, `categoria`, `unidad`).

```bash
python -m pip install -e ".[supabase]"
```

## Uso del motor

```python
from datetime import date
from abasto_ai.engine import FeatureEngine
from abasto_ai.repository import InMemoryPriceRepository

engine = FeatureEngine(InMemoryPriceRepository(rows))
snapshot = engine.consumer_snapshot(city="Bogotá", as_of=date(2026, 9, 12))
print(snapshot["cheap_today"])
```

## Decisiones y límites del MVP

- El forecast es una tendencia lineal de corto plazo sobre hasta 28 observaciones recientes, no una promesa de precio futuro.
- Una alerta se genera cuando la variación semanal supera el 8 % o cuando la señal proyectada es de subida.
- Las equivalencias no se infieren: se configuran por grupo para evitar sustituciones culinarias/comerciales erróneas.
- La canasta usa una lista explícita de productos y selecciona el menor precio disponible por producto; no presupone cantidades.

## Información necesaria antes de producción

1. Unidad normalizada y, cuando aplique, peso/conversión (kg, libra, unidad, bulto).
2. Identificador estable de producto y catálogo con categoría.
3. Identificador de central/mercado y reglas de cobertura de datos.
4. Grupos de sustitución aprobados y, para restaurantes, recetas, rendimientos y porciones.
5. Definición de canasta básica por segmento y cantidades.
6. Zona horaria, moneda y política para precios faltantes/outliers.

Sin estos datos, las funciones principales corren, pero las comparaciones, canastas y sustitutos tendrán precisión limitada.

## Priorización aplicada

El núcleo implementado resuelve primero decisión de compra y abastecimiento: ranking de precios, caídas/alertas, canastas, comparación de mercados, sustitutos y forecast. Las recomendaciones de menú se ordenan por costo de ingredientes disponible.

Se dejan para una siguiente iteración, porque exigen datos que todavía no están en el contrato: promociones/combos y margen (ventas, demanda y precio de carta); recetas con sustitución automática (rendimiento y equivalencia culinaria); y señales de inversión avanzadas como ciclos, cambios estructurales, correlaciones y backtesting. `price_history`, `investor_rankings` e `abasto_index` ya son la base para construirlas.
