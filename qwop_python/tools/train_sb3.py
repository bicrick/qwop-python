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

import functools
import math
import os

import gymnasium as gym
import sb3_contrib
import stable_baselines3
from gymnasium.wrappers import TimeLimit
from stable_baselines3.common import logger
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import safe_mean
from stable_baselines3.common.vec_env import SubprocVecEnv

from . import common


def _subprocess_make_env(env_kwargs, env_wrappers, seed, max_episode_steps):
    """Create one env inside a SubprocVecEnv worker. Registers the env then makes it (so the
    worker process has the 'local/QWOP-v1' namespace). Called via partial from the parent."""
    common.register_env(env_kwargs, env_wrappers)
    kwargs = {**env_kwargs, "seed": seed}
    env = gym.make("local/QWOP-v1", **kwargs)
    env = TimeLimit(env, max_episode_steps=max_episode_steps)
    env = Monitor(env, info_keywords=common.INFO_KEYS)
    return env


class LogCallback(BaseCallback):
    """Logs user-defined `info` values into tensorboard"""

    def _on_step(self) -> bool:
        for k in common.INFO_KEYS:
            v = safe_mean([ep_info[k] for ep_info in self.model.ep_info_buffer])
            self.model.logger.record(f"user/{k}", v)
        return True

    on_step = _on_step  # Fixes a bug with stable-baselines3 in version 2.2.1


def init_model(
    venv,
    seed,
    model_load_file,
    learner_cls,
    learner_kwargs,
    learning_rate,
    log_tensorboard,
    out_dir,
):
    alg = None

    match learner_cls:
        case "A2C":
            alg = stable_baselines3.A2C
        case "PPO":
            alg = stable_baselines3.PPO
        case "DQN":
            alg = stable_baselines3.DQN
        case "QRDQN":
            alg = sb3_contrib.QRDQN
        case "RPPO":
            alg = sb3_contrib.RecurrentPPO
        case _:
            raise Exception("Unexpected learner_cls: %s" % learner_cls)

    if model_load_file:
        print("Loading %s model from %s" % (alg.__name__, model_load_file))
        model = alg.load(model_load_file, env=venv)
    else:
        kwargs = dict(learner_kwargs, learning_rate=learning_rate, seed=seed)
        model = alg(env=venv, **kwargs)

    if log_tensorboard:
        os.makedirs(out_dir, exist_ok=True)
        log = logger.configure(folder=out_dir, format_strings=["tensorboard"])
        model.set_logger(log)

    return model


def create_vec_env(seed, max_episode_steps, n_envs=1, env_kwargs=None, env_wrappers=None):
    """Create vectorized env. Requires common.register_env() to have been called first (for n_envs==1).
    For n_envs>1, each subprocess registers the env via _subprocess_make_env."""
    if n_envs > 1:
        env_kwargs = env_kwargs or {}
        env_wrappers = env_wrappers or []
        env_fns = [
            functools.partial(
                _subprocess_make_env,
                env_kwargs,
                env_wrappers,
                seed + i,
                max_episode_steps,
            )
            for i in range(n_envs)
        ]
        return SubprocVecEnv(env_fns, start_method="spawn")
    kwargs = dict(
        env_id="local/QWOP-v1",
        n_envs=1,
        seed=seed,
        env_kwargs={"seed": seed},
        monitor_kwargs={"info_keywords": common.INFO_KEYS},
        wrapper_class=TimeLimit,
        wrapper_kwargs={"max_episode_steps": max_episode_steps},
    )
    return make_vec_env(**kwargs)


def train_sb3(
    learner_cls,
    seed,
    run_id,
    model_load_file,
    learner_kwargs,
    learner_lr_schedule,
    total_timesteps,
    max_episode_steps,
    n_checkpoints,
    n_envs,
    out_dir_template,
    log_tensorboard,
    env_kwargs=None,
    env_wrappers=None,
):
    venv = create_vec_env(
        seed,
        max_episode_steps,
        n_envs=n_envs,
        env_kwargs=env_kwargs,
        env_wrappers=env_wrappers,
    )

    try:
        out_dir = common.out_dir_from_template(out_dir_template, seed, run_id)
        learning_rate = common.lr_from_schedule(learner_lr_schedule)

        model = init_model(
            venv=venv,
            seed=seed,
            model_load_file=model_load_file,
            learner_cls=learner_cls,
            learner_kwargs=learner_kwargs,
            learning_rate=learning_rate,
            log_tensorboard=log_tensorboard,
            out_dir=out_dir,
        )

        model.learn(
            total_timesteps=total_timesteps,
            reset_num_timesteps=False,
            progress_bar=True,
            callback=[
                LogCallback(),
                CheckpointCallback(
                    save_freq=math.ceil(total_timesteps / n_checkpoints),
                    save_path=out_dir,
                    name_prefix="model",
                ),
            ],
        )

        common.save_model(out_dir, model)

        return {"out_dir": out_dir}
    finally:
        venv.close()
