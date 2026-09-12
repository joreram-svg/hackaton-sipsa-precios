from datetime import date
from typing import Literal

from pydantic import BaseModel


class Product(BaseModel):
    producto_id: str
    nombre: str
    categoria: str
    unidad_base: str


class Market(BaseModel):
    mercado_id: str
    nombre: str
    ciudad: str


class PricePoint(BaseModel):
    fecha: date
    precio_prom: float
    precio_min: float | None
    precio_max: float | None
    fuente: str


class PriceSeries(BaseModel):
    producto_id: str
    mercado_id: str
    unidad: Literal["COP/kg"] = "COP/kg"
    serie: list[PricePoint]


class OportunidadItem(BaseModel):
    producto_id: str
    nombre: str
    categoria: str
    mercado_id: str
    precio_actual: float
    precio_1w: float
    precio_4w: float
    var_1w_pct: float
    var_4w_pct: float
    percentil_hist: float
    score: float
    senal: Literal["COMPRAR", "NEUTRAL", "EVITAR"]
    razon: str


class Opportunities(BaseModel):
    fecha: date | None
    ciudad: str
    perfil: str
    items: list[OportunidadItem]


class TrendPoint(BaseModel):
    fecha: date
    precio_prom: float


class Trend(BaseModel):
    producto_id: str
    mercado_id: str
    serie: list[TrendPoint]
    var_1w_pct: float | None
    var_4w_pct: float | None
    var_52w_pct: float | None
    percentil_hist: float
    pendiente_pct_sem: float | None


class Forecast(BaseModel):
    producto_id: str
    mercado_id: str
    horizonte_semanas: int
    precio_actual: float
    precio_esperado: float
    banda_inf: float
    banda_sup: float
    var_esperada_pct: float
    metodo: Literal["ma4+estacional"]


class AlertItem(BaseModel):
    producto_id: str
    nombre: str
    mercado_id: str
    var_pct: float
    direccion: Literal["SUBE", "BAJA"]
    precio_actual: float


class Alerts(BaseModel):
    fecha: date | None
    alertas: list[AlertItem]


class WeeklySummary(BaseModel):
    fecha: date | None
    ciudad: str
    perfil: str
    top_comprar: list[OportunidadItem]
    top_evitar: list[OportunidadItem]
    alertas: list[AlertItem]
    texto: str


class Comparison(BaseModel):
    mercado_id: str
    ciudad: str
    precio_actual: float
    var_1w_pct: float | None

