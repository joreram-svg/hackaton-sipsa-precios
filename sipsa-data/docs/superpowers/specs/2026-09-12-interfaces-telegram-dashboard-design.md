# Diseño de interfaces SIPSA: Telegram y dashboard empresarial

## 1. Objetivo

Construir una capa de interfaz demostrable y desacoplada del backend para tres tipos de uso:

1. Consumidor final mediante Telegram.
2. Negocio pequeño mediante el mismo bot de Telegram, con un recorrido y menú diferenciados.
3. Negocio grande mediante un dashboard web inspirado en la jerarquía visual de TradingView.

La rama de interfaz controla navegación, presentación, accesibilidad, comportamiento responsive, persistencia de preferencias y comunicación con el contrato API. No calcula precios, señales, recomendaciones, tendencias ni pronósticos.

## 2. Decisiones aprobadas

- Rama y worktree: `codex/web-dashboard` en `.worktrees/web-dashboard`.
- Un solo bot de Telegram para consumidor y negocio pequeño.
- El perfil es autodeclarado; no existe control de acceso ni validación comercial en esta versión.
- El perfil elegido se guarda por chat y puede cambiarse en cualquier momento.
- El dashboard está orientado a negocios grandes.
- La interfaz debe funcionar antes de que el backend esté terminado mediante fixtures JSON compatibles con el contrato.
- Los datos simulados deben identificarse de forma visible como `Modo demo`.
- El dashboard adopta de TradingView su jerarquía, densidad y patrones útiles, sin copiar marca, código ni componentes propietarios.

## 3. Límites de responsabilidad

### Dentro de alcance

- Flujos y menús de Telegram.
- Registro local del perfil, ciudad y último menú utilizado.
- Dashboard HTML, CSS y JavaScript vanilla, sin paso de compilación.
- Cliente de datos intercambiable entre API real y fixtures.
- Estados de carga, vacío, error, desconexión y modo demo.
- Responsive para escritorio, tablet y móvil.
- Accesibilidad de navegación, controles, tablas y gráficos.
- Pruebas de interacción sin tráfico hacia Telegram ni servicios reales.

### Fuera de alcance

- Cálculo o interpretación de datos SIPSA.
- Generación de recomendaciones, alertas, señales o pronósticos.
- Ingesta, persistencia analítica y scheduler de datos.
- Autenticación, autorización o planes comerciales.
- Envíos reales de Telegram durante pruebas.
- Publicación, despliegue, commit o push sin autorización separada.

## 4. Arquitectura

La interfaz se divide en cuatro unidades independientes:

1. `Telegram UI`: recibe comandos y pulsaciones, mantiene el recorrido conversacional y presenta respuestas.
2. `Dashboard web`: presenta búsqueda, navegación, gráficos, métricas y tablas.
3. `Data provider`: adapta las solicitudes de ambas superficies al contrato del backend.
4. `Fixtures`: implementan el mismo contrato para permitir una demostración completa sin backend.

El proveedor de datos no contiene reglas de negocio. Su responsabilidad es solicitar, validar superficialmente y entregar las respuestas recibidas. La fuente activa se selecciona al iniciar: API real por defecto; fixtures cuando se activa explícitamente el modo demo o cuando la configuración de desarrollo lo determina. No se debe ocultar una caída del backend presentando datos simulados como reales.

## 5. Telegram: un bot, dos perfiles

Nombre de interfaz: `SIPSA Cerca`.

### 5.1 Onboarding compartido

1. `/start` presenta la bienvenida.
2. El usuario selecciona su ciudad.
3. El usuario elige `Consumidor` o `Negocio pequeño` mediante botones inline.
4. El bot guarda `chat_id`, perfil, ciudad y último menú en almacenamiento local SQLite.
5. El bot presenta el menú correspondiente.

No se solicitan credenciales ni datos empresariales. `Cambiar perfil` y `Cambiar ciudad` permanecen accesibles desde los dos menús.

### 5.2 Menú de consumidor

- `Precios de hoy`
- `Buscar producto`
- `Comparar ciudades`
- `Ver cambios recientes`
- `Cambiar ciudad`
- `Cambiar perfil`

El lenguaje es cotidiano y las respuestas se mantienen cortas. Cada recorrido debe llegar a la consulta objetivo con pocos toques y permitir volver al menú principal.

### 5.3 Menú de negocio pequeño

- `Resumen del negocio`
- `Explorar productos`
- `Mi seguimiento`
- `Comparar ciudades`
- `Preferencias`
- `Historial reciente`
- `Cambiar ciudad`
- `Cambiar perfil`

Este menú utiliza un tono operativo y conserva preferencias para facilitar consultas repetidas. La interfaz organiza las solicitudes y respuestas; el contenido analítico lo entrega el backend o el fixture.

### 5.4 Estados conversacionales

- Cargando: mensaje breve o indicador de escritura.
- Sin datos: explica que no hay información disponible y ofrece volver o cambiar ciudad/producto.
- Error de backend: mensaje claro con botón `Reintentar` y acceso al menú.
- Modo demo: el mensaje incluye una indicación visible de que los datos son simulados.
- Entrada no reconocida: muestra acciones válidas sin perder el perfil seleccionado.

## 6. Dashboard para negocio grande

Nombre de interfaz: `SIPSA Monitor`.

### 6.1 Dirección visual

Se adoptan los siguientes patrones de TradingView:

- Fondo neutro, alto contraste y uso contenido del color.
- Buscador global visible.
- Identidad fuerte del producto.
- Precio actual y variación como jerarquía principal.
- Pestañas para separar tipos de análisis.
- Gráfico dominante con selector de periodo.
- Indicadores clave en una franja compacta.
- Lista de seguimiento y comparación tabular.
- Espaciado generoso alrededor de la información crítica.

No se copian logotipo, iconografía de marca, código, textos ni componentes propietarios.

### 6.2 Estructura de la vista

1. Barra superior: marca, búsqueda, `Mercados`, `Seguimiento`, `Reportes` y `Ayuda`.
2. Encabezado de producto: categoría, producto, ciudad, unidad, precio, variación, fecha y fuente.
3. Pestañas: `Resumen`, `Evolución`, `Comparar ciudades` y `Estacionalidad`.
4. Gráfico: periodos `1S`, `1M`, `3M`, `6M`, `1A` y `Todo`.
5. Seguimiento: productos guardados y variaciones recibidas.
6. Datos clave: semana anterior, promedio de cuatro semanas, rango entre ciudades y variación de cuatro semanas.
7. Comparación por ciudad: tabla ordenable y legible.

Los controles actualizan la presentación sin recargar toda la página. Las búsquedas y filtros se reflejan en la URL cuando sea posible para permitir vistas compartibles.

### 6.3 Responsive y proporciones

- Escritorio 16:9, referencia `1440 × 900`: gráfico con proporción aproximada `2.4:1`; seguimiento a la derecha.
- Tablet 4:3, referencia `1024 × 768`: gráfico `16:9`; seguimiento reducido o debajo según el ancho efectivo.
- Móvil 9:16, referencia `390 × 844`: gráfico `4:3`; una sola columna; seguimiento como sección separada.
- Las métricas cambian de cuatro columnas a una cuadrícula `2 × 2`.
- Las pestañas permiten desplazamiento horizontal sin cortar sus etiquetas.
- La tabla cambia a una presentación condensada por ciudad o a desplazamiento horizontal contenido.
- Ningún texto, punto del gráfico o control se escala como si fuera parte de una imagen.
- Los objetivos táctiles mantienen al menos 44 píxeles efectivos en pantallas táctiles.

## 7. Contrato de datos y modo demo

El dashboard y Telegram consumen un proveedor con operaciones alineadas al contrato existente, entre ellas:

- listar productos y ciudades;
- obtener resumen por ciudad y perfil;
- obtener tendencia de producto;
- comparar ciudades;
- obtener los contenidos disponibles para seguimiento.

Los fixtures usan exactamente las mismas formas JSON que la API. Toda respuesta incluye metadatos suficientes para que la interfaz muestre fuente, fecha y modo de datos.

Reglas del modo demo:

- Se activa explícitamente mediante configuración o parámetro de desarrollo.
- Muestra una etiqueta persistente `Modo demo · datos simulados`.
- Nunca realiza tráfico hacia sistemas reales.
- Permite recorrer todos los estados y controles relevantes.

## 8. Estructura prevista de archivos

```text
sipsa-data/
  web/
    index.html
    styles.css
    app.js
    api-client.js
    fixtures/
      productos.json
      ciudades.json
      resumen.json
      tendencia.json
      comparacion.json
  src/sipsa/
    telegram_bot.py
    telegram_ui/
      __init__.py
      menus.py
      state.py
      data_provider.py
  tests/
    test_dashboard.py
    test_telegram_ui.py
    test_ui_contract.py
```

El archivo SQLite de preferencias se crea en `data/ui_state.sqlite` y queda ignorado por Git.

## 9. Accesibilidad

- HTML semántico y orden natural de tabulación.
- Etiquetas visibles para buscadores, selectores y filtros.
- Estado de carga con `aria-live="polite"`.
- Errores importantes con `role="alert"`.
- Los gráficos incluyen título y descripción accesible, además de una alternativa textual o tabular.
- El color nunca es el único indicador de subida, bajada o estado.
- Los menús de Telegram mantienen textos completos en sus botones y una alternativa mediante comandos.

## 10. Manejo de errores

- Respuestas HTTP inválidas se convierten en un estado visual común.
- Un reintento no borra filtros, perfil ni ciudad.
- Los errores de un panel no bloquean el resto del dashboard.
- Si el backend no está configurado, el entorno de desarrollo puede iniciar en modo demo explícito.
- Si Telegram no tiene token, el proceso termina de forma controlada y deja un mensaje accionable; las pruebas no necesitan token.

## 11. Estrategia de pruebas

### Automatizadas

- El dashboard y sus archivos estáticos responden correctamente desde FastAPI.
- Los fixtures cumplen el contrato esperado por la UI.
- Los menús de consumidor y negocio pequeño son diferentes y navegables.
- El perfil y la ciudad sobreviven al reinicio del almacenamiento local.
- `Cambiar perfil` reemplaza el menú sin mezclar estado del perfil anterior.
- Carga, vacío, error y modo demo tienen representación verificable.
- Las pruebas de Telegram usan objetos simulados y no envían mensajes reales.

### Visuales

- Verificación en `1440 × 900`, `1024 × 768` y `390 × 844`.
- Sin desbordamientos horizontales globales.
- Gráficos sin deformación ni etiquetas recortadas.
- Pestañas, métricas, seguimiento y tabla cambian de disposición según el ancho.

## 12. Criterios de aceptación

1. El dashboard se puede recorrer completamente con fixtures sin backend.
2. Cambiar a la API real requiere únicamente configuración, no cambios en componentes.
3. El dashboard conserva jerarquía y legibilidad en las tres proporciones aprobadas.
4. El bot permite elegir, persistir y cambiar entre consumidor y negocio pequeño.
5. Cada perfil de Telegram muestra un menú y lenguaje claramente diferentes.
6. Todos los errores ofrecen una salida o un reintento sin perder contexto.
7. Ninguna prueba genera tráfico real hacia Telegram, DANE u otros sistemas.
8. La revisión final no encuentra lógica analítica duplicada en la rama de interfaz.
