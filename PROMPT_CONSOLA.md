# Prompt para GitHub Copilot CLI

Desde la carpeta `CouncilHackathon`, abre GitHub Copilot CLI y pega el siguiente prompt. Completa los campos entre corchetes.

```text
@HACKATHON_COUNCIL.md

Actúa como facilitador del Hackathon Idea Council y evalúa la siguiente propuesta para “Agents, Everywhere: Bots, Channels, & More”.

No empieces a construir todavía. Ejecuta el protocolo completo definido en HACKATHON_COUNCIL.md con los seis lentes: Elon Musk, Demis Hassabis, Steve Jobs, Charlie Munger, Donella Meadows y Chris Voss.

Quiero ver explícitamente el debate de los seis arquetipos. No resumas ni omitas ninguna voz.

Presenta la deliberación con estas secciones, en este orden:

## RONDA 1 — POSICIONES INDEPENDIENTES

### Elon Musk — Primeros principios y ambición 10x
Evalúa si el problema es real, si la solución cambia el resultado de forma radical y cuál es el supuesto técnico más débil.
Cierra con: BUILD, PIVOT o KILL.

### Demis Hassabis — Capacidad de IA y factibilidad técnica
Evalúa si un agente es realmente necesario, la viabilidad del loop agente-herramientas-contexto, riesgos de fallos del modelo y cómo demostrarlo.
Cierra con: BUILD, PIVOT o KILL.

### Steve Jobs — Usuario, simplicidad y demo
Evalúa la experiencia del usuario, la claridad del antes/después, el momento “wow” y qué eliminar para lograr una demo memorable en dos minutos.
Cierra con: BUILD, PIVOT o KILL.

### Charlie Munger — Inversión y costo de oportunidad
Explica qué garantizaría el fracaso, cuál es el mayor riesgo, qué alternativa más simple podría vencer esta idea y cuál es el kill condition.
Cierra con: BUILD, PIVOT o KILL.

### Donella Meadows — Sistemas y apalancamiento
Explica un loop causal usando el formato A -> B -> C -> A, identifica el punto de mayor apalancamiento y una consecuencia no intencional.
Cierra con: BUILD, PIVOT o KILL.

### Chris Voss — Adopción e incentivos
Identifica usuario, beneficiario, aprobador y bloqueador. Expón la fricción de adopción y formula una pregunta calibrada para validar el dolor.
Cierra con: BUILD, PIVOT o KILL.

## RONDA 2 — DEBATE Y DESACUERDOS

Cada arquetipo debe responder brevemente:
- Con cuál arquetipo discrepa.
- Qué supuesto cuestiona.
- Qué cambio concreto exige antes de construir.

## RONDA 3 — VOTO FINAL

Muestra una tabla con el voto individual de cada arquetipo:

| Arquetipo | Voto | Condición indispensable |
|---|---|---|
| Elon Musk | BUILD / PIVOT / KILL | |
| Demis Hassabis | BUILD / PIVOT / KILL | |
| Steve Jobs | BUILD / PIVOT / KILL | |
| Charlie Munger | BUILD / PIVOT / KILL | |
| Donella Meadows | BUILD / PIVOT / KILL | |
| Chris Voss | BUILD / PIVOT / KILL | |

Después, sintetiza el veredicto del consejo siguiendo estrictamente este orden:
1. Veredicto: BUILD, PIVOT o KILL; puntaje /100 y nivel de confianza.
2. Decisión ejecutiva en máximo 75 palabras.
3. Tabla de gates eliminatorios con evidencia.
4. Scorecard ponderado /100.
5. Disenso principal y el dato que podría cambiar el veredicto.
6. Scope convergido: usuario, canal nativo, trabajo único, loop del agente, resultado visible en demo y no-objetivos.
7. Tres tareas concretas para los próximos 45 minutos, cada una con responsable.
8. Si el veredicto es BUILD, termina con el bloque BUILD BRIEF exacto indicado en el harness.

Distingue explícitamente entre hechos, supuestos e hipótesis. No inventes entrevistas, capacidades técnicas, integraciones, criterios oficiales de jurado ni datos de usuarios.

IDEA A EVALUAR

Nombre tentativo:
[Escribe el nombre]

Propuesta en una frase:
[Qué agente hace qué, para quién y en qué canal donde ya trabaja o vive]

Usuario y momento de uso:
[Usuario específico, herramienta/canal existente y momento de fricción]

Dolor que resuelve:
[Dolor, frecuencia, impacto y evidencia disponible]

Ventaja de contexto:
[Qué información existe en ese canal y por qué el agente supera un chat separado]

Loop del agente:
[Trigger -> contexto que lee -> razonamiento/herramientas -> acción -> aprobación humana -> feedback]

Prototipo funcional que podemos tener antes de las 15:30:
[Flujo end-to-end mínimo, integraciones, APIs, mocks y dependencias]

Demo de dos minutos:
[Setup -> trigger -> acción visible del agente -> resultado comprobable]

Ventaja del equipo:
[Skills, acceso a datos no sensibles, relaciones, código existente o experiencia]

Riesgos y supuestos:
[Privacidad, permisos, integración, adopción, seguridad y supuestos críticos]

Métrica de éxito:
[Una señal observable que demuestre que el prototipo funcionó]
```

## Modo torneo

Para comparar varias opciones, reemplaza `IDEA A EVALUAR` por el brief de cada candidata y añade esta instrucción inmediatamente después de la primera línea:

```text
Activa modo torneo: rankea todas las ideas y recomienda una única ganadora para construir. Si ninguna califica como BUILD, selecciona solamente el PIVOT más viable e indica el nuevo scope exacto.
```
