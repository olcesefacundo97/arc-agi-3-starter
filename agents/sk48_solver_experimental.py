from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CandidateSequence:
    actions: list[str]
    score: float
    notes: str = ""


class Sk48Solver:
    """
    Experimental solver skeleton for the sk48 environment.

    Goal:
    - stop relying on generic black-box heuristics
    - move toward a solver guided by the environment's internal logic

    This file is intentionally a scaffold, not a finished solver.
    """

    def __init__(self) -> None:
        self.best_sequences: list[CandidateSequence] = []

    def extract_clickable_nodes_from_level(self, level: Any) -> list[Any]:
        """
        Placeholder: extract clickable nodes / endpoints from the level.
        Expected future source in sk48.py:
        - sprites tagged with `epdquznwmq`
        """
        return []

    def extract_pairs_from_runtime(self, env: Any) -> dict[Any, Any]:
        """
        Placeholder: extract equivalent node pairs.
        Expected future source in sk48.py:
        - env.xpmcmtbcv
        """
        return {}

    def score_matching_progress(self, env: Any) -> float:
        """
        Placeholder scoring function.

        Future direction:
        - approximate progress toward env.gvtmoopqgy() == True
        - compare color-aligned segments between paired nodes
        - use structural matching, not reward or changed_pixels alone
        """
        return 0.0

    def enumerate_candidate_sequences(self) -> list[list[str]]:
        """
        Initial small candidate library.
        These are symbolic actions for now.
        """
        return [
            ["ACTION1", "ACTION4"],
            ["ACTION1", "ACTION4", "ACTION4"],
            ["ACTION4", "ACTION1", "ACTION4"],
            ["ACTION1", "ACTION4", "ACTION1"],
            ["ACTION4", "ACTION1", "ACTION1"],
        ]

    def simulate_short_sequence(self, env: Any, actions: list[str]) -> CandidateSequence:
        """
        Placeholder simulation entry point.

        Future versions should:
        - run a sequence against a safe copy or reproducible reset of the environment
        - evaluate structural matching after the sequence
        - support rollback / replay
        """
        return CandidateSequence(actions=actions, score=0.0, notes="not implemented")

    def search_best_local_sequence(self, env: Any) -> CandidateSequence | None:
        candidates = []
        for seq in self.enumerate_candidate_sequences():
            candidate = self.simulate_short_sequence(env, seq)
            candidates.append(candidate)

        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.score)
        self.best_sequences.append(best)
        return best


if __name__ == "__main__":
    solver = Sk48Solver()
    print("Sk48Solver scaffold ready")
    print("Initial candidate library:")
    for seq in solver.enumerate_candidate_sequences():
        print(" - ", seq)
