# SK48 Solver Plan

## Estado actual

La exploración heurística externa no produjo progreso real en `sk48`.

Hallazgos ya confirmados:
- maximizar `reward` no sirve como señal temprana
- maximizar `changed_pixels` tampoco alcanza
- secuencias cortas con `ACTION1` y `ACTION4` cambian el frame pero no completan niveles
- `ACTION6` no debe usarse a ciegas
- `ACTION7` funciona como undo

## Qué reveló el código del entorno

### Objetivo real
El progreso real depende de que `gvtmoopqgy()` devuelva `True`.
Solo entonces se activa `lgdrixfno`, se reproduce una animación y luego se ejecuta `next_level()`.

### Semántica de acciones
- `ACTION1` -> `(0, -1)`
- `ACTION2` -> `(0, 1)`
- `ACTION3` -> `(-1, 0)`
- `ACTION4` -> `(1, 0)`
- `ACTION6` -> cambiar nodo activo válido
- `ACTION7` -> restaurar snapshot previo

### Estructura interna relevante
- `self.xpmcmtbcv`: mapea pares de nodos equivalentes
- `self.mwfajkguqx`: lista de segmentos asociados a cada nodo
- `self.vjfbwggsd`: colores detectados por nodo
- `gvtmoopqgy()`: compara colores entre nodos emparejados

## Hallazgo nuevo importante

La clase real `Sk48` es accesible directamente por import del archivo `sk48.py`, pero la propiedad `action` no tiene setter.

Eso implica que el solver no puede usar el patrón ingenuo:
- `game.action = ...`
- `game.step()`

El siguiente paso debe ser investigar y utilizar correctamente alguno de estos caminos:
- `perform_action(...)`
- `handle_reset(...)`
- `full_reset(...)`
- u otro método runtime que cargue la acción antes de `step()`

## Hipótesis fuerte
`sk48` no es un entorno genérico de exploración, sino un puzzle de matching estructural entre pares de nodos y secuencias de segmentos.

Por lo tanto, el siguiente agente útil debe ser **específico para sk48**.

## Estrategia de solver propuesta

### Fase 1 — Reconstrucción del estado útil
Crear funciones auxiliares que, a partir del nivel y/o del frame, reconstruyan:
- nodos clickeables
- pares de nodos
- segmentos actuales por nodo
- targets de color
- obstáculos y límites

### Fase 2 — Modelo de transición simplificado
Implementar una simulación reducida que permita probar secuencias de:
- movimientos (`ACTION1..4`)
- cambios de nodo (`ACTION6`)
- undo (`ACTION7`)

Objetivo: aproximar cuándo una secuencia mejora el matching entre pares.

### Fase 3 — Función objetivo correcta
En vez de usar solo `reward` o `changed_pixels`, priorizar:
1. coincidencias de colores entre nodos emparejados
2. cantidad de segmentos alineados válidos
3. posibilidad de activar `gvtmoopqgy()`

### Fase 4 — Búsqueda
Probar búsqueda limitada por profundidad, por ejemplo:
- depth 2 o 3 para movimientos
- intercalando `ACTION6` solo en targets válidos
- usando `ACTION7` para rollback cuando una rama no mejora matching

## Primer código a escribir

### Módulo sugerido
`agents/sk48_solver_experimental.py`

### Funciones iniciales
- `extract_clickable_nodes_from_level(level)`
- `extract_pairs_from_level_or_runtime(...)`
- `score_matching_progress(...)`
- `enumerate_valid_action6_targets(...)`
- `simulate_short_sequence(...)`
- `search_best_local_sequence(...)`

## Experimentos mínimos recomendados

1. Verificar si desde el objeto expuesto por `arc.make()` hay forma práctica de acceder a:
   - `_get_valid_actions()`
   - `_get_hidden_state()`
   - o atributos internos del juego

2. Si no se puede, crear una versión local/independiente del solver que use directamente la lógica del archivo `sk48.py` como referencia.

3. Probar un agente solo para `sk48`, no general.

4. Investigar el flujo correcto para inyectar acciones en la instancia real `Sk48` sin usar `game.action = ...`.

## Decisión estratégica

No seguir iterando V8/V9/V10 generales.

Sí avanzar con:
- análisis específico de `sk48`
- solver guiado por lógica del entorno
- instrumentación más profunda o simulación externa

## Criterio de éxito

Se considerará progreso real cuando ocurra cualquiera de estas señales:
- `levels_completed` > 0
- activación de la fase de éxito (`lgdrixfno >= 0`)
- evidencia estructural de matching correcto entre pares
