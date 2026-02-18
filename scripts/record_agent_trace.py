"""
Record an action trace by running a trained model on the reference qwop-wr env.

Saves a JSON trace compatible with compare_trajectories.py.
Requires Python 3.10+ (qwop-wr uses match statement).
Model path can be absolute or relative to QWOP_WR_PATH.

Run from qwop-wr so cwd is on path:
  cd /path/to/qwop-wr
  python /path/to/qwop-python/scripts/record_agent_trace.py data/DQNfD-Stage1-vzqtwzx4/model.zip -o ../qwop-python/scripts/traces/dqnfd_trace.json
"""

import argparse
import json
import os
import sys

# Add qwop-wr for env and model loading
_qwop_wr = os.environ.get("QWOP_WR_PATH", "/Users/b407404/Desktop/Misc/qwop-wr")
if os.path.isdir(_qwop_wr):
    sys.path.insert(0, _qwop_wr)

# Add qwop-python project paths
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _patch_sb3_schedule_compat():
    """
    Patch stable_baselines3.common.utils with FloatSchedule/LinearSchedule if missing.
    Models saved with newer SB3 (2.6+) reference these; older SB3 lacks them.
    """
    import stable_baselines3.common.utils as sb3_utils

    if hasattr(sb3_utils, "FloatSchedule"):
        return

    class ConstantSchedule:
        def __init__(self, val):
            self.val = float(val)

        def __call__(self, progress_remaining):
            return self.val

    class LinearSchedule:
        def __init__(self, start, end, end_fraction=0.1):
            self.start = float(start)
            self.end = float(end)
            self.end_fraction = float(end_fraction)

        def __call__(self, progress_remaining):
            if (1 - progress_remaining) >= self.end_fraction:
                return self.end
            return self.start + (1 - progress_remaining) * (
                self.end - self.start
            ) / self.end_fraction

    class FloatSchedule:
        def __init__(self, value_schedule):
            if isinstance(value_schedule, (float, int)):
                self.value_schedule = ConstantSchedule(float(value_schedule))
            else:
                self.value_schedule = value_schedule

        def __call__(self, progress_remaining):
            return float(self.value_schedule(progress_remaining))

    sb3_utils.ConstantSchedule = ConstantSchedule
    sb3_utils.LinearSchedule = LinearSchedule
    sb3_utils.FloatSchedule = FloatSchedule


def _resolve_model_path(path):
    """Resolve model path; if relative, try under qwop-wr."""
    if os.path.isabs(path):
        return path
    # Try cwd first
    if os.path.isfile(path):
        return os.path.abspath(path)
    # Try under qwop-wr
    full = os.path.join(_qwop_wr, path)
    if os.path.isfile(full):
        return full
    return os.path.abspath(path)


def _load_model(model_path, model_cls=None):
    """Load model, trying EQRDQN, QRDQN, DQN in that order if cls not specified."""
    _patch_sb3_schedule_compat()
    model_path = _resolve_model_path(model_path)
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    import importlib

    if model_cls:
        mod_map = {
            "EQRDQN": ("qwop_gym.algorithms", "EnhancedQRDQN"),
            "QRDQN": ("sb3_contrib", "QRDQN"),
            "DQN": ("stable_baselines3", "DQN"),
        }
        mod_name, cls_name = mod_map[model_cls.upper()]
        mod = importlib.import_module(mod_name)
        return getattr(mod, cls_name).load(model_path)

    # Auto-detect: try EQRDQN first (DQNfD models)
    for mod_name, cls_name in [
        ("qwop_gym.algorithms", "EnhancedQRDQN"),
        ("sb3_contrib", "QRDQN"),
        ("stable_baselines3", "DQN"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            model = getattr(mod, cls_name).load(model_path)
            print(f"Loaded {cls_name} from {model_path}")
            return model
        except Exception as e:
            continue
    raise RuntimeError(
        f"Could not load model from {model_path}. "
        "Try --model-cls EQRDQN|QRDQN|DQN"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Record agent trace from trained model for behavior comparison"
    )
    parser.add_argument(
        "model",
        help="Path to model.zip (absolute or relative to QWOP_WR_PATH)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="scripts/traces/agent_trace.json",
        help="Output trace JSON path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Environment seed",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=2000,
        help="Max steps (cap episode length)",
    )
    parser.add_argument(
        "--model-cls",
        choices=["EQRDQN", "QRDQN", "DQN"],
        default=None,
        help="Model class (auto-detect if not set)",
    )
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="Only load model and exit (no env, for testing)",
    )
    args = parser.parse_args()

    if args.load_only:
        model = _load_model(args.model, args.model_cls)
        print("Model loaded successfully")
        return

    import gymnasium as gym
    import yaml

    from qwop_gym.tools import common

    model = _load_model(args.model, args.model_cls)

    env_kwargs = {
        "frames_per_step": 4,
        "reduced_action_set": True,
        "auto_draw": False,
        "stat_in_browser": False,
        "game_in_browser": False,
    }
    env_cfg = os.path.join(_qwop_wr, "config", "env.yml")
    if os.path.isfile(env_cfg):
        with open(env_cfg) as f:
            base = yaml.safe_load(f)
        for k, v in base.items():
            if k not in env_kwargs:
                env_kwargs[k] = v

    common.register_env(env_kwargs, [])

    env = gym.make("local/QWOP-v1", seed=args.seed)
    env.reset()
    env.reset()
    obs, info = env.reset(seed=args.seed)

    actions = []
    terminated = False
    step = 0

    while not terminated and step < args.max_steps:
        action, _ = model.predict(obs, deterministic=True)
        actions.append(int(action))
        obs, reward, terminated, truncated, info = env.step(action)
        step += 1

    env.close()

    trace = {
        "actions": actions,
        "seed": args.seed,
        "model": args.model,
        "length": len(actions),
        "frames_per_step": 4,
        "reduced_action_set": True,
        "final_distance": float(info["distance"]),
        "success": bool(info["is_success"]),
    }

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(trace, f, indent=2)

    print(f"Recorded {len(actions)} actions to {out_path}")
    print(f"  Seed: {args.seed}, Distance: {info['distance']:.1f}m, Success: {info['is_success']}")


if __name__ == "__main__":
    main()
