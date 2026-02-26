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

import math
import os

import sb3_contrib
import stable_baselines3
from gymnasium.wrappers import TimeLimit
from stable_baselines3.common import logger
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.utils import safe_mean

from . import common
from ..callbacks import EpisodeSuccessFilterCallback
from ..learners import PPOSuccessFilter


class LogCallback(BaseCallback):
    """Logs user-defined `info` values into tensorboard"""

    def _on_step(self) -> bool:
        ep_buffer = self.model.ep_info_buffer
        successful_eps = [ep for ep in ep_buffer if ep.get("is_success", 0)]
        for k in common.INFO_KEYS:
            if k == "is_success":
                v = safe_mean([ep[k] for ep in ep_buffer])
            else:
                v = safe_mean([ep[k] for ep in successful_eps])
            self.model.logger.record(f"user/{k}", v)
        return True

    on_step = _on_step  # Fixes a bug with stable-baselines3 in version 2.2.1


class VelocityRewardSchedulerCallback(BaseCallback):
    """Updates ProgressiveVelocityIncentiveWrapper with training progress."""

    def __init__(self, venv, total_timesteps):
        super().__init__()
        self.venv = venv
        self.total_timesteps = total_timesteps
        self._wrappers = self._find_progressive_wrappers()

    def _find_progressive_wrappers(self):
        wrappers = []
        for i in range(self.venv.num_envs):
            env = self.venv.envs[i]
            while env is not None:
                if hasattr(env, "set_progress"):
                    wrappers.append(env)
                    break
                env = getattr(env, "env", None)
        return wrappers

    def _on_step(self) -> bool:
        if not self._wrappers:
            return True
        progress_remaining = 1.0 - (self.model.num_timesteps / self.total_timesteps)
        for w in self._wrappers:
            w.set_progress(progress_remaining)
        return True


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
        case "PPO5":
            alg = PPOSuccessFilter
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


def create_vec_env(seed, max_episode_steps):
    """Create vectorized env. Requires common.register_env() to have been called first."""
    venv = make_vec_env(
        "local/QWOP-v1",
        env_kwargs={"seed": seed},
        monitor_kwargs={"info_keywords": common.INFO_KEYS},
        wrapper_class=TimeLimit,
        wrapper_kwargs={"max_episode_steps": max_episode_steps},
    )

    return venv


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
    out_dir_template,
    log_tensorboard,
):
    venv = create_vec_env(seed, max_episode_steps)

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

        callbacks = [
            LogCallback(),
            CheckpointCallback(
                save_freq=math.ceil(total_timesteps / n_checkpoints),
                save_path=out_dir,
                name_prefix="model",
            ),
        ]
        if learner_cls == "PPO5":
            callbacks.insert(0, EpisodeSuccessFilterCallback())
        scheduler = VelocityRewardSchedulerCallback(venv, total_timesteps)
        if scheduler._wrappers:
            callbacks.append(scheduler)

        model.learn(
            total_timesteps=total_timesteps,
            reset_num_timesteps=False,
            progress_bar=True,
            callback=callbacks,
        )

        common.save_model(out_dir, model)

        return {"out_dir": out_dir}
    finally:
        venv.close()
