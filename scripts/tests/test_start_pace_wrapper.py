"""Smoke tests for StartPaceWrapper with settle_spawn."""

from __future__ import annotations

from qwop_python.qwop_env import QWOPEnv
from qwop_python.wrappers.start_pace_wrapper import StartPaceWrapper


def test_start_pace_reset_and_steps_with_settle():
    env = StartPaceWrapper(
        QWOPEnv(settle_spawn=True, settle_max_steps=20, frames_per_step=2)
    )
    obs, info = env.reset(seed=0)
    assert obs.shape == (60,)
    assert "start_pace" in info
    assert info["start_pace"]["reached_focus"] is False
    assert "shaped_rewards" in info
    assert "start_pace_progress" in info["shaped_rewards"]

    for _ in range(5):
        obs, reward, terminated, truncated, info = env.step(0)
        assert "start_pace" in info
        assert "progress_bonus" in info["start_pace"]
        assert "split_bonus" in info["start_pace"]
        assert "early_fail_penalty" in info["start_pace"]
        assert isinstance(reward, float)
        if terminated or truncated:
            break

    env.close()


def test_start_pace_defaults():
    env = StartPaceWrapper(QWOPEnv(settle_spawn=True, settle_max_steps=20))
    assert env.focus_m == 10.0
    assert env.progress_mult == 4.0
    assert env.split_ref_s == 12.0
    assert env.split_bonus_scale == 1.5
    assert env.early_fail_cost == 10.0
    assert env.post_focus_progress_mult == 0.0
    env.close()


def test_early_fail_penalty_when_fallen_before_focus():
    """Force fallen before focus_m and check -early_fail_cost is applied."""
    base = QWOPEnv(settle_spawn=True, settle_max_steps=20, frames_per_step=1)
    env = StartPaceWrapper(base, focus_m=10.0, early_fail_cost=10.0)
    env.reset(seed=1)

    # Drive a few steps, then mark fallen/ended before focus.
    for _ in range(3):
        obs, reward, terminated, truncated, info = env.step(0)
        if terminated or truncated:
            break

    if not (terminated or truncated):
        # Inject terminal fall before focus for shaping check.
        env.unwrapped.game.game_state.fallen = True
        env.unwrapped.game.game_state.game_ended = True
        # One more step path: call shaping logic via a synthetic wrap by
        # stepping after game_ended (env still returns terminated).
        obs, reward, terminated, truncated, info = env.step(0)
        assert terminated
        if float(info.get("distance", 0.0)) < env.focus_m:
            assert info["start_pace"]["early_fail_penalty"] == -10.0
            assert info["shaped_rewards"]["start_pace_early_fail"] == -10.0

    env.close()


if __name__ == "__main__":
    test_start_pace_defaults()
    test_start_pace_reset_and_steps_with_settle()
    test_early_fail_penalty_when_fallen_before_focus()
    print("ok")
