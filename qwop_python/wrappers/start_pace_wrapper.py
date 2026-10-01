"""Shape the opening 10m under settle_spawn: speed + fast split + early-fall cost.

Mid-race already transfers Python→browser. After settle, the hole is post-plant
acceleration (browser PB ~8.8s to 10m vs settle-OFF Python ~6.8s). This wrapper
keeps the base gait reward but:
  - pays denser forward progress while distance < focus_m
  - pays a bonus when crossing focus_m that grows as split time drops
  - adds an extra terminal cost if fallen before focus_m

Does not change friction or disable settle — pair with settle_spawn=true.
"""

from __future__ import annotations

import gymnasium as gym


class StartPaceWrapper(gym.Wrapper):
    def __init__(
        self,
        env,
        focus_m: float = 10.0,
        progress_mult: float = 4.0,
        split_ref_s: float = 12.0,
        split_bonus_scale: float = 1.5,
        early_fail_cost: float = 10.0,
        post_focus_progress_mult: float = 0.0,
    ):
        super().__init__(env)
        self.focus_m = float(focus_m)
        self.progress_mult = float(progress_mult)
        self.split_ref_s = float(split_ref_s)
        self.split_bonus_scale = float(split_bonus_scale)
        self.early_fail_cost = float(early_fail_cost)
        self.post_focus_progress_mult = float(post_focus_progress_mult)
        self._last_dist = 0.0
        self._hit_focus = False
        self._split_bonus_paid = 0.0

    def reset(self, **kwargs):
        self._last_dist = 0.0
        self._hit_focus = False
        self._split_bonus_paid = 0.0
        obs, info = self.env.reset(**kwargs)
        self._last_dist = self._distance(info)
        return obs, info

    def _distance(self, info) -> float:
        for key in ("distance", "score", "meters"):
            if key in info and info[key] is not None:
                try:
                    return float(info[key])
                except (TypeError, ValueError):
                    pass
        game = getattr(self.env.unwrapped, "game", None)
        if game is not None and hasattr(game, "game_state"):
            return float(getattr(game.game_state, "score", 0.0) or 0.0)
        return 0.0

    def _time(self, info) -> float:
        for key in ("time", "score_time", "hud_s"):
            if key in info and info[key] is not None:
                try:
                    return float(info[key])
                except (TypeError, ValueError):
                    pass
        game = getattr(self.env.unwrapped, "game", None)
        if game is not None:
            return float(getattr(game, "score_time", 0.0) or 0.0)
        return 0.0

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        dist = self._distance(info)
        t = self._time(info)
        dd = max(0.0, dist - self._last_dist)
        self._last_dist = dist

        progress = 0.0
        if dist < self.focus_m:
            progress = self.progress_mult * dd
        elif self.post_focus_progress_mult:
            progress = self.post_focus_progress_mult * dd

        split_bonus = 0.0
        if not self._hit_focus and dist >= self.focus_m:
            self._hit_focus = True
            # Faster split → larger bonus. At ref time bonus≈0; below ref grows.
            split_bonus = max(0.0, (self.split_ref_s - t) * self.split_bonus_scale)
            self._split_bonus_paid = split_bonus

        early_pen = 0.0
        if (terminated or truncated) and dist < self.focus_m:
            success = bool(info.get("success") or info.get("is_success"))
            if not success:
                early_pen = -self.early_fail_cost

        shaped = float(reward) + progress + split_bonus + early_pen
        info = dict(info)
        info["start_pace_progress"] = progress
        info["start_pace_split_bonus"] = split_bonus
        info["start_pace_early_pen"] = early_pen
        info["start_pace_focus_hit"] = self._hit_focus
        if self._hit_focus:
            info["start_pace_split_s"] = t if split_bonus else info.get("split_10m_time", t)
        return obs, shaped, terminated, truncated, info
