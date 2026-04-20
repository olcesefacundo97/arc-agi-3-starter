# Submission Baseline Plan

## Objetivo

Tener una submission estable para Kaggle que:
- corra en modo offline
- no falle por instalación o acceso de red
- use una política simple y reproducible
- sirva como baseline clara mientras el solver específico de `sk48` queda en I+D separada

## Principios de la baseline

1. **Estabilidad antes que ambición**
   - evitar dependencias de red
   - evitar paths dudosos
   - evitar exploración experimental no validada

2. **Cumplir el contrato del entorno**
   - usar `arc_agi.Arcade` en `OperationMode.OFFLINE`
   - usar `perform_action`/wrapper oficial del entorno
   - respetar `GameAction`, `GameState` y `ActionInput`

3. **Mantener el código simple**
   - una sola política base
   - parámetros claros
   - export limpio para submission

## Política baseline recomendada

Usar una política simple con estas ideas:
- `RESET` cuando corresponda
- alternar entre unas pocas acciones válidas y reproducibles
- evitar depender de señales internas no accesibles desde el wrapper público
- limitar pasos por entorno

## Alcance de la baseline

Esta baseline no busca resolver `sk48` ni otros puzzles complejos por ingeniería inversa.
Busca:
- entregar una primera submission estable
- dejar el pipeline sano
- evitar errores de ejecución

## Separación recomendada

### Rama submission
- notebook limpio de Kaggle
- baseline simple
- export final de submission

### Rama research
- solver específico de `sk48`
- reverse engineering
- pruebas sobre clase real `Sk48`
- documentación del entorno

## Siguiente entregable sugerido

Crear un notebook final tipo:
- instalación offline desde wheels locales
- imports
- creación de `Arcade` offline
- detección de `GAME_IDS`
- `BaselineAgent`
- `run_single_game`
- `run_batch`
- resumen
- bloque final de export/submission

## Criterio de éxito de esta baseline

Se considera exitosa si:
- corre sin errores en Kaggle
- no depende de internet
- genera una submission válida
- sirve como base estable para futuras iteraciones
