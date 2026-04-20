# sk48 Solver Runtime Findings

## Contexto

Se pasó de usar el wrapper público (`arc.make(...)`) a importar e instanciar directamente la clase real `Sk48` desde `sk48.py`.

## Hallazgos técnicos

### 1. La clase real sí expone estado interno útil
Instanciando `Sk48()` aparecen atributos y métodos relevantes como:
- `gvtmoopqgy`
- `xpmcmtbcv`
- `mwfajkguqx`
- `vjfbwggsd`
- `uqclctlhyh`
- `perform_action`
- `set_level`

Esto confirma que la vía correcta para un solver específico no es el wrapper público, sino la clase real del entorno.

### 2. `action` no tiene setter
Intentar ejecutar acciones con:
- `game.action = ...`
- `game.step()`

falla porque `action` es una propiedad sin setter.

### 3. `perform_action(...)` requiere `ActionInput`
Intentar llamar `perform_action(GameAction.ACTION1)` falla.
La forma correcta es usar un `ActionInput` con `id`, `data` y `reasoning`.

### 4. Las acciones ya se pueden ejecutar correctamente
Con `ActionInput`, una acción como `ACTION1` modifica el estado:
- cambia la posición del nodo activo
- reduce `qiercdohl`

Pero no mejora aún el score estructural.

## Hallazgos de solver sobre nivel 0

### Estado inicial observado
- 1 solo par de nodos
- nodo A en `(11, 36)`
- nodo B en `(20, 56)`
- `len_a = 0`
- `len_b = 3`
- `matches = 0`
- score inicial = `-15`
- `gvtmoopqgy() = False`

### Secuencias de movimientos sin `ACTION6`
Se probaron todas las secuencias de longitud 3 con:
- `ACTION1`
- `ACTION3`
- `ACTION4`

Resultado:
- todas válidas
- ninguna mejoró el score
- todas quedaron en `-15`

### Secuencias con `ACTION6` + 3 movimientos
Se enumeraron 2 targets válidos de `ACTION6`:
- click en `{'x': 13, 'y': 38}` para el nodo `(11, 36)`
- click en `{'x': 22, 'y': 58}` para el nodo `(20, 56)`

Se probaron 54 combinaciones válidas de:
- `ACTION6`
- seguido por 3 movimientos entre `ACTION1`, `ACTION3`, `ACTION4`

Resultado:
- 54 ejecuciones válidas
- 0 errores
- ninguna mejoró el score
- todas mantuvieron score = `-15`
- `gvtmoopqgy()` permaneció en `False`

## Conclusión técnica actual

Ya se validó que:
- el driver correcto para acciones en la clase real funciona
- el estado interno es accesible
- pero las secuencias cortas probadas no alteran el matching estructural medido

## Siguiente hipótesis de trabajo

El siguiente progreso no vendrá de:
- secuencias muy cortas
- ni solo de `ACTION6` + movimientos simples

La próxima línea útil podría requerir:
1. secuencias más largas
2. inspección directa de cómo cambian `mwfajkguqx` y `vjfbwggsd` tras cada acción
3. identificación explícita del nodo activo (`vzvypfsnt`) en cada paso
4. medir no solo score agregado, sino diferencias estructurales intermedias entre segmentos y colores detectados
