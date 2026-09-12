# Baskio Dashboard and Brand Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar el dashboard responsive de Baskio para negocios grandes, integrar los recursos oficiales de marca y dejar preparado el avatar cuadrado que se aplicará al bot de Telegram.

**Architecture:** El dashboard es una aplicación estática HTML/CSS/JavaScript sin compilación, servida por un módulo FastAPI separado para no interferir con la API que desarrolla el otro equipo. `api-client.mjs` intercambia fixtures y API; `view-model.mjs` transforma exclusivamente para presentación; `app.mjs` controla DOM, navegación y estados. Los recursos del logo derivan de la imagen oficial entregada por el usuario.

**Tech Stack:** HTML5 semántico, CSS responsive, JavaScript ES modules, Node.js test runner, FastAPI, Pillow y pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-interfaces-telegram-dashboard-design.md`

## Global Constraints

- Trabajar únicamente en la rama `codex/web-dashboard` y su worktree.
- No modificar `src/sipsa/api/main.py`, modelos analíticos ni trabajo del backend.
- No calcular recomendaciones, señales, pronósticos ni conclusiones comerciales.
- Todos los datos simulados muestran `Modo demo · datos simulados`.
- Conservar el símbolo y la palabra `baskio` del archivo oficial; no rediseñarlos.
- Usar azul `#1B3361`, turquesa `#2EA6B6`, fondo `#F5F7FA`, superficie `#FFFFFF` y texto `#12213C`.
- Verificar `1440 × 900`, `1024 × 768` y `390 × 844`.
- No hacer tráfico real de prueba contra Telegram ni servicios externos.
- Cambiar la foto real del bot requiere autorización explícita inmediatamente antes de usar BotFather.
- Cada commit, push o publicación requiere autorización explícita separada.

---

### Task 1: Recursos oficiales de marca

**Files:**
- Source: `C:/Users/Categorymanager/Desktop/JORE/Phyton/Hackaton/WhatsApp Image 2026-09-12 at 2.14.31 PM.jpeg`
- Create: `web/assets/baskio-logo.png`
- Create: `web/assets/baskio-mark.png`
- Create: `web/assets/baskio-telegram-avatar.png`
- Create/Test: `tests/test_dashboard_assets.py`

**Interfaces:**
- Produces: logotipo horizontal RGBA con proporción mayor a `1.8:1`.
- Produces: símbolo cuadrado RGBA para navegación compacta.
- Produces: avatar PNG cuadrado de al menos `512 × 512`, con margen seguro mínimo de 12%.

- [ ] **Step 1: Escribir la prueba RED de formato y proporciones**

```python
from pathlib import Path

from PIL import Image


ASSETS = Path(__file__).resolve().parents[1] / "web" / "assets"


def test_recursos_baskio_tienen_formatos_para_dashboard_y_telegram():
    with Image.open(ASSETS / "baskio-logo.png") as logo:
        assert logo.format == "PNG"
        assert logo.width / logo.height > 1.8
        assert logo.mode == "RGBA"

    with Image.open(ASSETS / "baskio-mark.png") as mark:
        assert mark.width == mark.height
        assert mark.mode == "RGBA"

    with Image.open(ASSETS / "baskio-telegram-avatar.png") as avatar:
        assert avatar.width == avatar.height
        assert avatar.width >= 512
        assert avatar.format == "PNG"
```

- [ ] **Step 2: Ejecutar la prueba y comprobar RED**

Run: `python -m pytest tests/test_dashboard_assets.py -v -p no:cacheprovider`

Expected: FAIL porque `web/assets/` y los PNG todavía no existen.

- [ ] **Step 3: Preparar los tres recursos con ImageGen**

Usar la imagen como **edit target** y ejecutar dos ediciones de alta fidelidad:

```text
Use case: background-extraction
Asset type: dashboard horizontal logo
Primary request: remove only the white background and preserve the basket symbol and the exact lowercase word "baskio"
Input images: Image 1 is the edit target and official brand source
Composition/framing: preserve the original horizontal proportions and spacing
Text (verbatim): "baskio"
Constraints: exact logo geometry and colors; transparent background; no redraw; no extra text
Avoid: shadows, gradients, outlines, texture, new elements, altered typography
```

```text
Use case: precise-object-edit
Asset type: Telegram circular-profile avatar and compact dashboard mark
Primary request: isolate the basket symbol from the official logo and center it on a square canvas
Input images: Image 1 is the edit target and official brand source
Composition/framing: basket symbol centered; 16% white safe margin on every side; suitable for circular crop
Constraints: preserve exact basket geometry, navy and turquoise colors; no wordmark
Avoid: shadows, gradients, text, extra icons, redrawing
```

Guardar no destructivamente el horizontal como `baskio-logo.png`; conservar una versión RGBA transparente del símbolo como `baskio-mark.png`; componer la misma marca sobre fondo blanco y margen seguro como `baskio-telegram-avatar.png`.

- [ ] **Step 4: Inspeccionar visualmente los tres PNG**

Usar `view_image` y comprobar: texto exacto `baskio`, símbolo sin deformación, transparencia real en el horizontal y recorte circular seguro en el avatar.

- [ ] **Step 5: Ejecutar la prueba focalizada**

Run: `python -m pytest tests/test_dashboard_assets.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 6: Solicitar autorización antes de cualquier commit**

Proposed commit: `feat: add Baskio brand assets`

---

### Task 2: Servidor independiente y estructura accesible

**Files:**
- Create: `src/sipsa/dashboard.py`
- Create: `web/index.html`
- Create/Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `sipsa.dashboard.app: FastAPI`.
- Produces: `GET /` para el documento principal, `/assets/*` y `/fixtures/*` como archivos estáticos.
- Consumes: `web/assets/baskio-logo.png` y `web/assets/baskio-mark.png`.

- [ ] **Step 1: Escribir pruebas RED del servidor y la semántica**

```python
from fastapi.testclient import TestClient

from sipsa.dashboard import app


def test_dashboard_y_recursos_responden_sin_tocar_api_principal():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/assets/baskio-logo.png").status_code == 200
    assert client.get("/fixtures/resumen.json").status_code == 200


def test_dashboard_expone_estructura_accesible():
    html = TestClient(app).get("/").text
    assert '<header class="topbar">' in html
    assert '<main id="main-content"' in html
    assert 'aria-label="Periodos del gráfico"' in html
    assert '<table' in html
    assert 'alt="Baskio"' in html
```

- [ ] **Step 2: Ejecutar las pruebas y comprobar RED**

Run: `python -m pytest tests/test_dashboard.py -v -p no:cacheprovider`

Expected: ERROR al importar `sipsa.dashboard`.

- [ ] **Step 3: Implementar el servidor aislado**

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="Baskio Dashboard", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")
app.mount("/fixtures", StaticFiles(directory=WEB_ROOT / "fixtures"), name="fixtures")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")
```

- [ ] **Step 4: Crear `web/index.html` con estructura completa**

El documento debe contener, en este orden: enlace para saltar al contenido, `header.topbar` con logotipo y búsqueda, navegación, etiqueta persistente de modo demo, encabezado de producto, pestañas, selector de periodo, `svg` accesible, métricas, seguimiento y tabla comparativa. Cargar `/styles.css` y `/app.mjs` como módulo; usar `alt="Baskio"` en el logo y no repetir el wordmark dentro del contenido.

- [ ] **Step 5: Servir CSS y módulos desde el mismo servidor**

Añadir en `dashboard.py`:

```python
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
```

Referenciar `/static/styles.css` y `/static/app.mjs` desde HTML.

- [ ] **Step 6: Ejecutar las pruebas focalizadas**

Run: `python -m pytest tests/test_dashboard.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 7: Solicitar autorización antes de cualquier commit**

Proposed commit: `feat: add standalone Baskio dashboard shell`

---

### Task 3: Sistema visual responsive de Baskio

**Files:**
- Create: `web/styles.css`
- Modify/Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: custom properties `--baskio-navy`, `--baskio-teal`, `--surface`, `--canvas`, `--ink`.
- Produces: layouts en `1440 × 900`, `1024 × 768` y `390 × 844`.
- Produces: `.chart-frame` con proporciones `2.4:1`, `16:9` y `4:3` según breakpoint.

- [ ] **Step 1: Añadir prueba RED de CSS servido**

```python
def test_css_declara_tokens_y_proporciones_aprobadas():
    css = TestClient(app).get("/static/styles.css").text
    assert "--baskio-navy: #1b3361" in css.lower()
    assert "--baskio-teal: #2ea6b6" in css.lower()
    assert "aspect-ratio: 2.4 / 1" in css
    assert "aspect-ratio: 16 / 9" in css
    assert "aspect-ratio: 4 / 3" in css
    assert "prefers-reduced-motion" in css
```

- [ ] **Step 2: Ejecutar la prueba y comprobar RED**

Run: `python -m pytest tests/test_dashboard.py::test_css_declara_tokens_y_proporciones_aprobadas -v -p no:cacheprovider`

Expected: FAIL porque `styles.css` no contiene todavía el sistema visual.

- [ ] **Step 3: Implementar los tokens base**

```css
:root {
  --baskio-navy: #1b3361;
  --baskio-teal: #2ea6b6;
  --canvas: #f5f7fa;
  --surface: #ffffff;
  --ink: #12213c;
  --muted: #65708a;
  --line: #dce2eb;
  --positive: #17845b;
  --negative: #c74242;
  color-scheme: light;
  font-family: Aptos, "Segoe UI", sans-serif;
}
```

Crear una barra superior disciplinada, gráfico dominante, tarjetas de métricas con jerarquías distintas y tabla compacta. El turquesa se reserva para selección/foco y la serie principal; azul marino para identidad, títulos y navegación.

- [ ] **Step 4: Implementar los tres layouts**

Desktop: grid principal `minmax(0, 1fr) 304px`; gráfico `aspect-ratio: 2.4 / 1`. Tablet bajo `1100px`: seguimiento debajo y gráfico `16 / 9`. Móvil bajo `640px`: una columna, marca compacta, pestañas con scroll contenido, métricas `2 × 2`, gráfico `4 / 3` y objetivos táctiles mínimos de `44px`.

- [ ] **Step 5: Implementar accesibilidad visual**

Añadir `:focus-visible` con outline turquesa y offset, estados que combinan color + texto, `@media (prefers-reduced-motion: reduce)` y contraste AA para texto normal.

- [ ] **Step 6: Ejecutar las pruebas**

Run: `python -m pytest tests/test_dashboard.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 7: Solicitar autorización antes de cualquier commit**

Proposed commit: `feat: add responsive Baskio dashboard design system`

---

### Task 4: Cliente de datos intercambiable

**Files:**
- Create: `web/api-client.mjs`
- Create: `tests/js/api-client.test.mjs`
- Modify: `web/fixtures/resumen.json`
- Modify: `web/fixtures/tendencia.json`
- Modify: `web/fixtures/comparacion.json`

**Interfaces:**
- Produces: `createDataClient({ mode, baseUrl, fetchImpl })`.
- Produces: `client.get(resource: string, params?: URLSearchParams) -> Promise<object>`.
- Produces: documentos `{ mode, generated_at, data }` sin interpretar el contenido.

- [ ] **Step 1: Escribir pruebas RED de selección de fuente y error**

```javascript
import assert from "node:assert/strict";
import test from "node:test";
import { createDataClient } from "../../web/api-client.mjs";

test("modo demo solicita únicamente fixtures locales", async () => {
  const calls = [];
  const client = createDataClient({
    mode: "demo",
    fetchImpl: async (url) => {
      calls.push(url);
      return { ok: true, json: async () => ({ mode: "demo", data: [{}] }) };
    },
  });
  await client.get("resumen");
  assert.deepEqual(calls, ["/fixtures/resumen.json"]);
});

test("una respuesta fallida no se reemplaza con fixtures", async () => {
  const client = createDataClient({
    mode: "api",
    baseUrl: "http://127.0.0.1:8000",
    fetchImpl: async () => ({ ok: false, status: 503 }),
  });
  await assert.rejects(() => client.get("resumen"), /503/);
});
```

- [ ] **Step 2: Ejecutar pruebas y comprobar RED**

Run: `node --test tests/js/api-client.test.mjs`

Expected: FAIL porque el módulo no existe.

- [ ] **Step 3: Implementar el cliente mínimo**

```javascript
export function createDataClient({ mode = "demo", baseUrl = "", fetchImpl = fetch } = {}) {
  return {
    async get(resource, params = new URLSearchParams()) {
      const suffix = params.toString();
      const url = mode === "demo"
        ? `/fixtures/${resource}.json`
        : `${baseUrl}/v1/${resource}${suffix ? `?${suffix}` : ""}`;
      const response = await fetchImpl(url);
      if (!response.ok) throw new Error(`Datos no disponibles (${response.status})`);
      const payload = await response.json();
      if (!payload || !Array.isArray(payload.data)) throw new Error("Contrato de datos inválido");
      return payload;
    },
  };
}
```

- [ ] **Step 4: Ampliar fixtures solo con campos de presentación**

Añadir `metrics` al resumen, `points: [{ label, value }]` a tendencia y `cities: [{ city, value, unit }]` a comparación. Mantener cifras ficticias, `mode: "demo"` y textos que no emitan recomendaciones.

- [ ] **Step 5: Ejecutar contratos Python y JavaScript**

Run: `node --test tests/js/api-client.test.mjs`

Run: `python -m pytest tests/test_ui_contract.py -v -p no:cacheprovider`

Expected: ambas suites PASS.

- [ ] **Step 6: Solicitar autorización antes de cualquier commit**

Proposed commit: `feat: add dashboard fixture data client`

---

### Task 5: Presentación e interacciones del dashboard

**Files:**
- Create: `web/view-model.mjs`
- Create: `web/app.mjs`
- Create: `tests/js/view-model.test.mjs`
- Modify: `web/index.html`

**Interfaces:**
- Produces: `makeDashboardModel({ summary, trend, comparison, products, cities }, selection)`.
- Produces: `toSvgPoints(points, width, height) -> string` para coordenadas de presentación.
- Consumes: `createDataClient()` y nodos DOM con atributos `data-role`.

- [ ] **Step 1: Escribir pruebas RED de modelo de presentación**

```javascript
import assert from "node:assert/strict";
import test from "node:test";
import { makeDashboardModel, toSvgPoints } from "../../web/view-model.mjs";

test("selecciona el resumen de negocio y conserva la etiqueta demo", () => {
  const model = makeDashboardModel({
    summary: { mode: "demo", data: [{ city: "Bogotá", audience: "small_business", title: "Resumen", metrics: [] }] },
    trend: { data: [{ city: "Bogotá", product_id: "tomate-chonto", points: [{ label: "S1", value: 3000 }] }] },
    comparison: { data: [{ product_id: "tomate-chonto", cities: [] }] },
    products: { data: [{ id: "tomate-chonto", name: "Tomate chonto", unit: "kg" }] },
    cities: { data: [{ id: "bogota", name: "Bogotá" }] },
  }, { city: "Bogotá", productId: "tomate-chonto" });
  assert.equal(model.demo, true);
  assert.equal(model.product.name, "Tomate chonto");
  assert.equal(model.summary.title, "Resumen");
});

test("convierte puntos a coordenadas SVG dentro del lienzo", () => {
  const result = toSvgPoints([{ value: 10 }, { value: 20 }, { value: 15 }], 100, 50);
  assert.equal(result, "0,50 50,0 100,25");
});
```

- [ ] **Step 2: Ejecutar pruebas y comprobar RED**

Run: `node --test tests/js/view-model.test.mjs`

Expected: FAIL porque `view-model.mjs` no existe.

- [ ] **Step 3: Implementar modelo sin lógica analítica**

Seleccionar por coincidencia exacta de `city`, `audience` y `product_id`; no inferir tendencias. `toSvgPoints` escala exclusivamente las cifras recibidas al área visual y devuelve cadena vacía para lista vacía.

- [ ] **Step 4: Implementar `app.mjs`**

Al cargar: solicitar cinco fixtures en paralelo, mostrar estado `aria-live`, construir el modelo y renderizar encabezado, gráfico, métricas, seguimiento y tabla. Los controles de ciudad, producto, periodo y pestaña deben actualizar selección, `aria-selected`, URL mediante `history.replaceState` y presentación sin recargar.

- [ ] **Step 5: Implementar estados UI**

- Cargando: `Cargando datos…` en `aria-live`.
- Demo: badge persistente `Modo demo · datos simulados`.
- Vacío: `No hay información para esta selección.` y controles conservados.
- Error: `No fue posible cargar los datos.` con botón `Reintentar`.

- [ ] **Step 6: Ejecutar todas las pruebas de dashboard**

Run: `node --test tests/js/*.test.mjs`

Run: `python -m pytest tests/test_dashboard.py tests/test_dashboard_assets.py tests/test_ui_contract.py -v -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 7: Solicitar autorización antes de cualquier commit**

Proposed commit: `feat: add interactive Baskio dashboard`

---

### Task 6: Verificación visual, documentación y seguridad

**Files:**
- Modify: `README.md`
- Modify/Test: `tests/test_dashboard.py`

**Interfaces:**
- Documents: `python -m uvicorn sipsa.dashboard:app --reload --port 8080`.
- Verifies: dashboard usable in desktop, tablet and mobile reference sizes.

- [ ] **Step 1: Documentar ejecución local**

Añadir:

```powershell
$env:PYTHONPATH="src"
python -m uvicorn sipsa.dashboard:app --reload --port 8080
```

Abrir `http://127.0.0.1:8080`. Documentar que demo es el modo inicial y que el dashboard grande usa la marca Baskio.

- [ ] **Step 2: Ejecutar el servidor local sin red externa**

Run: `$env:PYTHONPATH='src'; python -m uvicorn sipsa.dashboard:app --host 127.0.0.1 --port 8080`

Expected: servidor local activo y `GET /` responde 200.

- [ ] **Step 3: Inspeccionar las proporciones aprobadas**

Capturar y revisar `1440 × 900`, `1024 × 768` y `390 × 844`. Comprobar logo no deformado, gráfico en proporción correcta, sin overflow global, tabla contenida, objetivos táctiles de 44px y navegación por teclado visible.

- [ ] **Step 4: Ejecutar suite final de interfaz**

Run: `node --test tests/js/*.test.mjs`

Run: `python -m pytest tests/test_dashboard.py tests/test_dashboard_assets.py tests/test_telegram_ui.py tests/test_ui_contract.py -v -p no:cacheprovider`

Expected: PASS sin tráfico externo.

- [ ] **Step 5: Auditar secretos y cambios fuera de alcance**

Run: `git diff --check`

Run: `rg -n "[0-9]{8,10}:[A-Za-z0-9_-]{30,}" . -g '!.env' -g '!.pytest_cache/**'`

Expected: ningún token, `.env` ausente del estado Git y ninguna modificación en `src/sipsa/api/`.

- [ ] **Step 6: Solicitar autorización antes de commit o push**

Proposed commit: `feat: deliver branded Baskio dashboard`

---

### Task 7: Aplicar avatar al bot real

**Files:**
- Consume: `web/assets/baskio-telegram-avatar.png`

**Interfaces:**
- Produces: foto de perfil circular visible en el bot Baskio.

- [ ] **Step 1: Mostrar al usuario el avatar final y explicar el cambio real**

Indicar que BotFather actualizará públicamente la foto del bot y que el cambio es reversible repitiendo `/setuserpic`.

- [ ] **Step 2: Solicitar autorización explícita inmediata**

No interpretar la aprobación del diseño ni de este plan como autorización para modificar Telegram.

- [ ] **Step 3: Aplicar mediante BotFather**

En `@BotFather`: ejecutar `/setuserpic`, seleccionar el bot Baskio y cargar `web/assets/baskio-telegram-avatar.png`. No pegar ni mostrar el token.

- [ ] **Step 4: Verificación visual dirigida por el usuario**

El usuario abre el perfil del bot y confirma que la canasta permanece completa dentro del círculo. No enviar mensajes automáticos de prueba.
