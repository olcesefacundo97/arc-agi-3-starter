import json

import arc_agi
from arc_agi.base import OperationMode
from arcengine import GameAction


ENV_DIR = "/kaggle/input/competitions/arc-prize-2026-arc-agi-3/environment_files"
MAX_GAMES = 25
MAX_STEPS = 200


class BaselineAgent:
    def __init__(self):
        self.actions = [
            GameAction.ACTION1,
            GameAction.ACTION2,
            GameAction.ACTION3,
            GameAction.ACTION4,
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

    step = 0
    for step in range(max_steps):
        action = agent.act(step)
        frame = env.step(action)

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

    with open("/kaggle/working/submission.json", "w") as f:
        json.dump(results, f)

    print("submission.json generated")
    print(results[:5])
