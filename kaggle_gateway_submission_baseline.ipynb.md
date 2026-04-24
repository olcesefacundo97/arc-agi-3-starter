# Kaggle Gateway Submission Baseline

Este notebook sigue el flujo correcto observado en el sample oficial.

La versión actual usa un agente **sequence memory + política específica para sk48**:
- mantiene el flujo oficial del gateway
- respeta `available_actions`
- no genera manualmente `submission.parquet` durante el rerun
- usa una política especial para juegos `sk48*`
- para el resto, conserva memoria de acciones/secuencias

## Celda 1 — escribir agente custom con política específica sk48

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Gateway-safe agent with sk48-specific branch and generic sequence memory fallback."""

    MAX_ACTIONS = 220
    BEAM_WIDTH = 3
    MEMORY_LIMIT = 700
    SEQUENCE_MAX_LEN = 3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

        self.last_signature = None
        self.last_memory_key = None
        self.last_action_key = None
        self.same_frame_count = 0
        self.best_score_seen = -1
        self.last_score = 0

        self.action_scores: dict[str, float] = {}
        self.action_counts: dict[str, int] = {}
        self.action_nochange: dict[str, int] = {}
        self.recent_actions: list[str] = []
        self.recent_contexts: list[tuple[str, str]] = []

        self.state_memory: dict[str, dict[str, float]] = {}
        self.state_sequence_memory: dict[str, dict[tuple[str, ...], float]] = {}
        self.state_hits: dict[str, int] = {}

        self.active_sequence: list[str] = []

        self.coord_index = 0
        self.coord_candidates = [
            (0, 0), (0, 63), (63, 0), (63, 63),
            (32, 32), (16, 16), (48, 48), (16, 48), (48, 16),
            (8, 8), (24, 24), (40, 40), (56, 56),
            (8, 56), (56, 8), (24, 40), (40, 24),
            (13, 38), (22, 58), (11, 36), (20, 56),
            (31, 31), (32, 31), (31, 32), (33, 33),
        ]

        # sk48: basado en investigación offline:
        # ACTION1/ACTION2 desplazan verticalmente; ACTION3/ACTION4 alteran estructura local;
        # ACTION6 requiere coordenadas y puede ser importante, pero se usa con cuidado.
        self.sk48_plan = [
            GameAction.ACTION1, GameAction.ACTION1, GameAction.ACTION1, GameAction.ACTION1,
            GameAction.ACTION3,
            GameAction.ACTION4,
            GameAction.ACTION2, GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION1,
            GameAction.ACTION4,
            GameAction.ACTION2,
        ]
        self.sk48_probe_every = 10

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
        return f"{super().name}.sk48_seq_memory.{self.MAX_ACTIONS}"

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
            return str(latest_frame.frame[-1])[:3500]
        except Exception:
            try:
                return str(latest_frame.frame)[:3500]
            except Exception:
                return "NO_FRAME"

    def _memory_key_from_signature(self, signature: str) -> str:
        return str(hash(signature[:1200]))

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

    def _action_from_key(self, key: str) -> GameAction | None:
        try:
            if key.endswith(":complex"):
                return GameAction.ACTION6
            value = int(key)
            for action in GameAction:
                if int(action.value) == value:
                    return action
        except Exception:
            return None
        return None

    def _trim_memory(self) -> None:
        if len(self.state_memory) <= self.MEMORY_LIMIT:
            return
        ordered = sorted(self.state_hits.items(), key=lambda kv: kv[1])
        for key, _ in ordered[: max(1, len(ordered) - self.MEMORY_LIMIT)]:
            self.state_memory.pop(key, None)
            self.state_sequence_memory.pop(key, None)
            self.state_hits.pop(key, None)

    def _update_state_memory(self, memory_key: str | None, action_key: str | None, reward_delta: float) -> None:
        if memory_key is None or action_key is None:
            return
        if memory_key not in self.state_memory:
            self.state_memory[memory_key] = {}
        self.state_memory[memory_key][action_key] = self.state_memory[memory_key].get(action_key, 0.0) + reward_delta
        self.state_hits[memory_key] = self.state_hits.get(memory_key, 0) + 1
        self._trim_memory()

    def _update_sequence_memory(self, reward_delta: float) -> None:
        if reward_delta == 0 or len(self.recent_contexts) < 2:
            return
        max_len = min(self.SEQUENCE_MAX_LEN, len(self.recent_contexts))
        for length in range(2, max_len + 1):
            window = self.recent_contexts[-length:]
            start_state = window[0][0]
            seq = tuple(action_key for _, action_key in window)
            if start_state not in self.state_sequence_memory:
                self.state_sequence_memory[start_state] = {}
            scaled = reward_delta / float(length)
            self.state_sequence_memory[start_state][seq] = self.state_sequence_memory[start_state].get(seq, 0.0) + scaled

    def _register_previous_outcome(self, latest_frame: FrameData) -> tuple[str, str]:
        signature = self._frame_signature(latest_frame)
        memory_key = self._memory_key_from_signature(signature)
        score_now = self._score_value(latest_frame)

        changed = self.last_signature is not None and signature != self.last_signature
        score_delta = score_now - self.last_score
        score_improved = score_now > self.best_score_seen

        reward_delta = 0.0
        if changed:
            reward_delta += 1.0
        else:
            reward_delta -= 0.45
        if score_delta > 0:
            reward_delta += 15.0 * score_delta
        elif score_improved:
            reward_delta += 10.0
        if self.same_frame_count >= 2:
            reward_delta -= 0.10

        if self.last_action_key is not None:
            self.action_counts[self.last_action_key] = self.action_counts.get(self.last_action_key, 0) + 1
            if not changed:
                self.action_nochange[self.last_action_key] = self.action_nochange.get(self.last_action_key, 0) + 1
            self.action_scores[self.last_action_key] = self.action_scores.get(self.last_action_key, 0.0) + reward_delta
            self._update_state_memory(self.last_memory_key, self.last_action_key, reward_delta)
            self._update_sequence_memory(reward_delta)

        if signature == self.last_signature:
            self.same_frame_count += 1
        else:
            self.same_frame_count = 0

        self.last_signature = signature
        self.last_score = score_now
        if score_now > self.best_score_seen:
            self.best_score_seen = score_now

        return signature, memory_key

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

    def _rank_actions(self, ids: set[int], memory_key: str) -> list[GameAction]:
        ranked = []
        local_memory = self.state_memory.get(memory_key, {})
        for action in self._candidate_actions(ids):
            key = self._key_for_action(action)
            global_score = self.action_scores.get(key, 0.0)
            local_score = local_memory.get(key, 0.0)
            count = self.action_counts.get(key, 0)
            nochange = self.action_nochange.get(key, 0)
            exploration_bonus = 1.25 / (1.0 + count)
            nochange_penalty = 0.20 * nochange
            repetition_penalty = 0.35 if self.recent_actions[-3:].count(key) >= 2 else 0.0
            value = global_score + 1.75 * local_score + exploration_bonus - nochange_penalty - repetition_penalty
            ranked.append((value, action))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in ranked]

    def _memory_action(self, ids: set[int], memory_key: str) -> GameAction | None:
        local_memory = self.state_memory.get(memory_key, {})
        if not local_memory:
            return None
        sorted_items = sorted(local_memory.items(), key=lambda kv: kv[1], reverse=True)
        for action_key, value in sorted_items[:3]:
            if value <= 0:
                continue
            action = self._action_from_key(action_key)
            if action is not None and self._is_available(action, ids):
                return action
        return None

    def _sequence_for_state(self, ids: set[int], memory_key: str) -> list[str]:
        seq_memory = self.state_sequence_memory.get(memory_key, {})
        if not seq_memory:
            return []
        sorted_items = sorted(seq_memory.items(), key=lambda kv: kv[1], reverse=True)
        for seq, value in sorted_items[:5]:
            if value <= 0:
                continue
            valid = True
            for action_key in seq:
                action = self._action_from_key(action_key)
                if action is None or not self._is_available(action, ids):
                    valid = False
                    break
            if valid:
                return list(seq)
        return []

    def _beam_pick(self, ranked: list[GameAction], memory_action: GameAction | None) -> GameAction:
        if memory_action is not None and random.random() < 0.52:
            return memory_action
        if not ranked:
            return GameAction.RESET
        beam = ranked[: self.BEAM_WIDTH]
        r = random.random()
        if r < 0.62:
            return beam[0]
        if r < 0.90:
            return random.choice(beam)
        return random.choice(ranked)

    def _record_chosen_action(self, memory_key: str, action: GameAction) -> None:
        self.last_action_key = self._key_for_action(action)
        self.last_memory_key = memory_key
        self.recent_actions.append(self.last_action_key)
        self.recent_actions = self.recent_actions[-10:]
        self.recent_contexts.append((memory_key, self.last_action_key))
        self.recent_contexts = self.recent_contexts[-8:]

    def _action_from_sequence_key(self, action_key: str) -> GameAction | None:
        return self._action_from_key(action_key)

    def _sk48_policy(self, ids: set[int], memory_key: str) -> GameAction | None:
        if not str(self.game_id).startswith("sk48"):
            return None

        # Periodically probe ACTION6 with structured coords, but do not spam it.
        if self.action_counter > 0 and self.action_counter % self.sk48_probe_every == 0 and self._is_available(GameAction.ACTION6, ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "sk48 branch probing ACTION6 coordinate based on offline diagnostics.",
            }
            return action

        # Deterministic structural pattern for sk48.
        candidate = self.sk48_plan[self.action_counter % len(self.sk48_plan)]
        if self._is_available(candidate, ids):
            candidate.reasoning = f"sk48 structural policy picked {candidate.value}."
            return candidate

        # If planned action unavailable, fallback to ranked generic action.
        ranked = self._rank_actions(ids, memory_key)
        if ranked:
            action = ranked[0]
            action.reasoning = f"sk48 fallback ranked action {action.value}."
            return action
        return None

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return any([
            latest_frame.state is GameState.WIN,
            self.action_counter >= self.MAX_ACTIONS,
        ])

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            self.active_sequence = []
            action = GameAction.RESET
            action.reasoning = "Reset because game is not started or game over."
            return action

        _, memory_key = self._register_previous_outcome(latest_frame)
        ids = self._available_action_ids(latest_frame)

        sk48_action = self._sk48_policy(ids, memory_key)
        if sk48_action is not None:
            self._record_chosen_action(memory_key, sk48_action)
            return sk48_action

        while self.active_sequence:
            next_key = self.active_sequence.pop(0)
            seq_action = self._action_from_sequence_key(next_key)
            if seq_action is not None and self._is_available(seq_action, ids):
                seq_action.reasoning = f"Continuing learned sequence with action {seq_action.value}."
                self._record_chosen_action(memory_key, seq_action)
                return seq_action

        if random.random() < 0.45:
            seq = self._sequence_for_state(ids, memory_key)
            if seq:
                first_key = seq.pop(0)
                self.active_sequence = seq
                action = self._action_from_sequence_key(first_key)
                if action is not None and self._is_available(action, ids):
                    action.reasoning = f"Starting learned sequence with action {action.value}."
                    self._record_chosen_action(memory_key, action)
                    return action

        if self.same_frame_count >= 2 and self._is_available(GameAction.ACTION6, ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Sequence memory detected stagnation; probing structured ACTION6 coordinate.",
            }
            self._record_chosen_action(memory_key, action)
            return action

        memory_action = self._memory_action(ids, memory_key)
        ranked = self._rank_actions(ids, memory_key)
        action = self._beam_pick(ranked, memory_action)

        if action is GameAction.RESET:
            action.reasoning = "Fallback reset from empty sequence memory."
            self.last_action_key = None
            self.last_memory_key = memory_key
            return action

        action.reasoning = f"Sequence memory picked {action.value}."
        self._record_chosen_action(memory_key, action)
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
