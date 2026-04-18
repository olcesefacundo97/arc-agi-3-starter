# SK48 Black-Box Postmortem

## Resumen ejecutivo

Se intentó abordar `sk48` mediante exploración black-box desde el wrapper público del entorno y mediante varias generaciones de agentes heurísticos. Ninguno produjo progreso real.

Resultado consolidado:
- `reward = 0.0`
- `levels_completed = 0`
- `available_actions` sin cambios relevantes
- sin activación de la fase de éxito del entorno

Conclusión:
La estrategia black-box quedó agotada para `sk48`.

## Qué se probó

### 1. Agentes generales V4/V5/V6/V7
Se probaron agentes con:
- reward shaping
- cambio de estado
- novedad
- top-k action ranking
- planner-lite
- transición entre estados

Resultado:
- ninguna versión obtuvo reward positivo
- ninguna completó niveles
- solo aumentaban la cantidad de pasos consumidos

### 2. Diagnóstico por frame
Se dejó de usar `repr(latest_frame)` y se pasó a medir:
- `changed_pixels`
- `available_actions`
- `levels_completed`

Hallazgo:
- varias acciones simples cambian el frame real
- `ACTION6` no producía cambios útiles en fase temprana
- aun así, no había progreso real

### 3. Secuencias cortas
Se probaron secuencias de 2 y 3 pasos usando principalmente:
- `ACTION1`
- `ACTION3`
- `ACTION4`

Hallazgo:
- algunas secuencias maximizaban `changed_pixels`
- pero no generaban reward ni avance de nivel

### 4. Política fija contextual
Se probó una política basada en las mejores secuencias detectadas.

Resultado:
- `final_reward = 0.0`
- `levels_completed = 0`
- `state = NOT_FINISHED`

### 5. Agente con rollback / undo
Se intentó usar:
- `ACTION7` como undo
- `_get_hidden_state()`
- `_get_valid_actions()`

Resultado:
- el wrapper expuesto por `arc.make(...)` no dejó acceder útilmente a esos métodos
- `hidden_state` quedó en `None`
- `valid_actions_runtime` quedó vacío
- el agente no obtuvo señales nuevas

## Qué reveló el código fuente del entorno

Leyendo `sk48.py` se detectó que:
- el entorno no es un ARC clásico simple, sino un puzzle estructural de matching entre pares de nodos
- el progreso real depende de que `gvtmoopqgy()` devuelva `True`
- solo entonces se activa una fase interna (`lgdrixfno`) y luego `next_level()`
- `ACTION6` cambia nodo activo válido
- `ACTION7` hace undo/restauración de snapshot

Esto explica por qué:
- maximizar reward no alcanzaba
- maximizar `changed_pixels` no alcanzaba
- secuencias visualmente activas no alcanzaban

## Lección principal

Para `sk48`, una estrategia black-box sobre el wrapper público no es suficiente.

No alcanza con optimizar:
- reward
- frame changes
- ranking de acciones
- secuencias cortas

La lógica relevante está en las reglas internas del entorno.

## Recomendación estratégica

### No seguir por esta vía
No seguir iterando agentes genéricos ni variantes black-box sobre `sk48`.

### Sí avanzar por esta vía
Si se desea continuar, hacerlo con un solver específico de entorno:
- usando `sk48.py` como especificación
- reconstruyendo pares de nodos
- reconstruyendo segmentos y matching
- aproximando o replicando la lógica de `gvtmoopqgy()`
- buscando secuencias con conocimiento interno del puzzle

## Estado final de esta línea de trabajo

La línea black-box queda documentada como:
- explorada con suficiente profundidad
- útil para aprendizaje del entorno
- no efectiva para resolver `sk48`

## Próximo paso recomendado

Mantener una baseline submission simple y estable para Kaggle, y abrir en paralelo una línea separada de I+D para un solver específico de `sk48` y, si corresponde, de otros entornos similares.
