import argparse
import logging

try:
    from fastmcp import FastMCP

    FASTMCP_AVAILABLE = True
except ModuleNotFoundError:
    FASTMCP_AVAILABLE = False

    class FastMCP:  # type: ignore[no-redef]
        """Permite importar y probar las tools cuando falta la dependencia opcional."""

        def __init__(self, _name: str):
            self.tools = {}

        def tool(self, function):
            self.tools[function.__name__] = function
            return function

        def run(self, **_kwargs):
            raise RuntimeError("Falta fastmcp>=2.0; instálelo para arrancar el servidor MCP")

from sipsa.analytics.forecast import forecast
from sipsa.config import get_settings
from sipsa.db.repo import Repository
from sipsa.service import build_weekly_summary


LOGGER = logging.getLogger(__name__)
mcp = FastMCP("SIPSA Data")


def get_repository() -> Repository:
    return Repository()


@mcp.tool
def listar_productos(categoria: str | None = None) -> list[dict]:
    """Lista productos disponibles; use categoría para limitar los resultados."""
    return get_repository().list_products(categoria)


@mcp.tool
def mejores_precios(
    ciudad: str = "Bogotá",
    categoria: str | None = None,
    perfil: str = "consumidor",
    top: int = 10,
) -> dict:
    """Busca las mejores oportunidades de compra para una ciudad y perfil."""
    return get_repository().opportunities(ciudad, categoria, perfil, top)


@mcp.tool
def productos_a_evitar(
    ciudad: str = "Bogotá",
    categoria: str | None = None,
    top: int = 10,
) -> dict:
    """Devuelve los productos con peor momento de compra en la ciudad."""
    return get_repository().opportunities(ciudad, categoria, "consumidor", top, True)


@mcp.tool
def tendencia_producto(producto_id: str, ciudad: str = "Bogotá", semanas: int = 12) -> dict:
    """Consulta la historia y variaciones recientes de un producto por ciudad."""
    return get_repository().trend(producto_id, ciudad, semanas)


@mcp.tool
def pronostico_producto(producto_id: str, ciudad: str = "Bogotá", horizonte: int = 2) -> dict:
    """Pronostica entre una y cuatro semanas el precio de un producto."""
    repo = get_repository()
    return forecast(producto_id, ciudad, horizonte, repo)


@mcp.tool
def alertas_precio(ciudad: str = "Bogotá", umbral_pct: float = 15, ventana: str = "1w") -> dict:
    """Lista subidas y bajadas que superan el umbral indicado."""
    return get_repository().alerts(ciudad, umbral_pct, ventana)


@mcp.tool
def resumen_semanal(ciudad: str = "Bogotá", perfil: str = "consumidor") -> dict:
    """Genera el resumen semanal en español listo para compartir."""
    return build_weekly_summary(get_repository(), ciudad, perfil)


@mcp.tool
def comparar_ciudades(producto_id: str) -> list[dict]:
    """Compara el precio actual del producto entre ciudades."""
    return get_repository().compare(producto_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Servidor MCP de SIPSA Data")
    parser.add_argument("--transport", choices=["stdio", "sse", "http"], default="stdio")
    args = parser.parse_args()
    if not FASTMCP_AVAILABLE:
        LOGGER.error("Falta fastmcp>=2.0; instálelo para arrancar el servidor MCP")
        return 0
    settings = get_settings()
    options = {"transport": args.transport}
    if args.transport != "stdio":
        options.update({"host": "127.0.0.1", "port": settings.mcp_port})
    mcp.run(**options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
