# SK48 Solver Status

## Estado actual

Se logró avanzar significativamente en la ingeniería inversa del entorno `sk48`, pero el solver completo sigue bloqueado por el cambio de nodo activo.

## Lo que ya funciona

### Acceso al entorno real
Se puede:
- importar `sk48.py` como módulo
- instanciar `Sk48()` directamente
- usar `set_level(0)` para cargar el nivel
- ejecutar acciones con `perform_action(ActionInput(...))`

### Estado interno accesible
Se puede inspeccionar correctamente:
- `xpmcmtbcv`
- `mwfajkguqx`
- `vjfbwggsd`
- `vzvypfsnt`
- `gvtmoopqgy()`

### Mecánicas ya entendidas
- `ACTION1` y `ACTION2` desplazan verticalmente el nodo activo
- `ACTION3` reduce localmente la estructura del nodo activo (`segments 2 -> 1` en nivel 0)
- `ACTION4` revierte esa reducción (`segments 1 -> 2`)
- `ACTION3/4` actúan como operadores estructurales locales, no como movimientos

## Lo que sigue bloqueado

### Cambio de nodo con `ACTION6`
El código muestra que `ACTION6` depende de:
- `current_level.get_sprite_at(x, y, "sys_click")`

Sin embargo:
- `get_sprites()` no devuelve sprites `sys_click`
- un barrido completo `0..63 x 0..63` no produjo ningún cambio de nodo activo
- intentar clicks aproximados sobre A y B tampoco funcionó

Resultado:
- `vzvypfsnt` nunca dejó de apuntar a A
- `ACTION3` siempre siguió afectando a A

## Implicancia estratégica

El solver quedó dividido en dos partes:

### Parte resuelta
- acceso a la clase real
- ejecución paso a paso
- análisis de estructura y matching
- comprensión parcial de la mecánica local

### Parte bloqueada
- descubrimiento del target real de `ACTION6`
- acceso práctico al cambio de foco hacia B
- cierre del matching entre ambos nodos

## Conclusión actual

El proyecto ya no está en una etapa de “probar heurísticas”.
Está en una etapa de:
- ingeniería inversa avanzada del entorno
- reconstrucción del modelo interno del puzzle

Pero el solver completo no puede cerrarse hasta resolver cómo se activa realmente `ACTION6`.

## Próximo paso recomendado

Dos líneas posibles:

### Línea A — continuar I+D
Investigar más profundamente:
- `get_sprite_at(...)`
- la representación interna de `sys_click`
- helpers adicionales del nivel o del motor base
- si los click targets viven en otra capa lógica distinta a `get_sprites()`

### Línea B — congelar estado actual
Mantener documentado lo aprendido y separar:
- una submission estable y simple para Kaggle
- una rama de I+D exclusiva para solver específico de `sk48`

## Recomendación práctica

Para el corto plazo:
- no seguir forzando un solver completo sobre `sk48` sin destrabar `ACTION6`
- conservar toda la documentación actual
- usar una baseline submission estable
- retomar el solver cuando haya una vía concreta para cambiar el nodo activo
