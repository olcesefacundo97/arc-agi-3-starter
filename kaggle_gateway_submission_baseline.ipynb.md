# Kaggle Gateway Submission Baseline

Este notebook sigue el flujo correcto observado en el sample oficial:

- En modo competencia (`KAGGLE_IS_COMPETITION_RERUN`):
  - espera el gateway
  - copia el repo oficial `ARC-AGI-3-Agents`
  - inyecta un agente custom como `my_agent.py`
  - sobrescribe `agents/__init__.py` para evitar imports opcionales pesados
  - escribe `.env` apuntando al gateway
  - ejecuta `python main.py --agent myagent`

- Fuera de competencia:
  - genera un `submission.parquet` dummy para que el notebook sea submitteable

## Celda 1 — escribir agente custom mejorado

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Safe adaptive baseline agent.

    Objetivo:
    - mantener el flujo oficial del gateway
    - evitar dependencias pesadas
    - usar available_actions cuando esté disponible
    - combinar exploración simple con coordenadas estructuradas para ACTION6
    """

    MAX_ACTIONS = 120

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)
        self.last_frame_repr = None
        self.same_frame_count = 0
        self.coord_index = 0
        self.coord_candidates = [
            (0, 0), (0, 63), (63, 0), (63, 63),
            (32, 32), (16, 16), (48, 48), (16, 48), (48, 16),
            (8, 8), (24, 24), (40, 40), (56, 56),
            (8, 56), (56, 8), (24, 40), (40, 24),
        ]
        self.simple_pattern = [
            GameAction.ACTION1,
            GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION4,
            GameAction.ACTION1,
            GameAction.ACTION4,
            GameAction.ACTION2,
            GameAction.ACTION3,
        ]

    @property
    def name(self) -> str:
        return f"{super().name}.safe_adaptive.{self.MAX_ACTIONS}"

    def _available_action_ids(self, latest_frame: FrameData) -> set[int]:
        available = getattr(latest_frame, "available_actions", None)
        ids: set[int] = set()
        if available:
            for item in available:
                try:
                    ids.add(int(item.value))
                except Exception:
                    try:
                        ids.add(int(item))
                    except Exception:
                        pass
        return ids

    def _is_available(self, action: GameAction, available_ids: set[int]) -> bool:
        if not available_ids:
            return action is not GameAction.RESET
        return int(action.value) in available_ids

    def _next_coord(self) -> tuple[int, int]:
        coord = self.coord_candidates[self.coord_index % len(self.coord_candidates)]
        self.coord_index += 1
        return coord

    def _frame_signature(self, latest_frame: FrameData) -> str:
        try:
            return str(latest_frame.frame[-1])[:2000]
        except Exception:
            try:
                return str(latest_frame.frame)[:2000]
            except Exception:
                return "NO_FRAME"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return any([
            latest_frame.state is GameState.WIN,
            self.action_counter >= self.MAX_ACTIONS,
        ])

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            action = GameAction.RESET
            action.reasoning = "Reset because game is not started or game over."
            return action

        available_ids = self._available_action_ids(latest_frame)

        signature = self._frame_signature(latest_frame)
        if signature == self.last_frame_repr:
            self.same_frame_count += 1
        else:
            self.same_frame_count = 0
        self.last_frame_repr = signature

        # Si el frame parece estancado y ACTION6 está disponible, probar coordenadas estructuradas.
        if self.same_frame_count >= 3 and self._is_available(GameAction.ACTION6, available_ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Frame appeared stagnant; trying structured ACTION6 coordinate.",
            }
            return action

        # Priorizar patrón simple seguro respetando available_actions.
        for offset in range(len(self.simple_pattern)):
            idx = (self.action_counter + offset) % len(self.simple_pattern)
            candidate = self.simple_pattern[idx]
            if self._is_available(candidate, available_ids):
                candidate.reasoning = f"Safe adaptive pattern picked {candidate.value}"
                return candidate

        # Fallback: elegir cualquier acción disponible excepto RESET.
        candidates = []
        for a in GameAction:
            if a is GameAction.RESET:
                continue
            if self._is_available(a, available_ids):
                candidates.append(a)

        if not candidates:
            action = GameAction.RESET
            action.reasoning = "Fallback reset because no candidates were available."
            return action

        action = random.choice(candidates)
        if action.is_simple():
            action.reasoning = f"Fallback picked {action.value}"
        elif action.is_complex():
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Fallback structured coordinate action.",
            }
        return action
```

## Celda 2 — flujo oficial de gateway en rerun

```python
import os

if os.getenv('KAGGLE_IS_COMPETITION_RERUN'):
    !curl --fail --retry 999 --retry-all-errors --retry-delay 5 \
          --retry-max-time 600 http://gateway:8001/api/games

    !cp -r /kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents \
           /kaggle/working/ARC-AGI-3-Agents

    !cp /kaggle/working/my_agent.py \
        /kaggle/working/ARC-AGI-3-Agents/agents/templates/my_agent.py

    with open('/kaggle/working/ARC-AGI-3-Agents/agents/__init__.py', 'w') as f:
        f.write("""from typing import Type, cast
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.random_agent import Random
from .templates.my_agent import MyAgent

load_dotenv()

AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "random": Random,
    "myagent": MyAgent,
}
""")

    with open('/kaggle/working/ARC-AGI-3-Agents/.env', 'w') as f:
        f.write("""SCHEME=http
HOST=gateway
PORT=8001
ARC_API_KEY=test-key-123
ARC_BASE_URL=http://gateway:8001/
OPERATION_MODE=online
ENVIRONMENTS_DIR=
RECORDINGS_DIR=/kaggle/working/server_recording
""")

    !cd /kaggle/working/ARC-AGI-3-Agents && \
        MPLBACKEND=agg \
        python main.py --agent myagent
```

## Celda 3 — dummy local fuera de rerun

```python
import os
if not os.getenv('KAGGLE_IS_COMPETITION_RERUN'):
    import pandas as pd
    submission = pd.DataFrame(
        data=[['1_0', '1', True, 1]],
        columns=['row_id', 'game_id', 'end_of_game', 'score']
    )
    submission.to_parquet('/kaggle/working/submission.parquet', index=False)
    submission.head()
```

## Nota importante

No generar `submission.parquet` manualmente durante el rerun de competencia. El flujo correcto es ejecutar el agente contra el gateway, igual que el sample oficial.
