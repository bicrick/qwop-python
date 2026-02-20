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

import importlib
import time
import os
import re
import glob
import math
import random
import string
import numpy as np
import yaml

from gymnasium.envs.registration import register

from ..qwop_env import QWOPEnv

# Keys of user-defined metrics in the `info` dict
INFO_KEYS = ("time", "distance", "avgspeed", "is_success", "total_reward")

# QWOPEnv kwargs we accept (filter out browser-specific etc.)
ALLOWED_ENV_KWARGS = {
    "backend",
    "frames_per_step",
    "reduced_action_set",
    "failure_cost",
    "success_reward",
    "time_cost_mult",
    "seed",
    "speed_rew_mult",
    "render_mode",
    "show_observation_panel",
    "reward_mode",
    "distance_rew_mult",
    "time_cost_mult_distance",
    "reward_dt_mode",
}


class Clock:
    """A better alternative to pygame.Clock for our use-case"""

    def __init__(self, fps):
        self.fps = fps
        self.min_interval = 1 / fps
        self.last_tick_at = time.time()

    def tick(self):
        tick_at = time.time()
        interval = tick_at - self.last_tick_at
        sleep_for = self.min_interval - interval

        if sleep_for > 0:
            time.sleep(sleep_for)

        self.last_tick_at = tick_at + sleep_for


class Replayer:
    def __init__(self, actions):
        self.actions = actions
        self.iterator = iter(actions)
        self.i = 0

    def predict(self, _obs):
        self.i += 1
        action = next(self.iterator, None)
        assert (
            action is not None
        ), f"Unexpected end of recording -- check seed, frames_per_step and steps_per_step"
        return (action, None)


def expand_env_kwargs(env_kwargs):
    env_include_cfg = env_kwargs.pop("__include__", None)

    if env_include_cfg:
        with open(env_include_cfg, "r") as f:
            env_kwargs = yaml.safe_load(f) | env_kwargs

    return env_kwargs


def register_env(env_kwargs=None, env_wrappers=None):
    if env_kwargs is None:
        env_kwargs = {}
    if env_wrappers is None:
        env_wrappers = []

    def wrapped_env_creator(**kwargs):
        filtered = {k: v for k, v in kwargs.items() if k in ALLOWED_ENV_KWARGS}
        env = QWOPEnv(**filtered)

        for wrapper in env_wrappers:
            wrapper_mod = importlib.import_module(wrapper["module"])
            wrapper_cls = getattr(wrapper_mod, wrapper["cls"])
            env = wrapper_cls(env, **wrapper.get("kwargs", {}))

        return env

    register(
        id="local/QWOP-v1",
        entry_point=wrapped_env_creator,
        kwargs=env_kwargs,
    )


def gen_seed():
    return int(np.random.default_rng().integers(2**31))


def gen_id():
    population = string.ascii_lowercase + string.digits
    return str.join("", random.choices(population, k=8))


def out_dir_from_template(tmpl, seed, run_id):
    out_dir = tmpl.format(seed=seed, run_id=run_id)

    if os.path.exists(out_dir):
        raise Exception("Output directory already exists: %s" % out_dir)

    return out_dir


def load_recordings(rec_file_patterns):
    recs = []
    if isinstance(rec_file_patterns, str):
        rec_file_patterns = [rec_file_patterns]

    for rfp in rec_file_patterns:
        for rec_file in sorted(glob.glob(rfp)):
            rec = load_recording(rec_file)

            if len(rec["episodes"]) > 0:
                recs.append(rec)

    if len(recs) == 0:
        print("No recordings found")
        exit(1)

    return recs


def load_recording(recfile):
    episodes = []

    with open(recfile) as f:
        rechead = f.readline()

        m = re.match(r"^seed=(\d+)$", rechead)
        assert m, "Failed to parse header for recording: %s" % recfile
        seed = int(m.group(1))

        actions = []
        n_episodes = 0

        for line in f:
            line = line.rstrip()

            if line == "*":
                episodes.append({"skip": False, "actions": actions})
                n_episodes += 1
                actions = []
            elif line == "X":
                episodes.append({"skip": True, "actions": actions})
                n_episodes += 1
                actions = []
            else:
                actions.append(int(line))

    if n_episodes == 0:
        print("Empty recording %s" % recfile)
    else:
        print("Loaded %d episodes with seed=%d from %s " % (n_episodes, seed, recfile))

    return {"file": recfile, "seed": seed, "episodes": episodes}


def exp_decay_fn(initial_value, final_value, decay_fraction, n_decays):
    assert initial_value > final_value
    assert final_value > 0
    assert decay_fraction >= 0 and decay_fraction <= 1
    assert n_decays > 0

    multiplier = math.exp(math.log(final_value / initial_value) / n_decays)
    const_fraction = 1 - decay_fraction
    milestones = [
        const_fraction + decay_fraction * step / (n_decays)
        for step in range(0, n_decays)
    ]

    milestones.reverse()

    def func(progress_remaining: float) -> float:
        value = initial_value
        for m in milestones:
            if progress_remaining < m:
                value *= multiplier
                if value < final_value:
                    break
            else:
                break
        return value

    return func


def lin_decay_fn(initial_value, final_value, decay_fraction):
    assert initial_value > final_value
    assert final_value > 0
    assert decay_fraction >= 0 and decay_fraction <= 1
    const_fraction = 1 - decay_fraction

    def func(progress_remaining: float) -> float:
        return max(0, 1 + (initial_value * progress_remaining - 1) / decay_fraction)

    return func


def lr_from_schedule(schedule):
    r_float = r"\d+(?:\.\d+)?"
    r_const = rf"^const_({r_float})$"
    r_lin = rf"^lin_decay_({r_float})_({r_float})_({r_float})$"
    r_exp = rf"^exp_decay_({r_float})_({r_float})_({r_float})(?:_(\d+))$"

    m = re.match(r_const, schedule)
    if m:
        return float(m.group(1))

    m = re.match(r_lin, schedule)
    if m:
        return lin_decay_fn(
            initial_value=float(m.group(1)),
            final_value=float(m.group(2)),
            decay_fraction=float(m.group(3)),
        )

    m = re.match(r_exp, schedule)
    if m:
        return exp_decay_fn(
            initial_value=float(m.group(1)),
            final_value=float(m.group(2)),
            decay_fraction=float(m.group(3)),
            n_decays=int(m.group(4)) if len(m.groups()) > 4 else 10,
        )

    print("Invalid config value for learner_lr_schedule: %s" % schedule)
    exit(1)


def skip_episode(env, steps_per_step, model):
    """Fast-forward through a skipped episode without rendering."""
    terminated = False

    try:
        env.get_wrapper_attr("disable_verbose_wrapper")()
    except AttributeError:
        pass

    while not terminated:
        action, _ = model.predict(None)
        for _ in range(steps_per_step):
            _, _, terminated, _, _ = env.step(action)
            if terminated:
                break

    try:
        env.get_wrapper_attr("enable_verbose_wrapper")()
    except AttributeError:
        pass


def play_model(env, fps, steps_per_step, model, obs):
    terminated = False
    clock = Clock(fps)

    while not terminated:
        action, _states = model.predict(obs)
        for _ in range(steps_per_step):
            obs, reward, terminated, truncated, info = env.step(action)
            env.render()
            clock.tick()
            if terminated:
                break


def save_model(out_dir, model):
    os.makedirs(out_dir, exist_ok=True)
    model_file = os.path.join(out_dir, "model.zip")
    model.save(model_file)


def save_config(out_dir, config):
    os.makedirs(out_dir, exist_ok=True)
    config_file = os.path.join(out_dir, "config.yml")

    with open(config_file, "w") as f:
        f.write(yaml.safe_dump(config))


def measure(func, kwargs):
    t1 = time.time()
    retval = func(**kwargs)
    t2 = time.time()

    return t2 - t1, retval


def save_run_metadata(action, cfg, duration, values):
    out_dir = values["out_dir"]
    metadata = dict(values, action=action, config=cfg, duration=duration)

    print("Output directory: %s" % out_dir)
    os.makedirs(out_dir, exist_ok=True)
    md_file = os.path.join(out_dir, "metadata.yml")

    with open(md_file, "w") as f:
        f.write(yaml.safe_dump(metadata))
