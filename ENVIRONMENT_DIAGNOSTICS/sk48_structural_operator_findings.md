# sk48 Structural Operator Findings

## Contexto

Se realizó un barrido controlado sobre la clase real `Sk48` usando `perform_action(ActionInput(...))` y observando cómo cambian:
- posición del nodo activo
- cantidad de segmentos por nodo
- cantidad de colores detectados por nodo
- resultado de `gvtmoopqgy()`

## Hallazgos clave

### 1. `ACTION1` y `ACTION2` actúan como desplazamiento vertical
En el nivel 0:
- `ACTION1` mueve el nodo activo hacia arriba
- `ACTION2` lo devuelve hacia abajo

Ejemplo observado:
- `(11, 36) -> (11, 30) -> (11, 24) -> ...`

No cambian:
- segmentos
- colores
- matching

### 2. `ACTION3` y `ACTION4` actúan como operadores estructurales locales
Con el nodo activo en `(11, 36)`:
- `ACTION3` cambia segmentos de `2 -> 1`
- `ACTION4` cambia segmentos de `1 -> 2`

Esto indica que:
- no son simplemente movimientos laterales
- modifican la estructura local del nodo activo

### 3. El efecto de `ACTION3` no depende de la posición vertical probada
Se probó `ACTION3` con el nodo activo en:
- `(11, 36)`
- `(11, 30)`
- `(11, 24)`
- `(11, 18)`
- `(11, 12)`

Resultado consistente:
- antes: `segments = 2`
- después: `segments = 1`
- `colors` sigue en `0`
- `gvtmoopqgy()` sigue en `False`

### 4. El efecto actual aún no altera el matching visible
Aunque `ACTION3` y `ACTION4` cambian la cantidad de segmentos del nodo A:
- `len_a` sigue en `0`
- `len_b` sigue en `3`
- `colors` no cambia
- `gvtmoopqgy()` sigue en `False`

## Conclusión técnica

Ya se aisló una primera mecánica real del puzzle:

- `ACTION1` / `ACTION2` = navegación vertical
- `ACTION3` / `ACTION4` = operadores estructurales locales sobre los segmentos del nodo activo

Sin embargo, todavía no se encontró la interacción que haga que el lado A empiece a producir colores detectables.

## Próxima hipótesis de trabajo

El siguiente progreso podría requerir:
1. combinar desplazamiento con operadores estructurales en otras regiones del mapa
2. inspeccionar cómo cambian `mwfajkguqx` internamente más allá del simple conteo
3. identificar si hay otra condición espacial u objetos intermedios necesarios para que `vjfbwggsd` empiece a poblarse en el nodo A

## Valor de este hallazgo

Este hallazgo permite dejar de tratar `ACTION3` y `ACTION4` como movimientos genéricos.
A partir de ahora deben considerarse operadores estructurales del solver específico de `sk48`.
