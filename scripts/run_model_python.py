"""
Run a trained model against the qwop-python Gym env.

Loads the model (DQNfD, QRDQN, etc.) and plays it on the Python physics
implementation. Records trace and prints results.
"""

import argparse
import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# SB3 schedule compat for older versions
from record_agent_trace import _patch_sb3_schedule_compat

_qwop_wr = os.environ.get("QWOP_WR_PATH", "/Users/b407404/Desktop/Misc/qwop-wr")
if os.path.isdir(_qwop_wr):
    sys.path.insert(0, _qwop_wr)


def _load_model(model_path, model_cls=None):
    _patch_sb3_schedule_compat()

    if not os.path.isabs(model_path):
        for base in [os.getcwd(), _qwop_wr]:
            full = os.path.join(base, model_path)
            if os.path.isfile(full):
                model_path = full
                break
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    import importlib
    mod_map = {
        "EQRDQN": ("qwop_gym.algorithms", "EnhancedQRDQN"),
        "QRDQN": ("sb3_contrib", "QRDQN"),
        "DQN": ("stable_baselines3", "DQN"),
    }
    order = [
        ("qwop_gym.algorithms", "EnhancedQRDQN"),
        ("sb3_contrib", "QRDQN"),
        ("stable_baselines3", "DQN"),
    ]
    if model_cls and model_cls.upper() in mod_map:
        order = [mod_map[model_cls.upper()]] + [x for x in order if x != mod_map[model_cls.upper()]]
    for mod_name, cls_name in order:
        try:
            mod = importlib.import_module(mod_name)
            model = getattr(mod, cls_name).load(model_path)
            print(f"Loaded {cls_name} from {model_path}")
            return model
        except Exception:
            continue
    raise RuntimeError(f"Could not load model from {model_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run trained model on qwop-python Gym env"
    )
    parser.add_argument("model", help="Path to model.zip")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Save trace JSON to this path",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument(
        "--steps-per-step",
        type=int,
        default=4,
        help="Number of env.step() calls per model action (match OG evaluate)",
    )
    parser.add_argument("--model-cls", choices=["EQRDQN", "QRDQN", "DQN"], default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print first few obs/actions")
    args = parser.parse_args()

    from qwop_gym_env import QWOPPythonEnv

    model = _load_model(args.model, args.model_cls)
    env = QWOPPythonEnv(
        frames_per_step=4,  # Match DQNfD training
        reduced_action_set=True,  # 9 actions: none, Q, W, O, P, QW, QP, WO, OP
    )

    obs, info = env.reset(seed=args.seed)
    actions = []
    terminated = False
    step = 0

    if args.verbose:
        print(f"Initial obs: mean={obs.mean():.3f} std={obs.std():.3f} min={obs.min():.3f} max={obs.max():.3f}")
        print(f"  torso (first 5): {obs[:5]}")

    while not terminated and step < args.max_steps:
        action, _ = model.predict(obs, deterministic=True)
        actions.append(int(action))
        if args.verbose and step < 5:
            print(f"Step {step}: action={action} dist={info['distance']:.2f}")
        for _ in range(args.steps_per_step):
            obs, reward, terminated, truncated, info = env.step(action)
            if terminated:
                break
        step += 1
    env.close()

    print(f"\nPython env run completed:")
    print(f"  Steps: {len(actions)}")
    print(f"  Distance: {info['distance']:.1f}m")
    print(f"  Success: {info['is_success']}")

    if args.output:
        trace = {
            "actions": actions,
            "seed": args.seed,
            "model": args.model,
            "source": "python",
            "length": len(actions),
            "frames_per_step": 4,
            "steps_per_step": args.steps_per_step,
            "reduced_action_set": True,
            "final_distance": float(info["distance"]),
            "success": bool(info["is_success"]),
        }
        out = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w") as f:
            json.dump(trace, f, indent=2)
        print(f"  Saved trace to {out}")


if __name__ == "__main__":
    main()
