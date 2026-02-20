"""
Parity tests: determinism and (optional) gold-trace comparison.

- Determinism: same seed + same actions => same obs, reward, terminated, info.
- Gold trace: when a gold file exists, replay and compare within tolerance.
"""

import json
import os

import numpy as np
import pytest

from qwop_python import QWOPEnv


def _run_episode(env, seed, actions, max_steps=200):
    """Run env with given seed and action list; return (observations, rewards, dones, infos)."""
    obs_list, reward_list, term_list, trunc_list, info_list = [], [], [], [], []
    obs, info = env.reset(seed=seed)
    for t, action in enumerate(actions):
        if t >= max_steps:
            break
        obs_list.append(obs.copy())
        obs, reward, terminated, truncated, info = env.step(action)
        reward_list.append(reward)
        term_list.append(terminated)
        trunc_list.append(truncated)
        info_list.append({k: (v if not isinstance(v, np.floating) else float(v)) for k, v in info.items()})
        if terminated or truncated:
            break
    return obs_list, reward_list, term_list, trunc_list, info_list


# Box2D/SWIG can produce tiny float differences; use small atol for obs/reward
DETERMINISM_ATOL = 1e-5
DETERMINISM_RTOL = 1e-6


def test_determinism_same_seed_same_actions():
    """Same seed and same action sequence must yield same trajectory (two fresh envs)."""
    seed = 42
    frames_per_step = 4
    actions = [0, 1, 2, 0, 1, 0, 2, 1] * 20  # 160 steps max

    env1 = QWOPEnv(seed=seed, frames_per_step=frames_per_step, reduced_action_set=True)
    env2 = QWOPEnv(seed=seed, frames_per_step=frames_per_step, reduced_action_set=True)
    run1 = _run_episode(env1, seed, actions)
    run2 = _run_episode(env2, seed, actions)
    env1.close()
    env2.close()

    obs1, rewards1, term1, trunc1, info1 = run1
    obs2, rewards2, term2, trunc2, info2 = run2

    assert len(obs1) == len(obs2), "Step count must match"
    for i in range(len(obs1)):
        assert np.allclose(obs1[i], obs2[i], rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL), (
            f"Obs mismatch at step {i}"
        )
    for i in range(len(rewards1)):
        assert np.isclose(rewards1[i], rewards2[i], rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL), (
            f"Reward mismatch at step {i}"
        )
    assert term1 == term2, "Terminated must match"
    assert trunc1 == trunc2, "Truncated must match"
    for i in range(len(info1)):
        for k in info1[i]:
            a, b = info1[i][k], info2[i][k]
            if isinstance(a, (int, bool)):
                assert a == b, f"Info[{i}][{k}] mismatch: {a} vs {b}"
            elif isinstance(a, float):
                assert np.isclose(a, b, rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL), (
                    f"Info[{i}][{k}] mismatch: {a} vs {b}"
                )
            elif isinstance(a, (list, np.ndarray)):
                assert np.allclose(
                    np.asarray(a), np.asarray(b), rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL
                ), f"Info[{i}][{k}] mismatch"


def test_determinism_protocol_30hz():
    """Determinism holds with reward_dt_mode=protocol_30hz (two fresh envs)."""
    seed = 123
    actions = [0, 1, 0, 2, 0] * 30

    env1 = QWOPEnv(
        seed=seed,
        frames_per_step=4,
        reduced_action_set=True,
        reward_dt_mode="protocol_30hz",
    )
    env2 = QWOPEnv(
        seed=seed,
        frames_per_step=4,
        reduced_action_set=True,
        reward_dt_mode="protocol_30hz",
    )
    run1 = _run_episode(env1, seed, actions)
    run2 = _run_episode(env2, seed, actions)
    env1.close()
    env2.close()

    obs1, rewards1, _, _, info1 = run1
    obs2, rewards2, _, _, info2 = run2
    assert len(obs1) == len(obs2)
    for i in range(len(obs1)):
        assert np.allclose(obs1[i], obs2[i], rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL)
    for i in range(len(rewards1)):
        assert np.isclose(rewards1[i], rewards2[i], rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL)
    for i in range(len(info1)):
        assert np.isclose(
            info1[i]["time"], info2[i]["time"], rtol=DETERMINISM_RTOL, atol=DETERMINISM_ATOL
        )


# Gold trace comparison (skipped if no gold file)
GOLD_TRACE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLD_TRACE_RTOL = 1e-3
GOLD_TRACE_ATOL = 1e-5


def _gold_trace_path(seed, frames_per_step=4):
    return os.path.join(GOLD_TRACE_DIR, f"gold_trace_seed{seed}_fps{frames_per_step}.json")


def _load_gold(path):
    with open(path) as f:
        data = json.load(f)
    return data


def _compare_step(obs, reward, terminated, truncated, info, gold, step_i):
    go, gr, gterm, gtrunc, gi = gold["obs"], gold["reward"], gold["terminated"], gold["truncated"], gold["info"]
    assert np.allclose(obs, np.array(go), rtol=GOLD_TRACE_RTOL, atol=GOLD_TRACE_ATOL), (
        f"Step {step_i}: obs mismatch"
    )
    assert np.isclose(reward, gr, rtol=GOLD_TRACE_RTOL, atol=GOLD_TRACE_ATOL), (
        f"Step {step_i}: reward {reward} vs gold {gr}"
    )
    assert terminated == gterm, f"Step {step_i}: terminated mismatch"
    assert truncated == gtrunc, f"Step {step_i}: truncated mismatch"
    for k in ("time", "distance", "avgspeed", "is_success"):
        if k in gi:
            assert np.isclose(info.get(k, 0), gi[k], rtol=GOLD_TRACE_RTOL, atol=GOLD_TRACE_ATOL), (
                f"Step {step_i}: info[{k}] mismatch"
            )


def test_constants_parity():
    """Assert critical physics/reward constants match documented parity (QWOP.min.js)."""
    from qwop_python.data import (
        GRAVITY,
        WORLD_SCALE,
        PHYSICS_TIMESTEP,
        VELOCITY_ITERATIONS,
        POSITION_ITERATIONS,
        DENSITY_FACTOR,
        TORQUE_FACTOR,
        TRACK_Y,
        CATEGORY_PLAYER,
        MASK_NO_SELF,
        HEAD_TORQUE_FACTOR,
        HEAD_TORQUE_OFFSET,
        CONTROL_Q,
        CONTROL_W,
        CONTROL_O,
        CONTROL_P,
    )
    assert GRAVITY == 10
    assert WORLD_SCALE == 20
    assert PHYSICS_TIMESTEP == 0.04
    assert VELOCITY_ITERATIONS == 5
    assert POSITION_ITERATIONS == 5
    assert DENSITY_FACTOR == 1
    assert TORQUE_FACTOR == 1
    assert abs(TRACK_Y - 10.74275) < 1e-5
    assert CATEGORY_PLAYER == 2
    assert MASK_NO_SELF == 65533
    assert HEAD_TORQUE_FACTOR == -4
    assert HEAD_TORQUE_OFFSET == 0.2
    # CONTROL_* motor_speeds and hip_limits (min.js 875)
    assert CONTROL_Q["motor_speeds"] == {
        "rightHip": 2.5,
        "leftHip": -2.5,
        "rightShoulder": -2.0,
        "leftShoulder": 2.0,
        "rightElbow": -10.0,
        "leftElbow": -10.0,
    }
    assert CONTROL_W["motor_speeds"] == {
        "rightHip": -2.5,
        "leftHip": 2.5,
        "rightShoulder": 2.0,
        "leftShoulder": -2.0,
        "rightElbow": 10.0,
        "leftElbow": 10.0,
    }
    assert CONTROL_O["motor_speeds"] == {"rightKnee": 2.5, "leftKnee": -2.5}
    assert CONTROL_O["hip_limits"] == {"leftHip": (-1.0, 1.0), "rightHip": (-1.3, 0.7)}
    assert CONTROL_P["motor_speeds"] == {"rightKnee": -2.5, "leftKnee": 2.5}
    assert CONTROL_P["hip_limits"] == {"leftHip": (-1.5, 0.5), "rightHip": (-0.8, 1.2)}


@pytest.mark.skipif(
    not os.path.isfile(_gold_trace_path(42)),
    reason="Gold trace not found; see doc/PARITY_GOLD_TRACE.md to generate",
)
def test_gold_trace_parity():
    """Replay from gold trace and compare obs, reward, done, info within tolerance."""
    seed = 42
    frames_per_step = 4
    path = _gold_trace_path(seed, frames_per_step)
    gold_data = _load_gold(path)
    assert gold_data["seed"] == seed
    assert gold_data["frames_per_step"] == frames_per_step
    steps = gold_data["steps"]

    env = QWOPEnv(
        seed=seed,
        frames_per_step=frames_per_step,
        reduced_action_set=gold_data.get("reduced_action_set", True),
        reward_dt_mode=gold_data.get("reward_dt_mode", "protocol_30hz"),
    )
    obs, info = env.reset(seed=seed)
    for i, gold_step in enumerate(steps):
        action = gold_step["action"]
        obs, reward, terminated, truncated, info = env.step(action)
        _compare_step(obs, reward, terminated, truncated, info, gold_step, i)
        if terminated or truncated:
            break
    env.close()
