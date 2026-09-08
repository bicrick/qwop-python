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
import warnings

import sb3_contrib
import stable_baselines3
from gymnasium.wrappers import TimeLimit
from stable_baselines3.common import logger
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.utils import safe_mean
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from . import common
from .ep_info_metrics import mean_crossed_splits, mean_is_success, mean_optional_key
from .sb3_timesteps import format_learn_budget_log, resolve_learn_total_timesteps
from ..callbacks import EpisodeSuccessFilterCallback
from ..learners import PPOSuccessFilter


class LogCallback(BaseCallback):
    """Logs user-defined `info` values into tensorboard"""

    def _on_step(self) -> bool:
        ep_buffer = self.model.ep_info_buffer
        successful_eps = [ep for ep in ep_buffer if ep.get("is_success", 0)]
        for k in common.INFO_KEYS:
            if k == "is_success":
                v = mean_is_success(ep_buffer, safe_mean)
            elif k.startswith("split_") and k.endswith("_time"):
                # -1.0 means mark not reached; average only crossed splits
                v = mean_crossed_splits(ep_buffer, k, safe_mean)
            else:
                # Successful eps from older demos / transfers may omit optional
                # metrics (e.g. speed_mps); average only keys that are present.
                v = mean_optional_key(successful_eps, k, safe_mean)
            self.model.logger.record(f"user/{k}", v)
        return True

    on_step = _on_step  # Fixes a bug with stable-baselines3 in version 2.2.1


class VelocityRewardSchedulerCallback(BaseCallback):
    """
    Updates wrappers that expose set_progress(progress_remaining):
    - ProgressiveVelocityIncentiveWrapper
    - AntiScrapeCurriculumWrapper (when anneal_penalties=True)

    Progress is measured over the *current run* window
    [start_timesteps, end_timesteps), not the model's lifetime counter.
    That keeps fine-tunes (large loaded num_timesteps) annealing correctly.
    """

    def __init__(self, venv, end_timesteps, start_timesteps=0):
        super().__init__()
        self.venv = venv
        self.start_timesteps = int(start_timesteps)
        self.end_timesteps = int(end_timesteps)
        self._wrappers, self._use_env_method = self._resolve_update_path()

    def _resolve_update_path(self):
        """Find progressive wrappers (Dummy) or flag env_method use (Subproc)."""
        has_progressive = any(
            (w.get("cls") or "") == "ProgressiveVelocityIncentiveWrapper"
            for w in getattr(common, "_REGISTERED_ENV_WRAPPERS", []) or []
        )
        if not has_progressive:
            return [], False

        envs = getattr(self.venv, "envs", None)
        if envs is None:
            # SubprocVecEnv: update via env_method in workers.
            return [], True

        wrappers = []
        for env in envs:
            cur = env
            while cur is not None:
                if type(cur).__name__ == "ProgressiveVelocityIncentiveWrapper":
                    wrappers.append(cur)
                    break
                cur = getattr(cur, "env", None)
        return wrappers, False

    def _progress_remaining(self) -> float:
        span = max(1, self.end_timesteps - self.start_timesteps)
        done = self.model.num_timesteps - self.start_timesteps
        return 1.0 - (done / span)

    def _on_step(self) -> bool:
        if not self._wrappers and not self._use_env_method:
            return True
        progress_remaining = self._progress_remaining()
        if self._use_env_method:
            try:
                self.venv.env_method("set_progress", progress_remaining)
            except Exception:
                self._use_env_method = False
            return True
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


def create_vec_env(seed, max_episode_steps, n_envs=1):
    """Create vectorized env. Requires common.register_env() to have been called first.

    Uses SubprocVecEnv when n_envs > 1 for true multi-process parallelism.
    Falls back to DummyVecEnv if SubprocVecEnv fails (e.g. platform/Box2D issues).

    Passes a picklable ``RegisteredEnvFactory`` so worker processes can
    reconstruct envs without relying on the parent gymnasium registry.
    """
    n_envs = max(1, int(n_envs))
    make_kwargs = dict(
        env_id=common.get_registered_env_factory(),
        n_envs=n_envs,
        seed=seed,
        env_kwargs={},
        monitor_kwargs={"info_keywords": common.INFO_KEYS},
        wrapper_class=TimeLimit,
        wrapper_kwargs={"max_episode_steps": max_episode_steps},
    )

    if n_envs <= 1:
        return make_vec_env(**make_kwargs, vec_env_cls=DummyVecEnv)

    try:
        venv = make_vec_env(**make_kwargs, vec_env_cls=SubprocVecEnv)
        print("Using SubprocVecEnv with n_envs=%d" % n_envs)
        return venv
    except Exception as exc:
        warnings.warn(
            "SubprocVecEnv failed (%s); falling back to DummyVecEnv with n_envs=%d"
            % (exc, n_envs),
            RuntimeWarning,
            stacklevel=2,
        )
        return make_vec_env(**make_kwargs, vec_env_cls=DummyVecEnv)


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
    n_envs=1,
    reset_num_timesteps=False,
):
    """Train (or fine-tune) an SB3 / sb3-contrib algorithm.

    ``total_timesteps`` is always the *additional* step budget for this run
    (same semantics as ``--max-timesteps``). With the default
    ``reset_num_timesteps=False``, SB3's learn() uses an absolute counter, so
    we pass ``model.num_timesteps + total_timesteps`` (see sb3_timesteps).
    """
    venv = create_vec_env(seed, max_episode_steps, n_envs=n_envs)

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

        requested_additional = int(total_timesteps)
        loaded_num_timesteps = int(getattr(model, "num_timesteps", 0) or 0)
        # After reset_num_timesteps=True, SB3 zeros the counter at learn() start.
        schedule_start = 0 if reset_num_timesteps else loaded_num_timesteps
        learn_total = resolve_learn_total_timesteps(
            requested_additional,
            loaded_num_timesteps,
            reset_num_timesteps=reset_num_timesteps,
        )
        print(
            format_learn_budget_log(
                loaded_num_timesteps=loaded_num_timesteps,
                requested_additional=requested_additional,
                reset_num_timesteps=reset_num_timesteps,
                learn_total_timesteps=learn_total,
            ),
            flush=True,
        )

        # CheckpointCallback save_freq is in steps *per env* for VecEnv.
        # Space checkpoints across this run's *additional* budget.
        save_freq = max(
            1, math.ceil(requested_additional / (n_checkpoints * venv.num_envs))
        )
        callbacks = [
            LogCallback(),
            CheckpointCallback(
                save_freq=save_freq,
                save_path=out_dir,
                name_prefix="model",
            ),
        ]
        if learner_cls == "PPO5":
            callbacks.insert(0, EpisodeSuccessFilterCallback())
        scheduler = VelocityRewardSchedulerCallback(
            venv,
            end_timesteps=learn_total,
            start_timesteps=schedule_start,
        )
        if scheduler._wrappers or scheduler._use_env_method:
            callbacks.append(scheduler)

        model.learn(
            total_timesteps=learn_total,
            reset_num_timesteps=reset_num_timesteps,
            progress_bar=True,
            callback=callbacks,
        )

        common.save_model(out_dir, model)

        return {"out_dir": out_dir}
    finally:
        venv.close()
