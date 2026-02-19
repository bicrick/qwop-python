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

import argparse
import importlib.resources
import os
import sys
from copy import deepcopy

import yaml

from . import common


def run(action, cfg, cli_overrides=None):
    cli_overrides = cli_overrides or {}

    if action == "play":
        from .play import run_play
        run_play()
        return

    env_wrappers = cfg.pop("env_wrappers", [])
    env_kwargs = cfg.pop("env_kwargs", {})
    expanded_env_kwargs = common.expand_env_kwargs(env_kwargs)
    common.register_env(expanded_env_kwargs, env_wrappers)

    if action in ("replay", "spectate", "benchmark", "train_bc", "train_gail", "train_airl"):
        print("Not implemented: %s" % action)
        sys.exit(1)

    if action in ("train_a2c", "train_ppo", "train_dqn", "train_qrdqn", "train_rppo"):
        ensure_sb3_installed()
        from .train_sb3 import train_sb3

        learner_cls = action.split("_")[-1].upper()
        default_template = "data/%s-{run_id}" % learner_cls

        run_config = deepcopy(
            {
                "seed": cfg.get("seed") or common.gen_seed(),
                "run_id": cfg.get("run_id") or common.gen_id(),
                "model_load_file": cfg.get("model_load_file"),
                "out_dir_template": cfg.get("out_dir_template", default_template),
                "log_tensorboard": cfg.get("log_tensorboard", False),
                "learner_kwargs": cfg.get("learner_kwargs", {}),
                "total_timesteps": cfg.get("total_timesteps", 1000000),
                "max_episode_steps": cfg.get("max_episode_steps", 5000),
                "n_checkpoints": cfg.get("n_checkpoints", 5),
                "learner_lr_schedule": cfg.get("learner_lr_schedule", "const_0.001"),
            }
        )

        run_duration, run_values = common.measure(
            train_sb3, dict(run_config, learner_cls=learner_cls)
        )

        common.save_run_metadata(
            action=action,
            cfg=dict(run_config, env_kwargs=env_kwargs),
            duration=run_duration,
            values=dict(run_values, env=expanded_env_kwargs),
        )
    else:
        print("Unknown action: %s" % action)
        sys.exit(1)


def ensure_sb3_installed():
    try:
        import stable_baselines3  # noqa: F401
    except ImportError as e:
        print(
            """
To use this feature, install stable_baselines3 and sb3-contrib:

    pip install stable_baselines3 sb3-contrib

Or install qwop-python with the sb3 extra (in the same env as qwop-python):

    pip install "qwop-python[sb3]"

(ImportError: %s)
"""
            % (e,)
        )
        sys.exit(1)


def ensure_bootstrapped(progname, action):
    if not os.path.isdir("config"):
        print("\nRun from project root or run: qwop-python bootstrap\n")
        sys.exit(1)

    config_path = os.path.join("config", f"{action}.yml")
    if not os.path.exists(config_path):
        print("\nRun from project root or run: qwop-python bootstrap\n")
        sys.exit(1)


def run_bootstrap():
    """Create config/ in CWD with templates from the package."""
    config_dir = os.path.join(os.getcwd(), "config")
    os.makedirs(config_dir, exist_ok=True)
    templates = (
        "env.yml",
        "train_ppo.yml",
        "train_qrdqn.yml",
        "train_a2c.yml",
        "train_dqn.yml",
        "train_rppo.yml",
    )
    pkg = importlib.resources.files("qwop_python.tools.templates")
    for name in templates:
        content = (pkg / name).read_text()
        path = os.path.join(config_dir, name)
        with open(path, "w") as f:
            f.write(content)
    print("Created config/ with %s" % ", ".join(templates))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", help=argparse.SUPPRESS)
    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        dest="config_file",
        type=str,
        default=None,
        help="config file, defaults to config/<action>.yml",
    )
    parser.add_argument("--run-id", type=str, help="run id (train_*)")

    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.usage = "%(prog)s [options] <action>"
    parser.epilog = """
action:
  bootstrap         create config/ with templates
  play              interactive gameplay
  train_ppo         train using PPO
  train_dqn         train using DQN
  train_qrdqn       train using QRDQN
  train_rppo        train using RPPO
  train_a2c         train using A2C

examples:
  %(prog)s bootstrap
  %(prog)s play
  %(prog)s train_ppo
"""

    args = parser.parse_args()

    if args.action == "bootstrap":
        run_bootstrap()
        return

    if args.action == "play":
        run(args.action, {})
        return

    cli_overrides = {
        "config_file": args.config_file,
        "run_id": args.run_id,
    }

    ensure_bootstrapped(parser.prog, args.action)

    if args.config_file is not None:
        config_path = args.config_file
    else:
        config_path = os.path.join("config", f"{args.action}.yml")

    print("Loading configuration from %s" % config_path)
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    if args.run_id is not None:
        cfg["run_id"] = args.run_id

    run(args.action, cfg, cli_overrides)


if __name__ == "__main__":
    main()
