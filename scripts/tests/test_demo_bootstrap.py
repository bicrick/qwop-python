"""Smoke tests for demo bootstrap: .rec format + BC policy round-trip."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3.common.policies import ActorCriticPolicy

from qwop_python.tools import common
from qwop_python.tools.train_bc import reconstruct_policy, save_bc_policy


def test_load_recording_roundtrip(tmp_path=None):
    root = tempfile.mkdtemp() if tmp_path is None else str(tmp_path)
    path = os.path.join(root, "demo.rec")
    with open(path, "w") as f:
        f.write("seed=123\n")
        f.write("1\n2\n3\n*\n")
        f.write("0\n0\nX\n")  # skipped episode terminator style
        f.write("4\n5\n*\n")

    rec = common.load_recording(path)
    assert rec["seed"] == 123
    assert len(rec["episodes"]) == 3
    assert rec["episodes"][0]["actions"] == [1, 2, 3]
    assert rec["episodes"][0]["skip"] is False
    assert rec["episodes"][1]["skip"] is True
    assert rec["episodes"][2]["actions"] == [4, 5]


def test_bc_policy_save_load():
    obs_space = spaces.Box(low=-1, high=1, shape=(60,), dtype=np.float32)
    act_space = spaces.Discrete(9)
    policy = ActorCriticPolicy(
        obs_space, act_space, lr_schedule=lambda _: 0.001, net_arch=[32, 32]
    )
    root = tempfile.mkdtemp()
    path = os.path.join(root, "model.zip")
    save_bc_policy(path, policy)
    loaded = reconstruct_policy(path, device="cpu")
    assert isinstance(loaded, ActorCriticPolicy)
    obs = obs_space.sample()
    a1, _ = policy.predict(obs, deterministic=True)
    a2, _ = loaded.predict(obs, deterministic=True)
    assert int(a1) == int(a2)


if __name__ == "__main__":
    test_load_recording_roundtrip()
    test_bc_policy_save_load()
    print("ok")
