# SIPSA Data

Servicio local de precios mayoristas semanales para Colombia. Ingiere fuentes DANE cuando están disponibles, conserva un histórico DuckDB a nivel `fecha + producto + ciudad`, calcula señales y las expone por REST, MCP, dashboard web y Telegram. Si una fuente externa o la base no responden, la demo degrada a seed o snapshot sin ocultarlo.

## Requisitos e instalación

- Python 3.11 o superior.
- PowerShell 7/Windows PowerShell.
- `uv` recomendado; `pip` funciona como alternativa.

Desde este directorio:

```powershell
# Con uv
uv sync --extra dev

# Alternativa con pip
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

En una sesión donde el paquete no esté instalado editable, configure la ruta fuente antes de los comandos:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
```

Copie la configuración y cambie los valores necesarios:

```powershell
Copy-Item .env.example .env
```

Variables principales: `DB_PATH`, `ADMIN_TOKEN`, `SOURCE_PRIORITY`, `SOCRATA_DATASET_ID`, `CIUDADES`, `HIST_WEEKS`, `API_PORT`, `MCP_PORT`, `TZ`, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_IDS`.

## Arranque exacto

### 1. Bootstrap

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python scripts/bootstrap.py --source auto
```

`--source auto` prueba `excel_dane`, `soap_dane`, `socrata` y por último `seed`. Para una demo determinista sin red:

```powershell
python scripts/bootstrap.py --source seed
```

### 2. API REST y dashboard

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m uvicorn sipsa.api.main:app --host 127.0.0.1 --port 8000
```

- API: `http://127.0.0.1:8000/v1/health`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/`

El dashboard no requiere otro proceso ni build step: FastAPI sirve `web/`.

### 3. MCP server

STDIO, para un cliente local:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m sipsa.mcp.server
```

SSE en `http://127.0.0.1:8001/sse`:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m sipsa.mcp.server --transport sse
```

Configuración de Claude Desktop:

```json
{
  "mcpServers": {
    "sipsa": {
      "command": "python",
      "args": ["-m", "sipsa.mcp.server"],
      "cwd": "C:\\Users\\Categorymanager\\Desktop\\JORE\\Phyton\\Hackaton\\sipsa-data",
      "env": {
        "PYTHONPATH": "C:\\Users\\Categorymanager\\Desktop\\JORE\\Phyton\\Hackaton\\sipsa-data\\src"
      }
    }
  }
}
```

Configuración de Codex (`config.toml`):

```toml
[mcp_servers.sipsa]
command = "python"
args = ["-m", "sipsa.mcp.server"]
cwd = "C:\\Users\\Categorymanager\\Desktop\\JORE\\Phyton\\Hackaton\\sipsa-data"
env = { PYTHONPATH = "C:\\Users\\Categorymanager\\Desktop\\JORE\\Phyton\\Hackaton\\sipsa-data\\src" }
```

Tools: `listar_productos`, `mejores_precios`, `productos_a_evitar`, `tendencia_producto`, `pronostico_producto`, `alertas_precio`, `resumen_semanal` y `comparar_ciudades`.

### 4. Bot de Telegram

Configure `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=token-entregado-por-BotFather
TELEGRAM_CHAT_IDS=123456789,-1001234567890
```

Luego arranque el proceso aparte:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m sipsa.telegram_bot
```

Sin `TELEGRAM_BOT_TOKEN`, el comando registra un aviso y termina con código 0. Comandos del bot: `/start`, `/hoy [ciudad] [perfil]`, `/precio <producto>` y `/alertas [ciudad]`. El job diario de las 06:00 envía el resumen a los IDs configurados después de ingestar y generar snapshots.

## Snapshots y operación offline

Generación manual:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python scripts/make_snapshot.py
```

Se crean 18 JSON en `data/snapshot/`: resumen y oportunidades para tres ciudades y tres perfiles. Si DuckDB no abre, las rutas críticas usan esos archivos y responden con `X-Data-Mode: snapshot`.

## Endpoints y ejemplos

Todos los precios están en COP/kg y las fechas usan ISO `YYYY-MM-DD`.

| Método | Ruta | Función |
|---|---|---|
| GET | `/v1/health` | Estado, fuente activa y porcentaje seed |
| GET | `/v1/productos` | Catálogo, con filtro `categoria` |
| GET | `/v1/ciudades` | Ciudades disponibles |
| GET | `/v1/precios` | Serie de producto y ciudad |
| GET | `/v1/oportunidades` | Mejores compras por perfil |
| GET | `/v1/evitar` | Peores compras por perfil |
| GET | `/v1/tendencia/{producto_id}` | Variación e historia |
| GET | `/v1/forecast/{producto_id}` | Pronóstico de 1 a 4 semanas |
| GET | `/v1/alertas` | Movimientos sobre un umbral |
| GET | `/v1/resumen-semanal` | Resumen legible para UI/Telegram |
| GET | `/v1/comparar` | Comparación entre ciudades |
| POST | `/v1/admin/ingest` | Ingesta protegida por token |
| POST | `/v1/admin/snapshot` | Regeneración de snapshots |

```powershell
curl.exe "http://127.0.0.1:8000/v1/health"
curl.exe "http://127.0.0.1:8000/v1/productos?categoria=verduras"
curl.exe "http://127.0.0.1:8000/v1/ciudades"
curl.exe "http://127.0.0.1:8000/v1/precios?producto_id=papa_pastusa&ciudad=Bogot%C3%A1"
curl.exe "http://127.0.0.1:8000/v1/oportunidades?ciudad=Bogot%C3%A1&perfil=restaurante&top=5"
curl.exe "http://127.0.0.1:8000/v1/evitar?ciudad=Bogot%C3%A1&top=5"
curl.exe "http://127.0.0.1:8000/v1/tendencia/papa_pastusa?ciudad=Bogot%C3%A1&semanas=12"
curl.exe "http://127.0.0.1:8000/v1/forecast/papa_pastusa?ciudad=Bogot%C3%A1&horizonte=2"
curl.exe "http://127.0.0.1:8000/v1/alertas?ciudad=Bogot%C3%A1&umbral_pct=15&ventana=1w"
curl.exe "http://127.0.0.1:8000/v1/resumen-semanal?ciudad=Bogot%C3%A1&perfil=restaurante"
curl.exe "http://127.0.0.1:8000/v1/comparar?producto_id=papa_pastusa"
curl.exe -X POST -H "X-Admin-Token: change-me" "http://127.0.0.1:8000/v1/admin/ingest"
curl.exe -X POST -H "X-Admin-Token: change-me" "http://127.0.0.1:8000/v1/admin/snapshot"
```

Los errores siguen `{ "error": { "code": "...", "message": "..." } }`.

## Datos y fallback

- `excel_dane` descubre anexos XLS/XLSX semanales y registra URLs en `data/raw/sources.json`.
- `soap_dane` importa `zeep` solo si está instalado y usa el WSDL SIPSA.
- `socrata` pagina de 50.000 filas; queda deshabilitado si `SOCRATA_DATASET_ID` está vacío.
- `seed` produce 104 semanas deterministas para 40 productos y tres ciudades.
- Los nombres no mapeados se agregan a `data/raw/unmapped.csv` sin detener la ingesta.
- Cada parquet crudo queda en `data/raw/`; no se borra automáticamente.
- `/v1/health` expone `fuente_activa` y `pct_seed` para que el fallback nunca sea silencioso.

## Pruebas

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest -p no:cacheprovider -q
```

Se deshabilita el caché de pytest porque algunos entornos administrados no permiten crear `.pytest_cache`.
