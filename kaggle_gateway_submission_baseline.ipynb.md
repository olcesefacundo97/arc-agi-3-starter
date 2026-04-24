# Kaggle Gateway Submission Baseline

Este notebook sigue el flujo correcto observado en el sample oficial.

La versión actual usa un agente **online beam-like heuristic search**:
- mantiene el flujo oficial del gateway
- respeta `available_actions`
- no genera manualmente `submission.parquet` durante el rerun
- aprende qué acciones producen cambios observables
- mantiene un pequeño beam de candidatas y elige entre las mejores con exploración controlada
- usa `ACTION6` con coordenadas estructuradas ante estancamiento

## Celda 1 — escribir agente custom beam-like heuristic

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Gateway-safe online beam-like heuristic agent.

    No puede simular ramas reales desde el gateway, así que implementa un beam online:
    - rankea acciones por evidencia histórica
    - conserva top-k candidatas
    - alterna explotación con exploración
    - usa ACTION6 con coordenadas estructuradas cuando detecta estancamiento
    """

    MAX_ACTIONS = 180
    BEAM_WIDTH = 3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

        self.last_signature = None
        self.last_action_key = None
        self.same_frame_count = 0
        self.best_score_seen = -1
        self.last_score = 0

        self.action_scores: dict[str, float] = {}
        self.action_counts: dict[str, int] = {}
        self.action_nochange: dict[str, int] = {}
        self.recent_actions: list[str] = []

        self.coord_index = 0
        self.coord_candidates = [
            (0, 0), (0, 63), (63, 0), (63, 63),
            (32, 32), (16, 16), (48, 48), (16, 48), (48, 16),
            (8, 8), (24, 24), (40, 40), (56, 56),
            (8, 56), (56, 8), (24, 40), (40, 24),
            # coords observed / useful in sk48 diagnostics
            (13, 38), (22, 58), (11, 36), (20, 56),
            # additional center-ish probes
            (31, 31), (32, 31), (31, 32), (33, 33),
        ]

        self.bootstrap_pattern = [
            GameAction.ACTION1,
            GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION4,
            GameAction.ACTION1,
            GameAction.ACTION4,
            GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION5,
            GameAction.ACTION7,
        ]

    @property
    def name(self) -> str:
        return f"{super().name}.online_beam.{self.MAX_ACTIONS}.k{self.BEAM_WIDTH}"

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
            return str(latest_frame.frame[-1])[:3000]
        except Exception:
            try:
                return str(latest_frame.frame)[:3000]
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
        score_delta = score_now - self.last_score
        score_improved = score_now > self.best_score_seen

        if self.last_action_key is not None:
            self.action_counts[self.last_action_key] = self.action_counts.get(self.last_action_key, 0) + 1

            delta = 0.0
            if changed:
                delta += 1.0
            else:
                delta -= 0.45
                self.action_nochange[self.last_action_key] = self.action_nochange.get(self.last_action_key, 0) + 1

            if score_delta > 0:
                delta += 15.0 * score_delta
            elif score_improved:
                delta += 10.0

            # discourage repeatedly trying the same thing when stuck
            if self.same_frame_count >= 2:
                delta -= 0.10

            self.action_scores[self.last_action_key] = self.action_scores.get(self.last_action_key, 0.0) + delta

        if signature == self.last_signature:
            self.same_frame_count += 1
        else:
            self.same_frame_count = 0

        self.last_signature = signature
        self.last_score = score_now
        if score_now > self.best_score_seen:
            self.best_score_seen = score_now

    def _candidate_actions(self, ids: set[int]) -> list[GameAction]:
        order = [
            GameAction.ACTION1,
            GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION4,
            GameAction.ACTION5,
            GameAction.ACTION7,
        ]
        candidates = [a for a in order if self._is_available(a, ids)]
        if not candidates:
            candidates = [a for a in self.bootstrap_pattern if self._is_available(a, ids)]
        return candidates

    def _rank_actions(self, ids: set[int]) -> list[GameAction]:
        ranked = []
        for action in self._candidate_actions(ids):
            key = self._key_for_action(action)
            base_score = self.action_scores.get(key, 0.0)
            count = self.action_counts.get(key, 0)
            nochange = self.action_nochange.get(key, 0)

            exploration_bonus = 1.25 / (1.0 + count)
            nochange_penalty = 0.20 * nochange
            repetition_penalty = 0.35 if self.recent_actions[-3:].count(key) >= 2 else 0.0

            ranked.append((base_score + exploration_bonus - nochange_penalty - repetition_penalty, action))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in ranked]

    def _beam_pick(self, ranked: list[GameAction]) -> GameAction:
        if not ranked:
            return GameAction.RESET

        beam = ranked[: self.BEAM_WIDTH]

        # Mostly exploit the beam leader, sometimes explore within the beam.
        r = random.random()
        if r < 0.68:
            return beam[0]
        if r < 0.90:
            return random.choice(beam)
        return random.choice(ranked)

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

        # Stagnation branch: probe complex coordinate action if allowed.
        if self.same_frame_count >= 2 and self._is_available(GameAction.ACTION6, ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Online beam detected stagnation; probing structured ACTION6 coordinate.",
            }
            self.last_action_key = self._key_for_action(action)
            self.recent_actions.append(self.last_action_key)
            self.recent_actions = self.recent_actions[-10:]
            return action

        ranked = self._rank_actions(ids)
        action = self._beam_pick(ranked)

        if action is GameAction.RESET:
            action.reasoning = "Fallback reset from empty beam."
            self.last_action_key = None
            return action

        action.reasoning = f"Online beam picked {action.value} from top-{self.BEAM_WIDTH} candidates."
        self.last_action_key = self._key_for_action(action)
        self.recent_actions.append(self.last_action_key)
        self.recent_actions = self.recent_actions[-10:]
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
