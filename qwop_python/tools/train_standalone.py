"""Standalone training with train-style config (algorithm, n_envs, checkpoint_dir)."""

import os
import yaml
from pathlib import Path
from datetime import datetime

import numpy as np
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback, CallbackList
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import safe_mean
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import PPO, A2C, DQN

from .. import QWOPEnv


INFO_KEYS = ("time", "distance", "avgspeed", "is_success")
ALGORITHMS = {"QRDQN": QRDQN, "DQN": DQN, "PPO": PPO, "A2C": A2C}


class LogCallback(BaseCallback):
    def __init__(self, log_interval: int = 50, **kwargs):
        super().__init__(**kwargs)
        self.log_interval = log_interval

    def _on_step(self) -> bool:
        if not self.model.ep_info_buffer:
            return True
        if self.log_interval and self.n_calls % self.log_interval != 0:
            return True
        buf = self.model.ep_info_buffer
        for k in INFO_KEYS:
            try:
                v = safe_mean([e[k] for e in buf if k in e])
                if v == v:
                    self.model.logger.record(f"user/{k}", v)
            except (KeyError, ZeroDivisionError):
                pass
        return True


def make_env(rank, seed, env_kwargs, max_episode_steps):
    def _init():
        env = QWOPEnv(**env_kwargs, seed=seed + rank)
        env = TimeLimit(env, max_episode_steps=max_episode_steps)
        env = Monitor(env, info_keywords=INFO_KEYS)
        return env

    return _init


def get_device(prefer: str = "auto") -> str:
    if prefer and prefer != "auto":
        return prefer
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def run_train_standalone(config_path, run_id="default", resume_from=None):
    config = yaml.safe_load(open(config_path))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{config['algorithm']}_{run_id}_{timestamp}"

    checkpoint_dir = Path(config.get("checkpoint_dir", "data/checkpoints")) / run_name
    model_dir = Path(config.get("model_dir", "data/models")) / run_name
    log_dir = Path(config.get("log_dir", "data/logs")) / run_name
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "run_name": run_name,
        "checkpoint_dir": str(checkpoint_dir),
        "model_dir": str(model_dir),
        "log_dir": str(log_dir),
    }

    print("=" * 70)
    print("QWOP RL TRAINING")
    print("=" * 70)
    print()
    print(f"Loading config from: {config_path}")
    print(f"Algorithm: {config['algorithm']}")
    print(f"Total timesteps: {config['total_timesteps']:,}")
    print(f"Parallel environments: {config['n_envs']}")
    print()
    print(f"Run name: {paths['run_name']}")
    print(f"Checkpoints: {paths['checkpoint_dir']}")
    print(f"Models: {paths['model_dir']}")
    print(f"Logs: {paths['log_dir']}")
    print()

    print("Creating environments...")
    env_fns = [
        make_env(
            rank=i,
            seed=config.get("seed", 0),
            env_kwargs=config.get("env_kwargs", {}),
            max_episode_steps=config["max_episode_steps"],
        )
        for i in range(config["n_envs"])
    ]
    venv = SubprocVecEnv(env_fns)
    venv = VecMonitor(
        venv,
        filename=str(Path(paths["log_dir"]) / "monitor"),
        info_keywords=INFO_KEYS,
    )
    print(f"Created {config['n_envs']} parallel environments")
    print()

    algo_name = config["algorithm"]
    if algo_name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algo_name}")

    AlgorithmClass = ALGORITHMS[algo_name]
    learner_kwargs = dict(config.get("learner_kwargs", {}))
    device = get_device(learner_kwargs.pop("device", "auto"))
    learner_kwargs["device"] = device
    print(f"Using device: {device}")
    print()

    if resume_from:
        print(f"Resuming from checkpoint: {resume_from}")
        model = AlgorithmClass.load(
            resume_from,
            env=venv,
            device=device,
            tensorboard_log=paths["log_dir"] if config.get("tensorboard", False) else None,
        )
        print("Model loaded")
    else:
        print(f"Creating new {algo_name} model...")
        model = AlgorithmClass(
            policy="MlpPolicy",
            env=venv,
            tensorboard_log=paths["log_dir"] if config.get("tensorboard", False) else None,
            verbose=0,
            **learner_kwargs,
        )
        print("Model created")
    print()

    callbacks = []
    save_freq = config.get("save_freq", 100_000) // config["n_envs"]
    callbacks.append(
        CheckpointCallback(
            save_freq=save_freq,
            save_path=paths["checkpoint_dir"],
            name_prefix="model",
            save_replay_buffer=True,
            save_vecnormalize=False,
        )
    )
    callbacks.append(LogCallback(log_interval=config.get("user_metrics_log_interval", 1)))

    demo_file = config.get("demo_file")
    demo_injection_ratio = config.get("demo_injection_ratio", 0.5)
    if demo_file and demo_injection_ratio and algo_name in ("QRDQN", "DQN"):
        if not os.path.exists(demo_file):
            raise FileNotFoundError(f"DQNfD demo_file not found: {demo_file}")
        from ..callbacks import DQNfDCallback

        callbacks.append(
            DQNfDCallback(
                demo_file=demo_file,
                injection_ratio=demo_injection_ratio,
                verbose=1,
            )
        )
        print(f"DQNfD enabled: injecting demos from {demo_file} at ratio {demo_injection_ratio}")

    callback_list = CallbackList(callbacks)
    print()
    print("=" * 70)
    print("STARTING TRAINING")
    print("=" * 70)
    print()

    try:
        model.learn(
            total_timesteps=config["total_timesteps"],
            callback=callback_list,
            progress_bar=True,
            reset_num_timesteps=False if resume_from else True,
        )
        print()
        print("=" * 70)
        print("TRAINING COMPLETE")
        print("=" * 70)
        print()
        final_model_path = Path(paths["model_dir"]) / "final_model"
        model.save(final_model_path)
        print(f"Final model saved to: {final_model_path}")
        config_save_path = Path(paths["model_dir"]) / "config.yml"
        with open(config_save_path, "w") as f:
            yaml.dump(config, f)
        print(f"Configuration saved to: {config_save_path}")
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("TRAINING INTERRUPTED")
        print("=" * 70)
        print()
        interrupted_model_path = Path(paths["model_dir"]) / "interrupted_model"
        model.save(interrupted_model_path)
        print(f"Interrupted model saved to: {interrupted_model_path}")
    finally:
        venv.close()
        print()
        print("Training session ended")
