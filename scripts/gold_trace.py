#!/usr/bin/env python3
"""
Generate or compare gold traces for qwop-python vs qwop-gym parity.

Usage:
  # Generate a gold trace from qwop-python (save to tests/fixtures/)
  python scripts/gold_trace.py generate --seed 42 --frames-per-step 4 --steps 100 --out tests/fixtures/gold_trace_seed42_fps4.json

  # Compare current qwop-python run to an existing gold file
  python scripts/gold_trace.py compare --gold tests/fixtures/gold_trace_seed42_fps4.json

Gold trace format: JSON with seed, frames_per_step, reduced_action_set, reward_dt_mode, steps[]
each step: action, obs (list), reward, terminated, truncated, info (time, distance, avgspeed, is_success).
"""

import argparse
import json
import sys

import numpy as np

# Run from project root (or scripts/) so qwop_python is importable
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)
from qwop_python import QWOPEnv


def generate(seed, frames_per_step, steps, out_path, reduced_action_set=True, reward_dt_mode="protocol_30hz"):
    env = QWOPEnv(
        seed=seed,
        frames_per_step=frames_per_step,
        reduced_action_set=reduced_action_set,
        reward_dt_mode=reward_dt_mode,
    )
    obs, info = env.reset(seed=seed)
    trace = {
        "seed": seed,
        "frames_per_step": frames_per_step,
        "reduced_action_set": reduced_action_set,
        "reward_dt_mode": reward_dt_mode,
        "steps": [],
    }
    for t in range(steps):
        action = int(np.random.default_rng(seed + t).integers(0, env.action_space.n))
        obs, reward, terminated, truncated, info = env.step(action)
        step_data = {
            "action": action,
            "obs": obs.tolist(),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "info": {
                "time": float(info.get("time", 0)),
                "distance": float(info.get("distance", 0)),
                "avgspeed": float(info.get("avgspeed", 0)),
                "is_success": float(info.get("is_success", 0)),
            },
        }
        trace["steps"].append(step_data)
        if terminated or truncated:
            break
    env.close()
    with open(out_path, "w") as f:
        json.dump(trace, f, indent=2)
    print(f"Wrote {len(trace['steps'])} steps to {out_path}")


def compare(gold_path, rtol=1e-3, atol=1e-5):
    with open(gold_path) as f:
        gold = json.load(f)
    env = QWOPEnv(
        seed=gold["seed"],
        frames_per_step=gold["frames_per_step"],
        reduced_action_set=gold.get("reduced_action_set", True),
        reward_dt_mode=gold.get("reward_dt_mode", "protocol_30hz"),
    )
    obs, _ = env.reset(seed=gold["seed"])
    errors = []
    for i, gs in enumerate(gold["steps"]):
        action = gs["action"]
        obs, reward, terminated, truncated, info = env.step(action)
        if not np.allclose(obs, np.array(gs["obs"]), rtol=rtol, atol=atol):
            errors.append(f"Step {i}: obs mismatch")
        if not np.isclose(reward, gs["reward"], rtol=rtol, atol=atol):
            errors.append(f"Step {i}: reward {reward} vs gold {gs['reward']}")
        if terminated != gs["terminated"] or truncated != gs["truncated"]:
            errors.append(f"Step {i}: done mismatch")
        for k in ("time", "distance", "avgspeed", "is_success"):
            if k in gs["info"] and not np.isclose(info.get(k, 0), gs["info"][k], rtol=rtol, atol=atol):
                errors.append(f"Step {i}: info[{k}] mismatch")
        if terminated or truncated:
            break
    env.close()
    if errors:
        for e in errors:
            print(e)
        sys.exit(1)
    print(f"OK: {len(gold['steps'])} steps match gold (rtol={rtol}, atol={atol})")


def main():
    p = argparse.ArgumentParser(description="Generate or compare gold traces for parity testing")
    sub = p.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--frames-per-step", type=int, default=4)
    gen.add_argument("--steps", type=int, default=100)
    gen.add_argument("--out", required=True, help="Output JSON path")
    gen.add_argument("--reduced-action-set", action="store_true", default=True)
    gen.add_argument("--reward-dt-mode", default="protocol_30hz")
    cmp = sub.add_parser("compare")
    cmp.add_argument("--gold", required=True, help="Path to gold trace JSON")
    cmp.add_argument("--rtol", type=float, default=1e-3)
    cmp.add_argument("--atol", type=float, default=1e-5)
    args = p.parse_args()
    if args.cmd == "generate":
        generate(
            seed=args.seed,
            frames_per_step=args.frames_per_step,
            steps=args.steps,
            out_path=args.out,
            reduced_action_set=args.reduced_action_set,
            reward_dt_mode=args.reward_dt_mode,
        )
    else:
        compare(args.gold, rtol=args.rtol, atol=args.atol)


if __name__ == "__main__":
    main()
