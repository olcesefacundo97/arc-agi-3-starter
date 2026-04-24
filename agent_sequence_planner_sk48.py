import random
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState


class MyAgent(Agent):
    """Gateway-safe sequence planner for sk48 + generic fallback.

    Planner idea:
    - Builds short candidate plans.
    - Executes one plan step by step.
    - Rewards/penalizes the plan after observing frame/structural deltas.
    - Reuses plans that worked in similar states.
    """

    MAX_ACTIONS = 260
    MEMORY_LIMIT = 700
    SEQUENCE_MAX_LEN = 4
    PLAN_MAX_LEN = 4

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
        self.last_structural_value = None

        self.action_scores: dict[str, float] = {}
        self.action_counts: dict[str, int] = {}
        self.action_nochange: dict[str, int] = {}

        self.state_memory: dict[str, dict[str, float]] = {}
        self.sequence_memory: dict[str, dict[tuple[str, ...], float]] = {}
        self.plan_memory: dict[str, dict[tuple[str, ...], float]] = {}
        self.state_hits: dict[str, int] = {}

        self.recent_actions: list[str] = []
        self.recent_contexts: list[tuple[str, str]] = []

        self.active_plan: list[str] = []
        self.active_plan_origin_key: str | None = None
        self.active_plan_tuple: tuple[str, ...] | None = None
        self.active_plan_reward_accum = 0.0

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

        self.sk48_seed_plans: list[tuple[str, ...]] = [
            ("1", "1", "1", "3"),
            ("1", "1", "4", "2"),
            ("3", "4", "2"),
            ("1", "3", "4"),
            ("2", "2", "3"),
            ("1", "4", "2"),
            ("6:complex", "3", "4"),
            ("1", "1", "6:complex"),
            ("3", "6:complex", "4"),
        ]

    @property
    def name(self) -> str:
        return f"{super().name}.sk48_sequence_planner.{self.MAX_ACTIONS}"

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
                    if x < minx:
                        minx = x
                    if x > maxx:
                        maxx = x
                    if y < miny:
                        miny = y
                    if y > maxy:
                        maxy = y

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

        if spatial < 6 or size < 8:
            return -999.0

        score = 40.0
        score -= similarity * 2.5
        score += min(spatial, 40) * 0.18
        score -= max(0, size - 80) * 0.03
        score -= center_bias * 0.04
        return score

    def _structural_value(self, latest_frame: FrameData) -> float:
        comps = self._connected_components(latest_frame)
        if not comps:
            return 0.0
        scores = []
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                s = self._pair_structural_score(comps[i], comps[j])
                if s > 0:
                    scores.append(s)
        if not scores:
            return 0.0
        scores.sort(reverse=True)
        return sum(scores[:5]) + 0.35 * len(scores[:12])

    def _detect_pair_centers(self, latest_frame: FrameData) -> list[tuple[int, int]]:
        comps = self._connected_components(latest_frame)
        if not comps:
            return []
        scored_pairs: list[tuple[float, dict[str, int], dict[str, int]]] = []
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                score = self._pair_structural_score(comps[i], comps[j])
                if score > 15.0:
                    scored_pairs.append((score, comps[i], comps[j]))
        scored_pairs.sort(key=lambda t: t[0], reverse=True)

        coords: list[tuple[int, int]] = []
        seen = set()
        for _, a, b in scored_pairs[:8]:
            ordered = (a, b) if a["count"] <= b["count"] else (b, a)
            for c in ordered:
                p = (c["cx"], c["cy"])
                if p not in seen:
                    coords.append(p)
                    seen.add(p)
        return coords[:16]

    def _detect_visual_centers(self, latest_frame: FrameData) -> list[tuple[int, int]]:
        comps = self._connected_components(latest_frame)
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

    def _next_coord(self) -> tuple[int, int]:
        if self.pair_coord_candidates and self.coord_index % 2 == 0:
            pool = self.pair_coord_candidates
        else:
            pool = self.dynamic_coord_candidates if self.dynamic_coord_candidates else self.coord_candidates
        coord = pool[self.coord_index % len(pool)]
        self.coord_index += 1
        return coord

    def _trim_memory(self) -> None:
        if len(self.state_memory) <= self.MEMORY_LIMIT:
            return
        ordered = sorted(self.state_hits.items(), key=lambda kv: kv[1])
        for key, _ in ordered[: max(1, len(ordered) - self.MEMORY_LIMIT)]:
            self.state_memory.pop(key, None)
            self.sequence_memory.pop(key, None)
            self.plan_memory.pop(key, None)
            self.state_hits.pop(key, None)

    def _update_dict_score(self, dct: dict, key, delta: float) -> None:
        dct[key] = dct.get(key, 0.0) + delta

    def _update_state_memory(self, memory_key: str | None, action_key: str | None, reward_delta: float) -> None:
        if memory_key is None or action_key is None:
            return
        if memory_key not in self.state_memory:
            self.state_memory[memory_key] = {}
        self._update_dict_score(self.state_memory[memory_key], action_key, reward_delta)
        self.state_hits[memory_key] = self.state_hits.get(memory_key, 0) + 1
        self._trim_memory()

    def _update_sequence_memory(self, reward_delta: float) -> None:
        if len(self.recent_contexts) < 2:
            return
        max_len = min(self.SEQUENCE_MAX_LEN, len(self.recent_contexts))
        for length in range(2, max_len + 1):
            window = self.recent_contexts[-length:]
            start_state = window[0][0]
            seq = tuple(action_key for _, action_key in window)
            if start_state not in self.sequence_memory:
                self.sequence_memory[start_state] = {}
            self._update_dict_score(self.sequence_memory[start_state], seq, reward_delta / float(length))

    def _finalize_active_plan_if_needed(self) -> None:
        if self.active_plan or self.active_plan_tuple is None or self.active_plan_origin_key is None:
            return
        if self.active_plan_origin_key not in self.plan_memory:
            self.plan_memory[self.active_plan_origin_key] = {}
        self._update_dict_score(
            self.plan_memory[self.active_plan_origin_key],
            self.active_plan_tuple,
            self.active_plan_reward_accum,
        )
        self.active_plan_tuple = None
        self.active_plan_origin_key = None
        self.active_plan_reward_accum = 0.0

    def _register_previous_outcome(self, latest_frame: FrameData) -> tuple[str, str]:
        signature = self._frame_signature(latest_frame)
        memory_key = self._memory_key_from_signature(signature)
        score_now = self._score_value(latest_frame)

        changed = self.last_signature is not None and signature != self.last_signature
        score_delta = score_now - self.last_score
        score_improved = score_now > self.best_score_seen

        structural_delta = 0.0
        if str(self.game_id).startswith("sk48"):
            struct_now = self._structural_value(latest_frame)
            if self.last_structural_value is not None:
                structural_delta = struct_now - self.last_structural_value
            self.last_structural_value = struct_now

        reward_delta = 0.0
        if changed:
            reward_delta += 1.0
        else:
            reward_delta -= 0.45
        if score_delta > 0:
            reward_delta += 15.0 * score_delta
        elif score_improved:
            reward_delta += 10.0
        if structural_delta > 0:
            reward_delta += min(5.0, structural_delta * 0.08)
        elif structural_delta < 0:
            reward_delta -= min(2.0, abs(structural_delta) * 0.035)
        if self.same_frame_count >= 2:
            reward_delta -= 0.10

        if self.last_action_key is not None:
            self.action_counts[self.last_action_key] = self.action_counts.get(self.last_action_key, 0) + 1
            if not changed:
                self.action_nochange[self.last_action_key] = self.action_nochange.get(self.last_action_key, 0) + 1
            self.action_scores[self.last_action_key] = self.action_scores.get(self.last_action_key, 0.0) + reward_delta
            self._update_state_memory(self.last_memory_key, self.last_action_key, reward_delta)
            self._update_sequence_memory(reward_delta)
            if self.active_plan_tuple is not None:
                self.active_plan_reward_accum += reward_delta

        if signature == self.last_signature:
            self.same_frame_count += 1
        else:
            self.same_frame_count = 0

        self.last_signature = signature
        self.last_score = score_now
        if score_now > self.best_score_seen:
            self.best_score_seen = score_now

        self._finalize_active_plan_if_needed()
        return signature, memory_key

    def _candidate_actions(self, ids: set[int]) -> list[GameAction]:
        order = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]
        return [a for a in order if self._is_available(a, ids)]

    def _valid_plan(self, plan: tuple[str, ...], ids: set[int]) -> bool:
        for key in plan:
            action = self._action_from_key(key)
            if action is None or not self._is_available(action, ids):
                return False
        return True

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

    def _build_candidate_plans(self, ids: set[int], memory_key: str) -> list[tuple[str, ...]]:
        plans: list[tuple[str, ...]] = []

        for plan, value in sorted(self.plan_memory.get(memory_key, {}).items(), key=lambda kv: kv[1], reverse=True)[:5]:
            if value > 0 and self._valid_plan(plan, ids):
                plans.append(plan)

        for plan in self.sk48_seed_plans:
            if self._valid_plan(plan, ids):
                plans.append(plan)

        ranked_actions = self._rank_actions(ids, memory_key)
        top_keys = [self._key_for_action(a) for a in ranked_actions[:4]]
        if len(top_keys) >= 2:
            plans.append(tuple(top_keys[:2]))
        if len(top_keys) >= 3:
            plans.append(tuple(top_keys[:3]))

        if self._is_available(GameAction.ACTION6, ids):
            for a in top_keys[:3]:
                plans.append((a, "6:complex"))
                plans.append(("6:complex", a))

        seen = set()
        unique = []
        for p in plans:
            if 1 <= len(p) <= self.PLAN_MAX_LEN and p not in seen and self._valid_plan(p, ids):
                unique.append(p)
                seen.add(p)
        return unique[:12]

    def _select_plan(self, ids: set[int], memory_key: str) -> tuple[str, ...] | None:
        plans = self._build_candidate_plans(ids, memory_key)
        if not plans:
            return None

        def value(plan: tuple[str, ...]) -> float:
            memory_value = self.plan_memory.get(memory_key, {}).get(plan, 0.0)
            action_value = sum(self.action_scores.get(k, 0.0) for k in plan) / max(1, len(plan))
            length_penalty = 0.08 * len(plan)
            complex_bonus = 0.35 if "6:complex" in plan else 0.0
            novelty = 0.15 if memory_value == 0 else 0.0
            return memory_value * 2.0 + action_value + complex_bonus + novelty - length_penalty

        ranked = sorted(plans, key=value, reverse=True)
        if random.random() < 0.72:
            return ranked[0]
        return random.choice(ranked[: min(4, len(ranked))])

    def _start_plan(self, plan: tuple[str, ...], memory_key: str) -> None:
        self.active_plan = list(plan)
        self.active_plan_origin_key = memory_key
        self.active_plan_tuple = plan
        self.active_plan_reward_accum = 0.0

    def _pop_plan_action(self, ids: set[int]) -> GameAction | None:
        while self.active_plan:
            key = self.active_plan.pop(0)
            action = self._action_from_key(key)
            if action is None or not self._is_available(action, ids):
                continue
            return action
        return None

    def _prepare_complex_action(self, action: GameAction) -> GameAction:
        if action.is_complex():
            x, y = self._next_coord()
            action.set_data({"x": int(x), "y": int(y)})
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "Sequence planner selected complex action with structural target coordinate.",
            }
        else:
            action.reasoning = f"Sequence planner selected action {action.value}."
        return action

    def _record_chosen_action(self, memory_key: str, action: GameAction) -> None:
        self.last_action_key = self._key_for_action(action)
        self.last_memory_key = memory_key
        self.recent_actions.append(self.last_action_key)
        self.recent_actions = self.recent_actions[-10:]
        self.recent_contexts.append((memory_key, self.last_action_key))
        self.recent_contexts = self.recent_contexts[-8:]

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return any([
            latest_frame.state is GameState.WIN,
            self.action_counter >= self.MAX_ACTIONS,
        ])

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            self.active_plan = []
            self.active_plan_tuple = None
            self.active_plan_origin_key = None
            action = GameAction.RESET
            action.reasoning = "Reset because game is not started or game over."
            return action

        _, memory_key = self._register_previous_outcome(latest_frame)
        ids = self._available_action_ids(latest_frame)
        self._refresh_dynamic_coords(latest_frame)

        action = self._pop_plan_action(ids)
        if action is not None:
            action = self._prepare_complex_action(action)
            self._record_chosen_action(memory_key, action)
            return action

        if str(self.game_id).startswith("sk48"):
            plan = self._select_plan(ids, memory_key)
            if plan is not None:
                self._start_plan(plan, memory_key)
                action = self._pop_plan_action(ids)
                if action is not None:
                    action = self._prepare_complex_action(action)
                    self._record_chosen_action(memory_key, action)
                    return action

        ranked = self._rank_actions(ids, memory_key)
        if ranked:
            action = ranked[0] if random.random() < 0.75 else random.choice(ranked[: min(3, len(ranked))])
            action = self._prepare_complex_action(action)
            self._record_chosen_action(memory_key, action)
            return action

        action = GameAction.RESET
        action.reasoning = "Fallback reset from sequence planner."
        return action
