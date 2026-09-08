# =============================================================================
# Copyright 2023 Simeon Manolov <s.manolloff@gmail.com>.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""Headlessly roll out a saved SB3 model and write .rec demonstration files."""

from __future__ import annotations

import importlib
import os

import gymnasium as gym

from . import common


def _load_model(mod_name, cls_name, file):
    print("Loading %s model from %s" % (cls_name, file))
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name).load(file)


def _find_record_wrapper(env):
    cur = env
    while cur is not None:
        if type(cur).__name__ == "RecordWrapper":
            return cur
        cur = getattr(cur, "env", None)
    return None


def record_model(
    model_file,
    model_mod="sb3_contrib",
    model_cls="QRDQN",
    n_episodes=20,
    max_episode_steps=2000,
    seed=None,
    deterministic=True,
    rec_file=None,
):
    """Run headless episodes and append kept trajectories to a .rec file.

    Env + RecordWrapper must already be registered via ``common.register_env``
    (main.py does this before dispatch). Prefer ``config/record_model.yml``.
    """
    if not model_file:
        raise ValueError("model_file is required for record_model")

    seed = int(seed) if seed is not None else common.gen_seed()
    model = _load_model(model_mod, model_cls, model_file)

    # Headless: do not set render_mode. RecordWrapper should be in env_wrappers.
    env = gym.make("local/QWOP-v1")
    recorder = _find_record_wrapper(env)
    if recorder is None:
        raise RuntimeError(
            "record_model requires RecordWrapper in env_wrappers "
            "(see config/record_model.yml)"
        )

    if rec_file:
        # Allow config-level rec_file override after wrapper construction.
        # RecordWrapper already opened its path; only warn if they differ.
        configured = getattr(recorder, "rec_file", None)
        if configured and os.path.abspath(configured) != os.path.abspath(rec_file):
            print(
                "Note: RecordWrapper rec_file=%s (ignoring top-level rec_file=%s)"
                % (configured, rec_file)
            )

    try:
        obs, _info = env.reset(seed=seed)
        # Header was written at wrapper init (possibly seed=0). Rewrite so
        # load_recordings / BC replay use the actual recording seed.
        recorder.rewrite_seed_header(seed)

        for ep in range(1, int(n_episodes) + 1):
            terminated = False
            truncated = False
            steps = 0
            info = {}
            while not (terminated or truncated) and steps < int(max_episode_steps):
                action, _ = model.predict(obs, deterministic=deterministic)
                if hasattr(action, "item"):
                    action = int(action.item())
                else:
                    action = int(action)
                obs, _reward, terminated, truncated, info = env.step(action)
                steps += 1

            ep_dist = info.get("distance", float("nan"))
            ep_time = info.get("time", float("nan"))
            if terminated or truncated:
                print(
                    "Episode %d/%d finished: time=%.2f distance=%.2f steps=%d "
                    "(recorded=%d discarded=%d)"
                    % (
                        ep,
                        n_episodes,
                        ep_time,
                        ep_dist,
                        steps,
                        recorder.n_recorded,
                        recorder.n_discarded,
                    )
                )
            else:
                print(
                    "Episode %d/%d hit max_episode_steps without terminate "
                    "(time=%.2f distance=%.2f steps=%d) — not written as *"
                    % (ep, n_episodes, ep_time, ep_dist, steps)
                )
                recorder.actions = []

            if ep < int(n_episodes):
                obs, _info = env.reset()
    finally:
        # Wrapper.close flushes the .rec handle then closes the env chain.
        env.close()

    out_path = getattr(recorder, "rec_file", None)
    print(
        "record_model done: episodes_run=%d recorded=%d discarded=%d file=%s"
        % (n_episodes, recorder.n_recorded, recorder.n_discarded, out_path)
    )
    return {
        "rec_file": out_path,
        "seed": seed,
        "n_episodes": int(n_episodes),
        "n_recorded": recorder.n_recorded,
        "n_discarded": recorder.n_discarded,
    }