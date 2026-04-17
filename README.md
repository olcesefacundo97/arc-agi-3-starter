# 🧠 ARC-AGI-3 Starter Kit
_Agente base para entornos interactivos – ARC Prize 2026_

## Descripción

Este repositorio contiene un starter kit modular en Python para desarrollar agentes en ARC-AGI-3.

A diferencia de benchmarks clásicos, ARC-AGI-3 no consiste en predecir respuestas, sino en aprender actuando.

## Objetivo del proyecto

Construir un agente que:

- Interactúe con entornos sin instrucciones explícitas
- Descubra patrones y objetivos por exploración
- Optimice decisiones en función de recompensas
- Generalice a entornos nunca vistos

## Arquitectura

Agent = Perception -> Memory -> Policy -> Action

## Estructura del repositorio

```text
arc-agi-3-starter/
├── agents/
├── core/
├── notebooks/
├── results/
├── replays/
├── run_local.py
├── evaluate.py
```

## Instalación

```bash
git clone https://github.com/olcesefacundo97/arc-agi-3-starter.git
cd arc-agi-3-starter
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Uso

```bash
python run_local.py --game ls20 --agent random
python run_local.py --agent heuristic
python run_local.py --agent memory
python evaluate.py --games ls20 ls21 ls22 --agent heuristic
```

## Agentes incluidos

### RandomAgent
Selección completamente aleatoria.

### HeuristicAgent
Penaliza acciones repetidas y mejora exploración básica.

### MemoryAgent
Registra estados visitados y ayuda a evitar loops.

## Estrategia de mejora

1. Baseline (Random)
2. Exploración heurística
3. Memoria episódica
4. Novelty bonus
5. Planner corto (lookahead)
6. Clasificación de entornos
7. Optimización de políticas

## Competencia Kaggle

Proyecto preparado para integrarse con ARC Prize 2026 ARC-AGI-3 en Kaggle.

## Autor

**Facundo Olcese**
Analista Funcional | Data & AI

## Licencia

MIT
