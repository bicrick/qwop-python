"""
Gymnasium environment wrapper for qwop-python.

Matches qwop-wr interface so trained models (DQNfD, QRDQN, etc.) can run
against the Python physics implementation.
"""

import sys
import os

# Ensure src is on path when used as standalone
_src = os.path.dirname(os.path.abspath(__file__))
if _src not in sys.path:
    sys.path.insert(0, _src)

import gymnasium as gym
import numpy as np

from game import QWOPGame
from physics import PhysicsWorld
from observation import extract_raw, normalize

DTYPE = np.float32


# Import from scripts when available (for action bridge)
def _get_scripts_path():
    scripts = os.path.join(os.path.dirname(_src), "scripts")
    return scripts


class QWOPPythonEnv(gym.Env):
    """
    Gymnasium env for qwop-python with same interface as qwop-wr QwopEnv.

    Uses frameskip=4 and reduced action set (9 actions) to match DQNfD training.
    Observation: 60 floats normalized to [-1, 1] (12 bodies x 5: pos_x, pos_y, angle, vel_x, vel_y)
    Action: Discrete(9) for reduced set (none, Q, W, O, P, QW, QP, WO, OP)
    """

    metadata = {"render_modes": [], "render_fps": 30}

    # Match qwop-wr / DQNfD training config
    DEFAULT_FRAMES_PER_STEP = 4
    DEFAULT_REDUCED_ACTION_SET = True

    def __init__(
        self,
        frames_per_step=None,
        reduced_action_set=None,
        speed_rew_mult=0.01,
        time_cost_mult=10,
        failure_cost=10,
        success_reward=50,
        seed=None,
    ):
        super().__init__()
        self.frames_per_step = (
            frames_per_step
            if frames_per_step is not None
            else self.DEFAULT_FRAMES_PER_STEP
        )
        self.reduced_action_set = (
            reduced_action_set
            if reduced_action_set is not None
            else self.DEFAULT_REDUCED_ACTION_SET
        )
        self.speed_rew_mult = DTYPE(speed_rew_mult)
        self.time_cost_mult = DTYPE(time_cost_mult)
        self.failure_cost = DTYPE(failure_cost)
        self.success_reward = DTYPE(success_reward)
        self.seedval = int(seed) if seed is not None else 42

        self.observation_space = gym.spaces.Box(
            shape=(60,), low=-1, high=1, dtype=DTYPE
        )
        self._build_action_space()

        self._game = None
        self._last_distance = 0.0
        self._last_time = 0.0
        self._total_reward = DTYPE(0)
        self._keys_prev = frozenset()

        # Lazy import for scripts (avoid circular deps)
        self._action_mod = None

    def _get_action_mod(self):
        if self._action_mod is None:
            scripts = _get_scripts_path()
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            from action_bridge import action_to_keys, apply_keys_to_controls
            self._action_keys = action_to_keys
            self._apply_keys = apply_keys_to_controls
            self._action_mod = True
        return self._action_keys, self._apply_keys

    def _build_action_space(self):
        import itertools
        import functools
        keyflags = [0b10, 0b100, 0b1000, 0b10000]  # Q,W,O,P
        combos = (
            list(itertools.combinations(keyflags, 0))
            + list(itertools.combinations(keyflags, 1))
            + list(itertools.combinations(keyflags, 2))
            + list(itertools.combinations(keyflags, 3))
            + list(itertools.combinations(keyflags, 4))
        )
        if self.reduced_action_set:
            redundant = [
                (0b10, 0b1000), (0b100, 0b10000),
                (0b10, 0b100, 0b1000), (0b10, 0b100, 0b10000),
                (0b10, 0b1000, 0b10000), (0b100, 0b1000, 0b10000),
                (0b10, 0b100, 0b1000, 0b10000),
            ]
            combos = [c for c in combos if c not in redundant]
        self._n_actions = len(combos)
        self.action_space = gym.spaces.Discrete(self._n_actions)

    def _ensure_game(self):
        if self._game is None:
            import builtins
            _print = builtins.print
            builtins.print = lambda *a, **k: None
            try:
                self._game = QWOPGame()
                self._game.initialize()
                self._game.start()
            finally:
                builtins.print = _print

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.seedval = int(seed)
        self._ensure_game()
        import builtins
        _print = builtins.print
        builtins.print = lambda *a, **k: None
        try:
            self._game.reset()
        finally:
            builtins.print = _print
        self._last_distance = 0.0
        self._last_time = 0.0
        self._total_reward = DTYPE(0)
        self._keys_prev = frozenset()

        raw = extract_raw(self._game.physics)
        torso = self._game.physics.get_body("torso")
        dist = (torso.position[0] * 10.0) / 10.0 if torso else 0.0  # meters, dist = pos/10 in ref units
        self._last_distance = dist
        self._last_time = self._game.score_time

        obs = normalize(raw)
        info = {
            "time": self._game.score_time,
            "distance": dist,
            "avgspeed": dist / self._game.score_time if self._game.score_time > 0 else 0,
            "is_success": False,
        }
        return obs, info

    def step(self, action):
        action_to_keys, apply_keys = self._get_action_mod()
        dt = 1.0 / 30.0

        keys_now = action_to_keys(action, reduced=self.reduced_action_set)
        apply_keys(self._game.controls, self._keys_prev, keys_now)
        self._keys_prev = keys_now

        for _ in range(self.frames_per_step):
            self._game.update(dt)
            if self._game.game_state.game_ended:
                break

        raw = extract_raw(self._game.physics)
        torso = self._game.physics.get_body("torso")
        dist = torso.position[0] if torso else 0.0  # meters (game score)
        time_now = self._game.score_time
        done = self._game.game_state.game_ended
        success = self._game.game_state.jump_landed and not self._game.game_state.fallen

        ds = dist - self._last_distance
        dt_step = time_now - self._last_time
        v = ds / dt_step if dt_step > 0 else 0
        rew = v * self.speed_rew_mult - dt_step * self.time_cost_mult / self.frames_per_step
        if done:
            if success or dist > 100:
                rew += self.success_reward
            else:
                rew -= self.failure_cost

        self._last_distance = dist
        self._last_time = time_now
        self._total_reward += rew

        obs = normalize(raw)
        info = {
            "time": time_now,
            "distance": dist,
            "avgspeed": dist / time_now if time_now > 0 else 0,
            "is_success": success or dist > 100,
        }
        return obs, rew, done, False, info

    def close(self):
        self._game = None
