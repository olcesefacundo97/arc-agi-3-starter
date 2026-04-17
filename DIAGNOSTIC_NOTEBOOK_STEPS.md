# Diagnostic Notebook Steps

Objetivo: dejar de iterar agentes a ciegas y pasar a un análisis por entorno.

## Qué se descubrió hasta ahora

- `latest_frame` existe y viene como `FrameDataRaw`
- las acciones simples y complejas producen `changed=True`
- el reward permanece en `0.0`
- por lo tanto, el reward no sirve como señal temprana principal
- hace falta analizar `frame`, `available_actions` y transiciones por entorno

## Recomendación de trabajo

Analizar primero **un entorno a la vez** (por ejemplo `sk48`) antes de seguir iterando versiones del agente.

## Pasos sugeridos en Kaggle

### 1. Crear entorno y hacer RESET
- instanciar `env = arc.make(game_id, render_mode=None)`
- ejecutar `GameAction.RESET`
- inspeccionar `latest_frame`

### 2. Inspeccionar `latest_frame.frame`
- ver tipo
- ver estructura
- ver si permite comparaciones más útiles que `repr(latest_frame)`

### 3. Probar todas las acciones simples
Registrar por acción:
- reward
- cambio de estado
- cambio de frame
- available_actions posteriores
- terminated/truncated

### 4. Probar acciones complejas en rango 0..63
El agente oficial usa coordenadas `0..63`, por lo que este rango debe respetarse en el diagnóstico.

Registrar por acción/coordenada:
- reward
- cambio de estado
- cambio de frame
- available_actions posteriores

### 5. Buscar patrones
Ejemplos:
- acciones que siempre cambian el estado
- acciones que abren nuevas `available_actions`
- acciones que no cambian `frame`
- coordenadas que parecen más prometedoras

## Hipótesis actual

El siguiente salto no debería ser V8/V9 ciegos, sino un agente basado en:

- cambio de `frame`
- transiciones específicas
- disponibilidad dinámica de acciones
- análisis por entorno

## Próximo entregable recomendado

Armar una tabla por entorno con:

| action | x | y | reward | state_changed | frame_changed | available_actions_after | notes |
|--------|---|---|--------|---------------|---------------|-------------------------|-------|

Esto debería usarse como base para una futura versión del agente realmente guiada por evidencia.
