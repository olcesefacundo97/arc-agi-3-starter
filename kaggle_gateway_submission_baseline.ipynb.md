# Kaggle Gateway Submission Baseline

Este notebook sigue el flujo correcto observado en el sample oficial.

La versión actual usa un agente **sequence memory + política específica para sk48 con matching visual de pares y scoring estructural**:
- mantiene el flujo oficial del gateway
- respeta `available_actions`
- no genera manualmente `submission.parquet` durante el rerun
- usa una política especial para juegos `sk48*`
- detecta componentes conectados en el frame
- empareja componentes similares por color/tamaño/forma aproximada
- puntúa pares por similitud, separación, tamaño y centralidad
- usa centros de pares de mayor score como coordenadas candidatas para `ACTION6`
- para el resto, conserva memoria de acciones/secuencias

## Celda 1 — escribir agente custom con scoring estructural sk48

```python
%%writefile /kaggle/working/my_agent.py
import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Gateway-safe agent with sk48 structural pair scoring and generic sequence memory fallback."""

    MAX_ACTIONS = 235
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
        self.dynamic_coord_candidates: list[tuple[int, int]] = []
        self.pair_coord_candidates: list[tuple[int, int]] = []
        self.coord_candidates = [
            (0, 0), (0, 63), (63, 0), (63, 63),
            (32, 32), (16, 16), (48, 48), (16, 48), (48, 16),
            (8, 8), (24, 24), (40, 40), (56, 56),
            (8, 56), (56, 8), (24, 40), (40, 24),
            (13, 38), (22, 58), (11, 36), (20, 56),
            (31, 31), (32, 31), (31, 32), (33, 33),
        ]

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
        self.sk48_probe_every = 5

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
        return f"{super().name}.sk48_struct_score_seq.{self.MAX_ACTIONS}"

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

    def _latest_grid(self, latest_frame: FrameData):
        try:
            frame = latest_frame.frame[-1]
            if len(frame) == 64 and len(frame[0]) == 64:
                return frame
        except Exception:
            pass
        return None

    def _background_color(self, grid) -> int | None:
        counts: dict[int, int] = {}
        for y in range(64):
            row = grid[y]
            for x in range(64):
                try:
                    c = int(row[x])
                except Exception:
                    continue
                counts[c] = counts.get(c, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _connected_components(self, latest_frame: FrameData) -> list[dict[str, int]]:
        grid = self._latest_grid(latest_frame)
        if grid is None:
            return []
        bg = self._background_color(grid)
        if bg is None:
            return []

        visited = [[False for _ in range(64)] for _ in range(64)]
        comps: list[dict[str, int]] = []

        for sy in range(64):
            for sx in range(64):
                if visited[sy][sx]:
                    continue
                visited[sy][sx] = True
                try:
                    color = int(grid[sy][sx])
                except Exception:
                    continue
                if color == bg:
                    continue

                stack = [(sx, sy)]
                minx = maxx = sx
                miny = maxy = sy
                count = 0

                while stack:
                    x, y = stack.pop()
                    count += 1
                    if x < minx: minx = x
                    if x > maxx: maxx = x
                    if y < miny: miny = y
                    if y > maxy: maxy = y

                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if nx < 0 or nx >= 64 or ny < 0 or ny >= 64:
                            continue
                        if visited[ny][nx]:
                            continue
                        visited[ny][nx] = True
                        try:
                            nc = int(grid[ny][nx])
                        except Exception:
                            continue
                        if nc == color:
                            stack.append((nx, ny))

                if count < 4:
                    continue
                w = maxx - minx + 1
                h = maxy - miny + 1
                if w > 45 or h > 45:
                    continue

                comps.append({
                    "color": color,
                    "count": count,
                    "minx": minx,
                    "miny": miny,
                    "maxx": maxx,
                    "maxy": maxy,
                    "w": w,
                    "h": h,
                    "cx": int((minx + maxx) / 2),
                    "cy": int((miny + maxy) / 2),
                })

        return comps[:80]

    def _pair_distance(self, a: dict[str, int], b: dict[str, int]) -> float:
        return (
            abs(a["color"] - b["color"]) * 2.0
            + abs(a["count"] - b["count"]) * 0.25
            + abs(a["w"] - b["w"]) * 1.2
            + abs(a["h"] - b["h"]) * 1.2
        )

    def _pair_structural_score(self, a: dict[str, int], b: dict[str, int]) -> float:
        similarity = self._pair_distance(a, b)
        spatial = abs(a["cx"] - b["cx"]) + abs(a["cy"] - b["cy"])
        size = a["count"] + b["count"]
        center_bias = abs(((a["cx"] + b["cx"]) / 2) - 32) + abs(((a["cy"] + b["cy"]) / 2) - 32)

        if spatial < 6:
            return -999.0
        if size < 8:
            return -999.0

        # Higher is better: very similar pair, separated enough, not too huge, reasonably central.
        score = 40.0
        score -= similarity * 2.5
        score += min(spatial, 40) * 0.18
        score -= max(0, size - 80) * 0.03
        score -= center_bias * 0.04
        return score

    def _detect_pair_centers(self, latest_frame: FrameData) -> list[tuple[int, int]]:
        comps = self._connected_components(latest_frame)
        if not comps:
            return []

        scored_pairs: list[tuple[float, dict[str, int], dict[str, int]]] = []
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                a = comps[i]
                b = comps[j]
                score = self._pair_structural_score(a, b)
                if score > 15.0:
                    scored_pairs.append((score, a, b))

        scored_pairs.sort(key=lambda t: t[0], reverse=True)

        coords: list[tuple[int, int]] = []
        seen = set()
        for _, a, b in scored_pairs[:8]:
            # Prefer the smaller/active-looking component first, then its pair.
            ordered = (a, b) if a["count"] <= b["count"] else (b, a)
            for c in ordered:
                p = (c["cx"], c["cy"])
                if p not in seen:
                    coords.append(p)
                    seen.add(p)
        return coords[:16]

    def _detect_visual_centers(self, latest_frame: FrameData) -> list[tuple[int, int]]:
        comps = self._connected_components(latest_frame)
        # Prefer actionable component sizes.
        centers = [(c["cx"], c["cy"]) for c in comps if 4 <= c["count"] <= 180]
        centers = sorted(set(centers), key=lambda p: (abs(p[0] - 32) + abs(p[1] - 32), p[1], p[0]))
        return centers[:12]

    def _refresh_dynamic_coords(self, latest_frame: FrameData) -> None:
        if not str(self.game_id).startswith("sk48"):
            return
        pair_centers = self._detect_pair_centers(latest_frame)
        visual_centers = self._detect_visual_centers(latest_frame)
        merged = []
        seen = set()
        for p in pair_centers + visual_centers + self.coord_candidates:
            if p not in seen:
                merged.append(p)
                seen.add(p)
        if merged:
            self.pair_coord_candidates = pair_centers
            self.dynamic_coord_candidates = merged[:40]

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
        if self.pair_coord_candidates and self.coord_index % 2 == 0:
            pool = self.pair_coord_candidates
        else:
            pool = self.dynamic_coord_candidates if self.dynamic_coord_candidates else self.coord_candidates
        coord = pool[self.coord_index % len(pool)]
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
        order = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]
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

    def _sk48_policy(self, latest_frame: FrameData, ids: set[int], memory_key: str) -> GameAction | None:
        if not str(self.game_id).startswith("sk48"):
            return None

        self._refresh_dynamic_coords(latest_frame)

        # Probe ACTION6 using top-scored pair centers when available.
        if self.action_counter > 0 and self.action_counter % self.sk48_probe_every == 0 and self._is_available(GameAction.ACTION6, ids):
            action = GameAction.ACTION6
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "sk48 structural-scoring branch probing top pair coordinate.",
            }
            return action

        candidate = self.sk48_plan[self.action_counter % len(self.sk48_plan)]
        if self._is_available(candidate, ids):
            candidate.reasoning = f"sk48 structural-scored policy picked {candidate.value}."
            return candidate

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

        sk48_action = self._sk48_policy(latest_frame, ids, memory_key)
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
