# sk48 ACTION6 Blocker

## Hallazgo

Se inspeccionó la lógica real de `ACTION6` en `sk48.py` y se confirmó que el cambio de nodo activo depende de esto:

- tomar `x` e `y` desde `action.data`
- buscar `current_level.get_sprite_at(x, y, "sys_click")`
- si encuentra un sprite válido, llamar `crbbymputr(...)`

## Problema observado

En la clase real `Sk48()`:
- al listar sprites de `current_level.get_sprites()`, no aparecen sprites con nombre `sys_click`
- la lista devuelta fue vacía para esa búsqueda
- los intentos de `ACTION6` con coordenadas aproximadas sobre los nodos no cambiaron `vzvypfsnt`

## Evidencia funcional

Se observó que:
- `initial active` = `(11, 36)`
- `after ACTION6 on A` = `(11, 36)`
- `after ACTION6 on B` = `(11, 36)`

Y luego `ACTION3` siguió afectando al nodo A, no al nodo B.

## Conclusión

El solver ya no está bloqueado por:
- acceso a la clase real
- ejecución de acciones
- comprensión de `ACTION3` / `ACTION4`

Ahora está bloqueado específicamente por no conocer los targets reales que hagan que `ACTION6` encuentre un sprite `sys_click` válido.

## Implicancia para el solver

Mientras no se resuelva este punto:
- no se puede cambiar de nodo activo de forma confiable
- no se puede operar estructuralmente sobre B
- no se puede construir un solver completo de matching entre pares

## Próximos pasos sugeridos

1. inspeccionar si `sys_click` se genera en otra colección distinta a `get_sprites()`
2. inspeccionar `current_level.get_sprite_at(...)` con barrido espacial para detectar qué nombres responde
3. revisar si el click válido depende de bounding boxes, visibilidad o capas lógicas no visibles en el listado simple
4. considerar leer más profundamente `on_set_level()` y helpers asociados para detectar cómo se crean o registran los targets clickeables
