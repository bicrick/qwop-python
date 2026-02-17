"""
Test DQNfD Callback

Verifies that DQNfDCallback loads demonstrations and injects them into a replay buffer.
"""

import sys
import os
import tempfile
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from callbacks import DQNfDCallback


def test_dqnfd_callback_loads_demos():
    """Create minimal npz, instantiate callback, verify it loads."""
    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
        npz_path = f.name

    try:
        n_transitions = 100
        obs_dim = 60
        np.savez_compressed(
            npz_path,
            obs=np.random.randn(n_transitions, obs_dim).astype(np.float32),
            actions=np.random.randint(0, 9, n_transitions).astype(np.int32),
            rewards=np.random.randn(n_transitions).astype(np.float32),
            next_obs=np.random.randn(n_transitions, obs_dim).astype(np.float32),
            dones=np.random.choice([True, False], n_transitions),
        )

        callback = DQNfDCallback(
            demo_file=npz_path,
            injection_ratio=0.5,
            verbose=0,
        )
        assert callback.n_demos == n_transitions
        assert callback.injection_interval == 2  # 1/0.5 = 2
        assert callback.demo_obs.shape == (n_transitions, obs_dim)
        assert callback.demo_actions.shape == (n_transitions,)
    finally:
        os.unlink(npz_path)


def test_dqnfd_callback_injection_interval():
    """Verify injection interval calculation."""
    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
        npz_path = f.name

    try:
        np.savez_compressed(
            npz_path,
            obs=np.zeros((10, 60), dtype=np.float32),
            actions=np.zeros(10, dtype=np.int32),
            rewards=np.zeros(10, dtype=np.float32),
            next_obs=np.zeros((10, 60), dtype=np.float32),
            dones=np.zeros(10, dtype=bool),
        )

        for ratio, expected_interval in [(0.5, 2), (1.0, 1), (0.25, 4)]:
            cb = DQNfDCallback(demo_file=npz_path, injection_ratio=ratio, verbose=0)
            assert cb.injection_interval == expected_interval, (
                f"ratio={ratio} => interval={cb.injection_interval}, expected {expected_interval}"
            )
    finally:
        os.unlink(npz_path)


def test_dqnfd_callback_inject_calls_add():
    """Verify _inject_demonstration calls replay_buffer.add with correct shape."""
    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
        npz_path = f.name

    try:
        np.savez_compressed(
            npz_path,
            obs=np.zeros((5, 60), dtype=np.float32),
            actions=np.array([1, 2, 3, 0, 1], dtype=np.int32),
            rewards=np.ones(5, dtype=np.float32),
            next_obs=np.ones((5, 60), dtype=np.float32),
            dones=np.array([False, False, False, False, True], dtype=bool),
        )

        added = []

        class MockReplayBuffer:
            buffer_size = 100000

            def add(self, obs, next_obs, action, reward, done, infos):
                added.append(
                    {
                        "obs_shape": obs.shape,
                        "action_shape": action.shape,
                        "done_shape": done.shape,
                    }
                )

        class MockModel:
            replay_buffer = MockReplayBuffer()

        callback = DQNfDCallback(demo_file=npz_path, injection_ratio=1.0, verbose=0)
        callback.model = MockModel()
        callback._on_training_start()

        callback._inject_demonstration()
        callback._inject_demonstration()

        assert len(added) == 2
        assert added[0]["obs_shape"] == (1, 60)
        assert added[0]["action_shape"] == (1,)
        assert added[0]["done_shape"] == (1,)
    finally:
        os.unlink(npz_path)


if __name__ == "__main__":
    test_dqnfd_callback_loads_demos()
    print("test_dqnfd_callback_loads_demos: OK")
    test_dqnfd_callback_injection_interval()
    print("test_dqnfd_callback_injection_interval: OK")
    test_dqnfd_callback_inject_calls_add()
    print("test_dqnfd_callback_inject_calls_add: OK")
    print("\nAll DQNfD callback tests passed.")
