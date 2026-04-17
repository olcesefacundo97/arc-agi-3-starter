# Results Comparison

Tabla base para comparar versiones del agente sobre entornos ARC-AGI-3 en modo offline.

## Métricas sugeridas

- `games_requested`: cantidad de entornos evaluados
- `games_succeeded`: cantidad de entornos ejecutados sin error
- `avg_steps`: promedio de pasos por entorno
- `avg_final_reward`: promedio de reward final
- `reward_gt_0`: cantidad de entornos con reward final mayor a 0
- `notes`: observaciones cualitativas

## Tabla comparativa

| Version | games_requested | games_succeeded | avg_steps | avg_final_reward | reward_gt_0 | notes |
|--------|------------------|-----------------|-----------|------------------|-------------|-------|
| V4     |                  |                 |           |                  |             | cambio de estado + novedad |
| V5     |                  |                 |           |                  |             | top-k action heuristic |
| V6     |                  |                 |           |                  |             | planner-lite más disciplinado |

## Cómo llenar esta tabla

1. Correr cada versión del notebook en modo offline.
2. Guardar el `summary` resultante.
3. Contar manualmente o con una celda adicional cuántos entornos terminaron con `final_reward > 0`.
4. Completar esta tabla en el repo para comparar mejoras reales.

## Siguiente paso recomendado

Una vez completada la tabla:

- decidir cuál versión queda como baseline principal
- documentar fortalezas y debilidades
- preparar el agente final para presentación/envío oficial
