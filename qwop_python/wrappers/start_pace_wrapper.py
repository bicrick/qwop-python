"""
Start-pace reward shaping for sim→browser transfer fine-tunes.

After settle_spawn, most of the Python→browser gap is in the first ~10 m.
This wrapper densifies early forward progress and bonuses a fast 10 m split,
while punishing faceplants before the focus mark.
"""

from __future__ import annotations

import gymnasium as gymnasium


class StartPaceWrapper(gymnasium.Wrapper):
    """
    Shape reward for the opening metres of a race.

    While ``distance < focus_m``:
      reward += progress_mult * delta_distance

    On the first step that crosses ``focus_m``:
      reward += max(0, (split_ref_s - t) * split_bonus_scale)

    If the episode ends fallen before ``focus_m``:
      reward -= early_fail_cost

    After focus, progress uses ``post_focus_progress_mult`` (default 0).

    Defaults match the farm start-pace fine-tune:
      focus_m=10, progress_mult=4, split_ref_s=12, split_bonus_scale=1.5,
      early_fail_cost=10, post_focus_progress_mult=0
    """

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

        self._last_distance = 0.0
        self._reached_focus = False

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._last_distance = float(info.get("distance", 0.0))
        self._reached_focus = self._last_distance >= self.focus_m
        info = dict(info)
        self._write_info(
            info,
            progress_bonus=0.0,
            split_bonus=0.0,
            early_fail_penalty=0.0,
            delta_distance=0.0,
        )
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        info = dict(info)

        distance = float(info.get("distance", 0.0))
        t = float(info.get("time", 0.0))
        delta_distance = distance - self._last_distance

        progress_bonus = 0.0
        split_bonus = 0.0
        early_fail_penalty = 0.0

        if distance < self.focus_m:
            progress_bonus = self.progress_mult * delta_distance
        else:
            if not self._reached_focus:
                # First cross of focus_m this episode.
                split_bonus = max(
                    0.0, (self.split_ref_s - t) * self.split_bonus_scale
                )
                self._reached_focus = True
            progress_bonus = self.post_focus_progress_mult * delta_distance

        if (
            (terminated or truncated)
            and distance < self.focus_m
            and bool(info.get("fallen", False))
        ):
            early_fail_penalty = -self.early_fail_cost

        shaped = reward + progress_bonus + split_bonus + early_fail_penalty
        self._write_info(
            info,
            progress_bonus=progress_bonus,
            split_bonus=split_bonus,
            early_fail_penalty=early_fail_penalty,
            delta_distance=delta_distance,
        )
        self._last_distance = distance
        return obs, shaped, terminated, truncated, info

    def _write_info(
        self,
        info: dict,
        *,
        progress_bonus: float,
        split_bonus: float,
        early_fail_penalty: float,
        delta_distance: float,
    ) -> None:
        shaping = {
            "progress_bonus": float(progress_bonus),
            "split_bonus": float(split_bonus),
            "early_fail_penalty": float(early_fail_penalty),
            "delta_distance": float(delta_distance),
            "reached_focus": bool(self._reached_focus),
            "focus_m": self.focus_m,
            "progress_mult": self.progress_mult,
            "post_focus_progress_mult": self.post_focus_progress_mult,
            "split_ref_s": self.split_ref_s,
            "split_bonus_scale": self.split_bonus_scale,
            "early_fail_cost": self.early_fail_cost,
        }
        info["start_pace"] = shaping
        if "shaped_rewards" not in info:
            info["shaped_rewards"] = {}
        info["shaped_rewards"]["start_pace_progress"] = shaping["progress_bonus"]
        info["shaped_rewards"]["start_pace_split"] = shaping["split_bonus"]
        info["shaped_rewards"]["start_pace_early_fail"] = shaping[
            "early_fail_penalty"
        ]
