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

    if action == "evaluate":
        ensure_sb3_installed()
        from .evaluate import run_evaluate
        model = cli_overrides.get("model") or cfg.get("model_file")
        if not model:
            print("Error: --model or config with model_file required")
            sys.exit(1)
        run_evaluate(
            model_path=model,
            n_episodes=cli_overrides.get("episodes") or cfg.get("n_episodes", 100),
            seed=cli_overrides.get("seed") or cfg.get("seed", 42),
            render=cli_overrides.get("render", False) or cfg.get("render", False),
            max_episode_steps=cfg.get("max_episode_steps", 1000),
            frames_per_step=cfg.get("env_kwargs", {}).get("frames_per_step", 4),
            reduced_action_set=cfg.get("env_kwargs", {}).get("reduced_action_set", True),
            output_dir=cli_overrides.get("output") or cfg.get("output_dir"),
            algorithm=cli_overrides.get("algo") or cfg.get("algorithm"),
        )
        return

    if action == "collect_demos":
        ensure_sb3_installed()
        from .collect_demos import run_collect_demos
        model = cli_overrides.get("model") or cfg.get("model_file")
        if not model:
            print("Error: --model or config with model_file required")
            sys.exit(1)
        env_kwargs = cfg.get("env_kwargs", {})
        run_collect_demos(
            model_path=model,
            out_file=cli_overrides.get("output") or cfg.get("out_file", "data/demonstrations/demos.npz"),
            n_episodes=cli_overrides.get("episodes") or cfg.get("n_episodes", 50),
            seed_start=cfg.get("seed_start", 10000),
            max_episode_steps=cfg.get("max_episode_steps", 1000),
            **env_kwargs,
        )
        return

    if action == "train":
        ensure_sb3_installed()
        config_path = cli_overrides.get("config_file")
        if not config_path:
            print("Error: train action requires -c config/file.yml")
            sys.exit(1)
        with open(config_path, "r") as f:
            train_cfg = yaml.safe_load(f)
        if "algorithm" not in train_cfg:
            print("Use train_ppo, train_qrdqn, etc. for tools config; or train -c config/train_qrdqn_single.yml")
            sys.exit(1)
        from .train_standalone import run_train_standalone
        run_train_standalone(
            config_path=config_path,
            run_id=cli_overrides.get("run_id", "default"),
            resume_from=cli_overrides.get("resume_from"),
        )
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
                "learner_lr_schedule": cfg.get("learner_lr_schedule", "const_0.003"),
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
    except ImportError:
        print(
            """
To use this feature, install stable_baselines3 and sb3-contrib:

    pip install stable_baselines3 sb3-contrib
"""
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
    templates = ("env.yml", "train_ppo.yml", "train_qrdqn.yml", "collect_demos.yml", "evaluate.yml")
    pkg = importlib.resources.files("qwop_python.tools.templates")
    for name in templates:
        content = (pkg / name).read_text()
        path = os.path.join(config_dir, name)
        with open(path, "w") as f:
            f.write(content)
    print("Created config/ with env.yml, train_ppo.yml, train_qrdqn.yml, collect_demos.yml, evaluate.yml")


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
    parser.add_argument("--model", type=str, help="model path (evaluate, collect_demos)")
    parser.add_argument("--episodes", type=int, help="episodes (evaluate, collect_demos)")
    parser.add_argument("--output", type=str, help="output path or dir (evaluate, collect_demos)")
    parser.add_argument("--render", action="store_true", help="render evaluation")
    parser.add_argument("--run-id", type=str, default="default", help="run id (train)")
    parser.add_argument("--resume-from", type=str, help="checkpoint to resume (train)")
    parser.add_argument("--seed", type=int, help="random seed (evaluate)")
    parser.add_argument("--algo", type=str, help="algorithm override (evaluate)")

    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.usage = "%(prog)s [options] <action>"
    parser.epilog = """
action:
  bootstrap         create config/ with templates
  play              interactive gameplay
  evaluate          evaluate trained model (--model or -c required)
  collect_demos     collect expert demos for DQNfD (--model or -c required)
  train             train with standalone config (-c required, e.g. train_qrdqn_single.yml)
  train_ppo         train using PPO
  train_dqn         train using DQN
  train_qrdqn       train using QRDQN
  train_rppo        train using RPPO
  train_a2c         train using A2C

examples:
  %(prog)s bootstrap
  %(prog)s play
  %(prog)s evaluate --model data/models/QRDQN_*/final_model.zip --episodes 50
  %(prog)s collect_demos -c config/collect_demos.yml
  %(prog)s train -c config/train_qrdqn_single.yml
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
        "model": args.model,
        "episodes": args.episodes,
        "output": args.output,
        "render": args.render,
        "run_id": args.run_id,
        "resume_from": args.resume_from,
        "seed": args.seed,
        "algo": args.algo,
    }

    if args.action in ("evaluate", "collect_demos"):
        if args.model:
            cfg = {}
        elif args.config_file and os.path.exists(args.config_file):
            with open(args.config_file, "r") as f:
                cfg = yaml.safe_load(f) or {}
        else:
            config_path = os.path.join("config", f"{args.action}.yml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
            else:
                print("\nRun from project root or run: qwop-python bootstrap\n")
                print("Or use --model for evaluate, or --model and --output for collect_demos")
                sys.exit(1)
        run(args.action, cfg, cli_overrides)
        return

    if args.action == "train":
        config_path = args.config_file or os.path.join("config", "train_qrdqn_single.yml")
        if not os.path.exists(config_path):
            print("Error: train requires -c config/file.yml (e.g. -c config/train_qrdqn_single.yml)")
            sys.exit(1)
        cli_overrides["config_file"] = config_path
        run(args.action, {}, cli_overrides)
        return

    ensure_bootstrapped(parser.prog, args.action)

    if args.config_file is not None:
        config_path = args.config_file
    else:
        config_path = os.path.join("config", f"{args.action}.yml")

    print("Loading configuration from %s" % config_path)
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    run(args.action, cfg, cli_overrides)


if __name__ == "__main__":
    main()
