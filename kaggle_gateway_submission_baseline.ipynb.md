# Kaggle Gateway Submission Baseline

Este notebook sigue el flujo correcto observado en el sample oficial.

La versión actual usa un agente heurístico seguro:
- respeta `available_actions`
- aprende qué acciones suelen cambiar el frame
- penaliza acciones que no producen cambios
- usa `ACTION6` con coordenadas estructuradas solo cuando conviene explorar
- mantiene el flujo oficial del gateway sin generar manualmente el parquet durante el rerun

## Celda 1 — escribir agente custom heuristic solver

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Gateway-safe heuristic solver baseline.

    Este agente no accede a estado interno del entorno.
    Trabaja únicamente con la interfaz pública del gateway:
    - latest_frame
    - available_actions
    - niveles completados
    - cambios de frame observables
    """

    MAX_ACTIONS = 160

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

        self.last_signature = None
        self.last_action_key = None
        self.same_frame_count = 0
        self.best_score_seen = -1

        self.action_scores: dict[str, float] = {}
        self.action_counts: dict[str, int] = {}
        self.action_nochange: dict[str, int] = {}

        self.coord_index = 0
        self.coord_candidates = [
            (0, 0), (0, 63), (63, 0), (63, 63),
            (32, 32), (16, 16), (48, 48), (16, 48), (48, 16),
            (8, 8), (24, 24), (40, 40), (56, 56),
            (8, 56), (56, 8), (24, 40), (40, 24),
            (13, 38), (22, 58), (11, 36), (20, 56),
        ]

        self.default_pattern = [
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
        return f"{super().name}.heuristic_solver.{self.MAX_ACTIONS}"

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

    def _is_available(self, action: GameAction, ids: set[int]) -> bool:
        if action is GameAction.RESET:
            return False
        if not ids:
            return True
        return int(action.value) in ids

    def _frame_signature(self, latest_frame: FrameData) -> str:
        try:
            return str(latest_frame.frame[-1])[:2500]
        except Exception:
            try:
                return str(latest_frame.frame)[:2500]
            except Exception:
                return "NO_FRAME"

    def _score_value(self, latest_frame: FrameData) -> int:
        try:
            return int(getattr(latest_frame, "levels_completed", 0))
        except Exception:
            return 0

    def _next_coord(self) -> tuple[int, int]:
        coord = self.coord_candidates[self.coord_index % len(self.coord_candidates)]
        self.coord_index += 1
        return coord

    def _key_for_action(self, action: GameAction) -> str:
        try:
            if action.is_complex():
                return f"{int(action.value)}:complex"
            return str(int(action.value))
        except Exception:
            return str(action)

    def _register_previous_outcome(self, latest_frame: FrameData) -> None:
        signature = self._frame_signature(latest_frame)
        score_now = self._score_value(latest_frame)

        changed = self.last_signature is not None and signature != self.last_signature
        score_improved = score_now > self.best_score_seen

        if self.last_action_key is not None:
            self.action_counts[self.last_action_key] = self.action_counts.get(self.last_action_key, 0) + 1

            delta = 0.0
            if changed:
                delta += 1.0
            else:
                delta -= 0.35
                self.action_nochange[self.last_action_key] = self.action_nochange.get(self.last_action_key, 0) + 1

            if score_improved:
                delta += 10.0

            self.action_scores[self.last_action_key] = self.action_scores.get(self.last_action_key, 0.0) + delta

        if signature == self.last_signature:
            self.same_frame_count += 1
        else:
            self.same_frame_count = 0

        self.last_signature = signature
        if score_now > self.best_score_seen:
            self.best_score_seen = score_now

    def _rank_simple_actions(self, ids: set[int]) -> list[GameAction]:
        candidates = []
        for action in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]:
            if self._is_available(action, ids):
                key = self._key_for_action(action)
                score = self.action_scores.get(key, 0.0)
                count = self.action_counts.get(key, 0)
                nochange = self.action_nochange.get(key, 0)
                exploration_bonus = 1.0 / (1.0 + count)
                penalty = 0.15 * nochange
                candidates.append((score + exploration_bonus - penalty, action))

        if not candidates:
            for action in self.default_pattern:
                if self._is_available(action, ids):
                    candidates.append((0.0, action))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in candidates]

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

        self._register_previous_outcome(latest_frame)
        ids = self._available_action_ids(latest_frame)

        # Si estamos estancados, probar ACTION6 con coordenadas estructuradas si está disponible.
        if self.same_frame_count >= 2 and self._is_available(GameAction.ACTION6, ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Heuristic solver detected stagnation and is probing ACTION6 coordinates.",
            }
            self.last_action_key = self._key_for_action(action)
            return action

        ranked = self._rank_simple_actions(ids)
        if ranked:
            # Mezclar explotación y exploración para no casarse con una acción mediocre.
            if random.random() < 0.78:
                action = ranked[0]
            else:
                action = random.choice(ranked[: min(3, len(ranked))])
            action.reasoning = f"Heuristic ranked action {action.value}"
            self.last_action_key = self._key_for_action(action)
            return action

        # Fallback defensivo.
        action = GameAction.RESET
        action.reasoning = "No valid ranked actions; fallback reset."
        self.last_action_key = None
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
