"""
Smoke tests for the JS (Planck/PyMiniRacer) backend.

Requires: mini-racer (PyMiniRacer), and qwop_python/js/planck.min.js (see qwop_python/js/README.md).
"""

import os

import numpy as np
import pytest


def _mini_racer_available():
    try:
        from py_mini_racer import MiniRacer
        return True
    except ImportError:
        return False


def _planck_available():
    js_dir = os.path.join(os.path.dirname(__file__), "..", "qwop_python", "js")
    return os.path.isfile(os.path.join(js_dir, "planck.min.js"))


@pytest.mark.skipif(
    not _mini_racer_available(),
    reason="mini-racer not installed; pip install mini-racer or qwop-python[js]",
)
@pytest.mark.skipif(
    not _planck_available(),
    reason="planck.min.js not found in qwop_python/js/; see qwop_python/js/README.md",
)
def test_js_backend_reset_step():
    """JS backend: reset and several steps produce valid obs and no crash."""
    from qwop_python import QWOPEnv

    env = QWOPEnv(backend="js", seed=42, frames_per_step=1, reduced_action_set=True)
    obs, info = env.reset(seed=42)
    assert obs.shape == (60,)
    assert obs.dtype == np.float32
    assert "distance" in info
    assert "time" in info

    for _ in range(10):
        action = env.action_space.sample()
        obs, reward, term, trunc, info = env.step(action)
        assert obs.shape == (60,)
        assert np.isfinite(obs).all()
        assert np.isfinite(reward)
        if term or trunc:
            break

    env.close()


@pytest.mark.skipif(
    not _mini_racer_available(),
    reason="mini-racer not installed",
)
@pytest.mark.skipif(
    not _planck_available(),
    reason="planck.min.js not found",
)
def test_js_backend_deterministic_reset():
    """JS backend: same seed gives same initial observation."""
    from qwop_python import QWOPEnv

    env = QWOPEnv(backend="js", seed=123, frames_per_step=1)
    obs1, _ = env.reset(seed=123)
    obs2, _ = env.reset(seed=123)
    np.testing.assert_array_almost_equal(obs1, obs2)
    env.close()
