from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import duckdb

from sipsa.analytics.forecast import forecast
from sipsa.api.models import (
    Alerts,
    City,
    Comparison,
    Forecast,
    Opportunities,
    PriceSeries,
    Product,
    Trend,
    WeeklySummary,
)
from sipsa.config import PROJECT_ROOT, get_settings
from sipsa.db.repo import Repository
from sipsa.service import build_weekly_summary
from sipsa.snapshot import load_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    from sipsa.scheduler import create_scheduler

    scheduler = create_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="SIPSA Data", version="1.0.0", lifespan=lifespan)


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


@app.get("/v1/ciudades", response_model=list[City])
def ciudades(repo: Repository = Depends(get_repo)):
    return repo.list_cities()


@app.get("/v1/precios", response_model=PriceSeries)
def precios(
    producto_id: str,
    ciudad: str = "Bogotá",
    desde: date | None = None,
    hasta: date | None = None,
    repo: Repository = Depends(get_repo),
):
    serie = repo.price_history(producto_id, ciudad, desde, hasta)
    if not serie:
        raise LookupError(f"Producto o serie no encontrada: {producto_id}")
    return {"producto_id": producto_id, "ciudad": ciudad, "unidad": "COP/kg", "serie": serie}


def _opportunities(repo, ciudad, categoria, perfil, top, ascending=False):
    return repo.opportunities(ciudad, categoria, perfil, top, ascending)


def _snapshot_response(kind: str, ciudad: str, perfil: str) -> JSONResponse:
    return JSONResponse(
        content=load_snapshot(kind, ciudad, perfil),
        headers={"X-Data-Mode": "snapshot"},
    )


@app.get("/v1/oportunidades", response_model=Opportunities)
def oportunidades(
    ciudad: str = "Bogotá",
    categoria: str | None = None,
    perfil: Literal["consumidor", "restaurante", "mayorista"] = "consumidor",
    top: int = Query(10, ge=1, le=100),
    repo: Repository = Depends(get_repo),
):
    try:
        return _opportunities(repo, ciudad, categoria, perfil, top)
    except (OSError, duckdb.Error):
        return _snapshot_response("oportunidades", ciudad, perfil)


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
    ciudad: str = "Bogotá",
    semanas: int = Query(12, ge=1, le=104),
    repo: Repository = Depends(get_repo),
):
    return repo.trend(producto_id, ciudad, semanas)


@app.get("/v1/forecast/{producto_id}", response_model=Forecast)
def pronostico(
    producto_id: str,
    ciudad: str = "Bogotá",
    horizonte: int = Query(2, ge=1, le=4),
    repo: Repository = Depends(get_repo),
):
    return forecast(producto_id, ciudad, horizonte, repo)


@app.get("/v1/alertas", response_model=Alerts)
def alertas(
    ciudad: str = "Bogotá",
    umbral_pct: float = Query(15, ge=0),
    ventana: Literal["1w", "4w"] = "1w",
    repo: Repository = Depends(get_repo),
):
    return repo.alerts(ciudad, umbral_pct, ventana)


@app.get("/v1/resumen-semanal", response_model=WeeklySummary)
def resumen_semanal(
    ciudad: str = "Bogotá",
    perfil: Literal["consumidor", "restaurante", "mayorista"] = "consumidor",
    repo: Repository = Depends(get_repo),
):
    try:
        return build_weekly_summary(repo, ciudad, perfil)
    except (OSError, duckdb.Error):
        return _snapshot_response("resumen", ciudad, perfil)


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
    from sipsa.snapshot import make_snapshot

    return {"archivos": make_snapshot()}


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "web", html=True), name="web")
