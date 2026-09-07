"""
Stuck / belly-slide termination wrapper.

Original QWOP JS does NOT treat torso–track contact as a fall — only head,
arms, and forearms (see doc/reference/QWOP_FUNCTIONS_EXACT.md). Belly-slide
crawls therefore never terminate via fall detection and can burn
max_episode_steps.

This optional wrapper ends the episode as a failure when progress stalls
(low speed and flat distance for N steps). Disabled unless added via
env_wrappers in config — existing training configs are unchanged.
"""

import gymnasium as gymnasium


class StuckDetectionWrapper(gymnasium.Wrapper):
    """
    Terminate as failure when the runner is effectively stuck.

    Checks each step after the base env step. When both:
      - |speed| < min_speed_mps (prefers info['speed_mps'], else Δdistance/Δtime)
      - distance gained over the patience window < flat_distance_m
    for ``patience_steps`` consecutive env steps, the episode terminates
    with info['stuck']=True and is_success=0.

    Args:
        env: Wrapped QWOP env
        patience_steps: Consecutive stuck steps required (default: 100)
        min_speed_mps: Speed below this counts as "low velocity" (default: 0.05)
        flat_distance_m: Max metres gained over the patience window (default: 0.5)
        failure_cost: Extra reward penalty on stuck termination (default: None →
            use unwrapped.failure_cost if present, else 10.0)
    """

    def __init__(
        self,
        env,
        patience_steps=100,
        min_speed_mps=0.05,
        flat_distance_m=0.5,
        failure_cost=None,
    ):
        super().__init__(env)
        self.patience_steps = int(patience_steps)
        self.min_speed_mps = float(min_speed_mps)
        self.flat_distance_m = float(flat_distance_m)
        if failure_cost is None:
            failure_cost = getattr(env.unwrapped, "failure_cost", 10.0)
        self.failure_cost = float(failure_cost)

        self._stuck_steps = 0
        self._window_start_distance = None
        self._last_distance = 0.0
        self._last_time = 0.0

    def reset(self, **kwargs):
        self._stuck_steps = 0
        self._window_start_distance = None
        obs, info = self.env.reset(**kwargs)
        self._last_distance = float(info.get("distance", 0.0))
        self._last_time = float(info.get("time", 0.0))
        self._window_start_distance = self._last_distance
        info = dict(info)
        info.setdefault("stuck", False)
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        info = dict(info)
        info.setdefault("stuck", False)

        if terminated or truncated:
            self._stuck_steps = 0
            self._window_start_distance = float(info.get("distance", 0.0))
            self._last_distance = self._window_start_distance
            self._last_time = float(info.get("time", 0.0))
            return obs, reward, terminated, truncated, info

        distance = float(info.get("distance", 0.0))
        time_val = float(info.get("time", 0.0))
        speed = info.get("speed_mps")
        if speed is None:
            dt = max(time_val - self._last_time, 1e-8)
            speed = (distance - self._last_distance) / dt
        speed = float(speed)

        if self._window_start_distance is None:
            self._window_start_distance = distance

        low_speed = abs(speed) < self.min_speed_mps
        if low_speed:
            self._stuck_steps += 1
        else:
            self._stuck_steps = 0
            self._window_start_distance = distance

        stuck = False
        if self._stuck_steps >= self.patience_steps:
            gained = distance - self._window_start_distance
            if abs(gained) < self.flat_distance_m:
                stuck = True

        self._last_distance = distance
        self._last_time = time_val

        if stuck:
            terminated = True
            reward = float(reward) - self.failure_cost
            info["stuck"] = True
            info["is_success"] = 0.0
            info["fallen"] = info.get("fallen", False)
            self._stuck_steps = 0
            self._window_start_distance = distance

        return obs, reward, terminated, truncated, info
