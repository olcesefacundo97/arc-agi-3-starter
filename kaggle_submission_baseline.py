import os

import pandas as pd
import arc_agi
from arc_agi.base import OperationMode
from arcengine import GameAction


ENV_DIR = "/kaggle/input/competitions/arc-prize-2026-arc-agi-3/environment_files"
MAX_GAMES = 25
MAX_STEPS = 200


class BaselineAgent:
    def __init__(self):
        # ligera mejora sin romper estabilidad
        self.actions = [
            GameAction.ACTION1,
            GameAction.ACTION1,
            GameAction.ACTION2,
            GameAction.ACTION2,
            GameAction.ACTION3,
        ]

    def act(self, step: int):
        return self.actions[step % len(self.actions)]


arc = arc_agi.Arcade(
    operation_mode=OperationMode.OFFLINE,
    environments_dir=ENV_DIR,
)


def run_game(game_id: str, max_steps: int = MAX_STEPS):
    env = arc.make(game_id, render_mode=None)
    agent = BaselineAgent()

    frame = env.step(GameAction.RESET)

    last_state = None
    same_count = 0
    step = 0

    for step in range(max_steps):
        if step % 50 == 0 and step > 0:
            frame = env.step(GameAction.RESET)

        action = agent.act(step)
        frame = env.step(action)

        try:
            current_state = str(frame.frame)
        except Exception:
            current_state = None

        if current_state == last_state:
            same_count += 1
        else:
            same_count = 0

        last_state = current_state

        if same_count > 10:
            break

        if frame.state.name in ["WIN", "GAME_OVER"]:
            break

    return {
        "game_id": game_id,
        "steps": step,
        "state": frame.state.name,
        "score": getattr(frame, "levels_completed", 0),
    }


def run_all_games(limit: int = MAX_GAMES):
    results = []

    for env_info in arc.available_environments[:limit]:
        try:
            results.append(run_game(env_info.game_id))
        except Exception as e:
            results.append({
                "game_id": env_info.game_id,
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    results = run_all_games()

    df = pd.DataFrame(results)
    output_path = "/kaggle/working/submission.parquet"
    df.to_parquet(output_path, index=False)

    print("submission.parquet generated")
    print("Exists:", os.path.exists(output_path))
    print("Size:", os.path.getsize(output_path))
    print(df.head())
