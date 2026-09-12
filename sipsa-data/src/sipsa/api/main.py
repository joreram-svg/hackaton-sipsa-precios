from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sipsa.analytics.forecast import forecast
from sipsa.api.models import (
    Alerts,
    Comparison,
    Forecast,
    Market,
    Opportunities,
    PriceSeries,
    Product,
    Trend,
    WeeklySummary,
)
from sipsa.config import get_settings
from sipsa.db.repo import Repository


app = FastAPI(title="SIPSA Data", version="1.0.0")


def get_repo() -> Repository:
    return Repository()


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return error_response(400, "BAD_REQUEST", str(exc.errors()[0].get("msg", "Parámetro inválido")))


@app.exception_handler(ValueError)
async def bad_request(_: Request, exc: ValueError):
    return error_response(400, "BAD_REQUEST", str(exc))


@app.exception_handler(LookupError)
async def not_found(_: Request, exc: LookupError):
    return error_response(404, "NOT_FOUND", str(exc))


@app.get("/v1/health")
def health(repo: Repository = Depends(get_repo)):
    return repo.health()


@app.get("/v1/productos", response_model=list[Product])
def productos(categoria: str | None = None, repo: Repository = Depends(get_repo)):
    return repo.list_products(categoria)


@app.get("/v1/mercados", response_model=list[Market])
def mercados(ciudad: str | None = None, repo: Repository = Depends(get_repo)):
    return repo.list_markets(ciudad)


@app.get("/v1/precios", response_model=PriceSeries)
def precios(
    producto_id: str,
    mercado_id: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    repo: Repository = Depends(get_repo),
):
    mercado_id = mercado_id or repo.default_market()
    serie = repo.price_history(producto_id, mercado_id, desde, hasta)
    if not serie:
        raise LookupError(f"Producto o serie no encontrada: {producto_id}")
    return {"producto_id": producto_id, "mercado_id": mercado_id, "unidad": "COP/kg", "serie": serie}


def _opportunities(repo, ciudad, categoria, perfil, top, ascending=False):
    return repo.opportunities(ciudad, categoria, perfil, top, ascending)


@app.get("/v1/oportunidades", response_model=Opportunities)
def oportunidades(
    ciudad: str = "Bogotá",
    categoria: str | None = None,
    perfil: Literal["consumidor", "restaurante", "mayorista"] = "consumidor",
    top: int = Query(10, ge=1, le=100),
    repo: Repository = Depends(get_repo),
):
    return _opportunities(repo, ciudad, categoria, perfil, top)


@app.get("/v1/evitar", response_model=Opportunities)
def evitar(
    ciudad: str = "Bogotá",
    categoria: str | None = None,
    perfil: Literal["consumidor", "restaurante", "mayorista"] = "consumidor",
    top: int = Query(10, ge=1, le=100),
    repo: Repository = Depends(get_repo),
):
    return _opportunities(repo, ciudad, categoria, perfil, top, True)


@app.get("/v1/tendencia/{producto_id}", response_model=Trend)
def tendencia(
    producto_id: str,
    mercado_id: str | None = None,
    semanas: int = Query(12, ge=1, le=104),
    repo: Repository = Depends(get_repo),
):
    return repo.trend(producto_id, mercado_id, semanas)


@app.get("/v1/forecast/{producto_id}", response_model=Forecast)
def pronostico(
    producto_id: str,
    mercado_id: str | None = None,
    horizonte: int = Query(2, ge=1, le=4),
    repo: Repository = Depends(get_repo),
):
    mercado_id = mercado_id or repo.default_market()
    return forecast(producto_id, mercado_id, horizonte, repo)


@app.get("/v1/alertas", response_model=Alerts)
def alertas(
    ciudad: str = "Bogotá",
    umbral_pct: float = Query(15, ge=0),
    ventana: Literal["1w", "4w"] = "1w",
    repo: Repository = Depends(get_repo),
):
    return repo.alerts(ciudad, umbral_pct, ventana)


def build_weekly_summary(repo, ciudad="Bogotá", perfil="consumidor") -> dict:
    buy = repo.opportunities(ciudad, None, perfil, 5, False)
    avoid = repo.opportunities(ciudad, None, perfil, 5, True)
    alert_data = repo.alerts(ciudad, 15, "1w")
    buy_names = ", ".join(item["nombre"] for item in buy["items"])
    avoid_names = ", ".join(item["nombre"] for item in avoid["items"])
    text = f"📊 SIPSA {ciudad}: ↑ Comprar: {buy_names}. ↓ Evitar: {avoid_names}."
    if alert_data["alertas"]:
        first = alert_data["alertas"][0]
        text += f" Alerta: {first['nombre']} {first['direccion'].lower()} {abs(first['var_pct']) * 100:.0f}%."
    return {"fecha": buy["fecha"], "ciudad": ciudad, "perfil": perfil,
            "top_comprar": buy["items"], "top_evitar": avoid["items"],
            "alertas": alert_data["alertas"], "texto": text[:600]}


@app.get("/v1/resumen-semanal", response_model=WeeklySummary)
def resumen_semanal(
    ciudad: str = "Bogotá",
    perfil: Literal["consumidor", "restaurante", "mayorista"] = "consumidor",
    repo: Repository = Depends(get_repo),
):
    return build_weekly_summary(repo, ciudad, perfil)


@app.get("/v1/comparar", response_model=list[Comparison])
def comparar(producto_id: str, repo: Repository = Depends(get_repo)):
    rows = repo.compare(producto_id)
    if not rows:
        raise LookupError(f"Producto no encontrado: {producto_id}")
    return rows


def require_admin(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    if x_admin_token != get_settings().admin_token:
        raise ValueError("X-Admin-Token inválido")


@app.post("/v1/admin/ingest", dependencies=[Depends(require_admin)])
def admin_ingest():
    from sipsa.ingest.pipeline import run_ingest

    return run_ingest("auto")


@app.post("/v1/admin/snapshot", dependencies=[Depends(require_admin)])
def admin_snapshot():
    from scripts.make_snapshot import make_snapshot

    return {"archivos": make_snapshot()}
