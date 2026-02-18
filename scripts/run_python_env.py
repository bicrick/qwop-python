"""
Headless runner for qwop-python game.

Runs the Python QWOP env without display, applying a given action trace
and yielding (state_60, score, game_over) per step.
"""

import sys
import os

# Add project root and scripts for imports
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_extractor import extract_state
from action_bridge import action_to_keys, apply_keys_to_controls

# Suppress game initialization prints when running headless
_ORIGINAL_PRINT = print
def _quiet_print(*args, **kwargs):
    pass

def run_python_env(actions, reduced=True, frames_per_step=4, quiet=True):
    """
    Run qwop-python with given action trace.

    Args:
        actions: List of discrete action indices (0..8 reduced, 0..15 full).
        reduced: Use reduced action set (default True).
        frames_per_step: Physics steps per trace action (default 4, matches training).
        quiet: Suppress initialization prints (default True).

    Yields:
        (state_60, score, game_over) per step (one per trace action).
        state_60: np.ndarray (60,) float32 raw observation.
        score: float, torso x / 10.
        game_over: bool.
    """
    if quiet:
        import builtins
        builtins.print = _quiet_print

    try:
        from game import QWOPGame

        game = QWOPGame()
        game.initialize()
        game.start()

        keys_prev = frozenset()
        dt = 1.0 / 30.0  # ~30 FPS to match reference timing

        for step_idx, action in enumerate(actions):
            keys_now = action_to_keys(action, reduced=reduced)
            apply_keys_to_controls(game.controls, keys_prev, keys_now)
            keys_prev = keys_now

            for _ in range(frames_per_step):
                game.update(dt)
                if game.game_state.game_ended:
                    break

            state = extract_state(game.physics)
            torso = game.physics.get_body("torso")
            # Distance in meters (our physics uses m; ref uses dm so pos/10=m)
            score = torso.position[0] if torso else 0.0
            game_over = game.game_state.game_ended

            yield state, score, game_over
            if game_over:
                break
    finally:
        if quiet:
            import builtins
            builtins.print = _ORIGINAL_PRINT
