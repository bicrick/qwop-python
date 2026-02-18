"""
Run qwop-wr (reference) environment and yield raw state for comparison.

Requires qwop-wr repo to be importable. Set QWOP_WR_PATH or add it to PYTHONPATH.
Browser and chromedriver paths: CHROME_PATH, CHROMEDRIVER_PATH, or config/env.yml.
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))

# Add qwop-wr for QwopEnv import
_qwop_wr = os.environ.get("QWOP_WR_PATH", "/Users/b407404/Desktop/Misc/qwop-wr")
if os.path.isdir(_qwop_wr):
    sys.path.insert(0, _qwop_wr)
else:
    # Assume qwop-wr is installed or on path
    pass


def _get_browser_driver():
    """Resolve browser and driver paths from env or config."""
    browser = os.environ.get("CHROME_PATH") or os.environ.get("BROWSER_PATH")
    driver = os.environ.get("CHROMEDRIVER_PATH") or os.environ.get("DRIVER_PATH")
    if not browser or not driver:
        try:
            import yaml
            cfg_path = os.path.join(_qwop_wr, "config", "env.yml")
            if os.path.isfile(cfg_path):
                with open(cfg_path) as f:
                    cfg = yaml.safe_load(f)
                browser = browser or cfg.get("browser")
                driver = driver or cfg.get("driver")
        except Exception:
            pass
    return browser, driver


def run_reference_env(actions, seed=42, reduced=True, frames_per_step=4, quiet=True):
    """
    Run qwop-wr QwopEnv with given action trace.

    Args:
        actions: List of discrete action indices.
        seed: Reset seed for reproducibility.
        reduced: Use reduced action set (default True).
        frames_per_step: Physics steps per env.step (default 4, matches training).
        quiet: Suppress env init logs (default True).

    Yields:
        (state_60, score, game_over) per step.
        state_60: np.ndarray (60,) float32 raw observation.
        score: float, distance (torso x / 10).
        game_over: bool.
    """
    browser, driver = _get_browser_driver()
    if not browser or not driver:
        raise RuntimeError(
            "Browser and chromedriver required. Set CHROME_PATH and "
            "CHROMEDRIVER_PATH, or QWOP_WR_PATH with config/env.yml"
        )

    from qwop_gym.envs.v1.qwop_env import QwopEnv

    class RawObsQwopEnv(QwopEnv):
        """Expose raw observation (reaction.data) after each step."""

        def step(self, action):
            self.steps += 1
            reaction = self._perform_action(action)
            reward = self._calc_reward(reaction, self.last_reaction)
            terminated = reaction.game_over or action == getattr(
                self, "action_t", None
            )
            info = self._build_info(reaction)
            self.last_reward = reward
            self.total_reward += reward
            self.last_reaction = reaction
            self._last_raw_obs = reaction.data.copy()
            return reaction.ndata, reward, terminated, False, info

    env_kwargs = {
        "browser": browser,
        "driver": driver,
        "frames_per_step": frames_per_step,
        "reduced_action_set": reduced,
        "auto_draw": False,
        "stat_in_browser": False,
        "game_in_browser": False,
        "seed": seed,
    }

    env = RawObsQwopEnv(**env_kwargs)

    try:
        env.reset(seed=seed)
        for action in actions:
            _, _, terminated, _, info = env.step(action)
            state = env._last_raw_obs.copy()
            score = info["distance"]
            game_over = terminated
            yield state, score, game_over
            if game_over:
                break
    finally:
        env.close()
