"""
Cross-env parity test: qwop-python vs qwop-gym (browser).

Runs the same (seed, action sequence) in both envs and compares obs, reward,
terminated, truncated, and info step-by-step. Requires:
- qwop-gym installed (pip install -e /path/to/qwop-gym)
- Chrome and chromedriver; set QWOP_GYM_BROWSER and QWOP_GYM_DRIVER.

See doc/CROSS_ENV_TEST.md for setup.
"""

import os
import sys

import numpy as np
import pytest

# Tolerances for cross-env comparison (browser Box2D vs PyBox2D; divergence compounds)
CROSS_RTOL = 2e-2
CROSS_ATOL = 1e-1
REWARD_RTOL, REWARD_ATOL = 5e-1, 1e-1
INFO_RTOL, INFO_ATOL = 5e-1, 1e-1


def _get_browser_driver():
    browser = os.environ.get("QWOP_GYM_BROWSER")
    driver = os.environ.get("QWOP_GYM_DRIVER")
    return browser, driver


def _try_import_qwop_gym():
    try:
        from qwop_gym.envs.v1.qwop_env import QwopEnv as QwopEnvGym
        return QwopEnvGym
    except ImportError:
        return None


@pytest.mark.skipif(
    _try_import_qwop_gym() is None,
    reason="qwop-gym not installed; pip install -e /path/to/qwop-gym",
)
@pytest.mark.skipif(
    None in _get_browser_driver(),
    reason="Set QWOP_GYM_BROWSER and QWOP_GYM_DRIVER to run cross-env parity test",
)
def test_cross_env_parity_qwop_python_vs_qwop_gym():
    """Same seed + same actions in qwop-gym (browser) and qwop-python => same trajectory within tolerance."""
    from qwop_python import QWOPEnv as QWOPEnvPython

    QwopEnvGym = _try_import_qwop_gym()
    browser, driver = _get_browser_driver()

    seed = 42
    frames_per_step = 4
    max_steps = 80
    actions = [0, 1, 2, 0, 1, 0, 2, 1] * 10  # 80 actions

    env_gym = None
    env_py = None
    try:
        env_gym = QwopEnvGym(
            browser=browser,
            driver=driver,
            seed=seed,
            frames_per_step=frames_per_step,
            reduced_action_set=True,
            game_in_browser=False,
            t_for_terminate=False,
        )
        env_py = QWOPEnvPython(
            seed=seed,
            frames_per_step=frames_per_step,
            reduced_action_set=True,
            reward_dt_mode="protocol_30hz",
        )

        obs_g, _ = env_gym.reset(seed=seed)
        obs_p, _ = env_py.reset(seed=seed)

        # Initial obs should match
        assert np.allclose(obs_g, obs_p, rtol=CROSS_RTOL, atol=CROSS_ATOL), "Initial obs mismatch"

        for step in range(min(max_steps, len(actions))):
            action = actions[step]
            obs_g, r_g, term_g, trunc_g, info_g = env_gym.step(action)
            obs_p, r_p, term_p, trunc_p, info_p = env_py.step(action)

            assert np.allclose(obs_g, obs_p, rtol=CROSS_RTOL, atol=CROSS_ATOL), (
                f"Step {step}: obs mismatch"
            )
            assert np.isclose(r_g, r_p, rtol=REWARD_RTOL, atol=REWARD_ATOL), (
                f"Step {step}: reward {r_g} vs {r_p}"
            )
            assert term_g == term_p, f"Step {step}: terminated {term_g} vs {term_p}"
            assert trunc_g == trunc_p, f"Step {step}: truncated {trunc_g} vs {trunc_p}"

            for key in ("time", "distance", "avgspeed"):
                if key in info_g and key in info_p:
                    gv, pv = info_g[key], info_p[key]
                    assert np.isclose(gv, pv, rtol=INFO_RTOL, atol=INFO_ATOL), (
                        f"Step {step}: info[{key}] {gv} vs {pv}"
                    )
            if "is_success" in info_g and "is_success" in info_p:
                assert info_g["is_success"] == info_p["is_success"], (
                    f"Step {step}: info[is_success] {info_g['is_success']} vs {info_p['is_success']}"
                )

            if term_g or trunc_g:
                break
    finally:
        if env_gym is not None:
            env_gym.close()
        if env_py is not None:
            env_py.close()
