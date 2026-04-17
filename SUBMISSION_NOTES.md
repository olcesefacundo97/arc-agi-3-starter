# Submission Notes

## Estado actual del proyecto

Este repositorio ya validó técnicamente los siguientes puntos:

- carga offline de entornos ARC-AGI-3 usando `OperationMode.OFFLINE`
- uso de `environment_files` locales
- ejecución de juegos reales sin depender de `three.arcprize.org`
- generación de scorecard local
- pruebas de agentes baseline y variantes adaptadas al contrato del starter oficial

## Diagnóstico sobre Kaggle

Se intentó utilizar Kaggle como canal de submission, pero aunque el notebook corre correctamente, la submission falla con un error genérico del sistema.

La evidencia acumulada sugiere que el problema no está en la sintaxis ni en la ejecución básica del notebook, sino en que el flujo custom usado no coincide con el pipeline exacto de evaluación esperado.

## Hallazgo clave del README oficial

El README oficial de `ARC-AGI-3-Agents` indica que el envío para la competencia debe realizarse mediante un formulario oficial:

https://forms.gle/wMLZrEFGDh33DhzV9

Además, el quickstart oficial sigue orientado a API/web y no documenta un flujo de submission Kaggle offline equivalente.

## Conclusión práctica

No seguir iterando notebooks custom para Kaggle hasta no tener confirmación explícita del pipeline de evaluación correcto.

El camino recomendado es:

1. Mantener este repositorio como baseline técnico y experimental.
2. Ordenar el agente y la documentación.
3. Preparar el material para el canal oficial de envío documentado por ARC Prize.

## Checklist de preparación para envío oficial

- [ ] confirmar versión final del agente a presentar
- [ ] documentar estrategia del agente
- [ ] documentar dependencias y modo offline/online
- [ ] agregar instrucciones claras de ejecución
- [ ] incluir evidencia de pruebas locales/offline
- [ ] revisar si hace falta demo, video o documentación adicional
- [ ] completar formulario oficial de submission

## Próximos pasos recomendados para este repo

- limpiar README para distinguir claramente entre experimento local y submission oficial
- consolidar un único agente baseline estable
- agregar notas sobre limitaciones actuales del flujo Kaggle
- preparar una versión más prolija del agente para presentar
