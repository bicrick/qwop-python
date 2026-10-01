"""Reward bonuses for clearing the opening meters; extra cost for early faceplants.

Browser hunt deaths are ~75% before 10s / under ~5–10m. This wrapper keeps the
base gait reward but pays milestone bonuses and an extra terminal penalty when
the episode ends fallen short of early_fail_m.
"""

from __future__ import annotations

import gymnasium as gym


class EarlySurvivalWrapper(gym.Wrapper):
    def __init__(
        self,
        env,
        milestones_m=(5.0, 10.0, 20.0),
        milestone_bonus=2.0,
        early_fail_m=10.0,
        early_fail_cost=8.0,
    ):
        super().__init__(env)
        self.milestones_m = tuple(float(x) for x in milestones_m)
        self.milestone_bonus = float(milestone_bonus)
        self.early_fail_m = float(early_fail_m)
        self.early_fail_cost = float(early_fail_cost)
        self._hit = set()

    def reset(self, **kwargs):
        self._hit = set()
        return self.env.reset(**kwargs)

    def _distance(self, info) -> float:
        for key in ("distance", "score", "meters"):
            if key in info and info[key] is not None:
                try:
                    return float(info[key])
                except (TypeError, ValueError):
                    pass
        # Fall back to unwrapped game state when present.
        game = getattr(self.env.unwrapped, "game", None)
        if game is not None and hasattr(game, "game_state"):
            return float(getattr(game.game_state, "score", 0.0) or 0.0)
        return 0.0

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        dist = self._distance(info)
        bonus = 0.0
        for m in self.milestones_m:
            if m not in self._hit and dist >= m:
                self._hit.add(m)
                bonus += self.milestone_bonus
        early_pen = 0.0
        if (terminated or truncated) and dist < self.early_fail_m:
            # Only punish real falls / short ends, not a successful finish.
            success = bool(info.get("success") or info.get("is_success"))
            if not success:
                early_pen = -self.early_fail_cost
        shaped = float(reward) + bonus + early_pen
        info = dict(info)
        info["early_survival_bonus"] = bonus
        info["early_survival_penalty"] = early_pen
        info["early_survival_dist"] = dist
        return obs, shaped, terminated, truncated, info
