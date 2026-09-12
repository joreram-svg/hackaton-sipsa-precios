# Baskio Dashboard Harness

Genera siempre el dashboard `baskio_dashboard.html` a partir de los datos reales
en Supabase, con un ciclo de mejora continua: cada corrida valida el resultado
antes de publicarlo, y si algo falla, deja el dashboard anterior intacto y
registra por qué en `CHANGELOG.md` en vez de romper la página en producción.

## Pipeline (`build.py`)

```
fetch_data.py     -> conecta a Supabase, trae precios y abastecimiento del
                      último año, agregado por producto y ciudad.
compute.py        -> calcula variación 1sem/4sem/1año, volatilidad, tendencia,
                      pronóstico 7d/30d con intervalo de confianza y señal
                      SUBIR/BAJAR/ESTABLE, y los insights de mercado
                      (gainers, losers, desempeño por categoría, amplitud).
render.py         -> inyecta el dataset calculado en template.html
                      (la plantilla estática: layout, estilos, i18n ES/EN).
validate.py       -> puerta de calidad: estructura del HTML, ids requeridos,
                      cobertura mínima de datos, señales válidas, sin
                      caracteres corruptos (mojibake).
changelog.py      -> compara contra la última corrida promovida y escribe
                      un resumen de qué cambió (fecha de datos, gainers/
                      losers, señales que voltearon, amplitud de mercado).
```

Si la validación falla, el build se **rechaza**: no se sobrescribe
`output/baskio_dashboard.html`. El intento fallido queda en
`output/history/rejected_<timestamp>.*` para inspección, y el motivo en
`CHANGELOG.md` y `harness.log`.

Si la validación pasa, se promueve: la versión anterior se archiva en
`output/history/`, se escribe el nuevo `output/baskio_dashboard.html`,
se guarda el dataset en `output/latest_dataset.json` (para diffs futuros),
y se agrega una entrada al changelog con lo que cambió.

## Instalación

```bash
cd baskio-harness
python -m pip install -r requirements.txt
cp .env.example .env   # y pon tu password real ahí, o exporta la variable
```

En PowerShell, para exportar la variable sin usar `.env`:

```powershell
$env:BASKIO_DSN = "postgresql://postgres.orvnduqyuhgfaolccxcw:TU-PASSWORD@aws-0-us-east-2.pooler.supabase.com:5432/postgres"
```

## Uso

**Una sola corrida:**

```bash
python build.py
```

**Corrida de prueba, sin promover nada** (solo valida y muestra el diff):

```bash
python build.py --dry-run
```

**Loop continuo** (para dejarlo "siempre" generando, ej. cada hora):

```bash
python harness.py --interval-minutes 60
```

`harness.py` corre en primer plano, reintenta indefinidamente, y baja el
intervalo a la mitad (mínimo 5 min) después de una corrida rechazada para
recuperarse más rápido de un problema transitorio (ej. Supabase caído un
momento) sin martillar la base de datos.

## Dejarlo corriendo siempre en Windows (Task Scheduler)

Para que se regenere solo sin tener una terminal abierta, crea una tarea
programada que llame a `python harness.py --once` cada hora (más robusto que
dejar `harness.py` en loop dentro de una sesión que se puede cerrar):

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "harness.py --once" -WorkingDirectory "G:\My Drive\Documentos\02-Tecnico\02-Labs_GenAI\37-Hackathon\baskio-harness"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "BaskioDashboardHarness" -Action $action -Trigger $trigger -Description "Regenera el dashboard Baskio con datos de Supabase"
```

Recuerda configurar `BASKIO_DSN` como variable de entorno de sistema/usuario
(no solo de tu sesión de PowerShell) para que la tarea programada la vea:

```powershell
[Environment]::SetEnvironmentVariable("BASKIO_DSN", "postgresql://...", "User")
```

## Dónde queda el resultado

```
output/baskio_dashboard.html   <- el dashboard actual, listo para abrir o publicar
output/latest_dataset.json     <- snapshot del dataset de la última corrida promovida
output/history/                <- versiones anteriores y builds rechazados
CHANGELOG.md                   <- historial de qué cambió en cada corrida
harness.log                    <- log técnico de cada corrida
```

## Extender la puerta de calidad

`validate.py` es el lugar para agregar más reglas de "mejora continua": por
ejemplo, alertar si un producto pierde cobertura de ciudades, si la
volatilidad de algún producto se dispara de forma sospechosa, o si el número
de productos con historial completo cae respecto a la corrida anterior.
Cualquier chequeo que agregues ahí automáticamente bloquea la promoción de un
build que lo viole.
