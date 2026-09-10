"""Smoke tests for spawn settle (browser first-contact parity)."""

from __future__ import annotations

import math

from qwop_python.qwop_env import QWOPEnv
from qwop_python.data import PHYSICS_TIMESTEP


def _max_player_speed(physics) -> float:
    mx = 0.0
    for body in physics.bodies.values():
        vx, vy = body.linearVelocity
        mx = max(mx, math.hypot(vx, vy), abs(body.angularVelocity))
    return mx


def test_reset_settle_zeros_clock_and_velocities():
    env = QWOPEnv(settle_spawn=True, settle_max_steps=20)
    obs, info = env.reset(seed=0)
    assert obs.shape == (60,)
    assert info["time"] == 0.0
    assert abs(info["distance"]) < 1e-6
    assert env.game.score_time == 0.0
    assert abs(env.game.game_state.score) < 1e-6
    assert _max_player_speed(env.game.physics) < 1e-6
    assert not env.game.game_state.fallen
    env.close()


def test_settle_disabled_still_resets_cleanly():
    env = QWOPEnv(settle_spawn=False)
    _, info = env.reset(seed=1)
    assert info["time"] == 0.0
    assert abs(info["distance"]) < 1e-6
    assert _max_player_speed(env.game.physics) < 1e-6
    env.close()


def test_null_action_after_settle_no_huge_freefall_vy():
    """After settle, first null frames should not look like mid-air free-fall."""
    settled = QWOPEnv(settle_spawn=True, settle_max_steps=20)
    unsettled = QWOPEnv(settle_spawn=False)
    settled.reset(seed=0)
    unsettled.reset(seed=0)

    settled.game.controls.reset()
    settled.game.update(PHYSICS_TIMESTEP)
    unsettled.game.controls.reset()
    unsettled.game.update(PHYSICS_TIMESTEP)

    s_vy = settled.game.physics.get_body("torso").linearVelocity[1]
    u_vy = unsettled.game.physics.get_body("torso").linearVelocity[1]
    # Unsettled first tick is pure gravity (~g*dt = 0.4). Settled should be
    # smaller in magnitude than the ~2.5+ plant spike from free-fall.
    assert abs(s_vy) < 1.0
    assert abs(s_vy) <= abs(u_vy) + 0.05

    # Advance unsettled to typical plant window (~0.27s ≈ 8 updates from t0;
    # already did 1, so 7 more) and confirm free-fall spike exists without settle.
    for _ in range(7):
        unsettled.game.controls.reset()
        unsettled.game.update(PHYSICS_TIMESTEP)
    plant_vy = unsettled.game.physics.get_body("torso").linearVelocity[1]
    assert plant_vy > 1.5

    settled.close()
    unsettled.close()


if __name__ == "__main__":
    test_reset_settle_zeros_clock_and_velocities()
    test_settle_disabled_still_resets_cleanly()
    test_null_action_after_settle_no_huge_freefall_vy()
    print("ok")
