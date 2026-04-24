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

## Celda 1 — escribir agente custom

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    MAX_ACTIONS = 80

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            action = GameAction.RESET
        else:
            available = getattr(latest_frame, "available_actions", None)
            candidates = []
            if available:
                for a in GameAction:
                    if a is GameAction.RESET:
                        continue
                    try:
                        if int(a.value) in [int(x) for x in available]:
                            candidates.append(a)
                    except Exception:
                        pass
            if not candidates:
                candidates = [a for a in GameAction if a is not GameAction.RESET]
            action = random.choice(candidates)

        if action.is_simple():
            action.reasoning = f"Baseline picked {action.value}"
        elif action.is_complex():
            action.set_data({"x": random.randint(0, 63), "y": random.randint(0, 63)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Baseline random coordinate action",
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
