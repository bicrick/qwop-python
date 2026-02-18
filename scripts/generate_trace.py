"""
Generate action traces for behavior comparison.

Produces JSON trace files with either fixed or random action sequences.
"""

import argparse
import json
import os
import random
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from action_bridge import ACTION_CMDFLAGS_REDUCED


def generate_fixed(length, pattern="noop"):
    """
    Generate a fixed pattern of actions.

    Args:
        length: Number of steps.
        pattern: "noop" (all 0), "q" (all Q), "alternate" (0,Q,0,Q,...), "cycle" (0,1,2,...,8,0,1,...).

    Returns:
        List of action indices.
    """
    n_actions = len(ACTION_CMDFLAGS_REDUCED)
    if pattern == "noop":
        return [0] * length
    if pattern == "q":
        return [1] * length  # Q is action 1 in reduced set
    if pattern == "alternate":
        return [0, 1] * (length // 2) + [0] * (length % 2)
    if pattern == "cycle":
        return [i % n_actions for i in range(length)]
    raise ValueError(f"Unknown pattern: {pattern}")


def generate_random(length, seed=None):
    """Generate random action sequence (reduced set)."""
    rng = random.Random(seed)
    n = len(ACTION_CMDFLAGS_REDUCED)
    return [rng.randint(0, n - 1) for _ in range(length)]


def main():
    parser = argparse.ArgumentParser(
        description="Generate action traces for comparison"
    )
    parser.add_argument(
        "--length",
        type=int,
        default=100,
        help="Number of steps",
    )
    parser.add_argument(
        "--pattern",
        choices=["noop", "q", "alternate", "cycle", "random"],
        default="noop",
        help="Trace pattern",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for random or for trace metadata",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON path",
    )
    parser.add_argument(
        "--frames-per-step",
        type=int,
        default=4,
        help="Physics steps per action (default 4, matches DQNfD training)",
    )
    args = parser.parse_args()

    if args.pattern == "random":
        actions = generate_random(args.length, seed=args.seed)
    else:
        actions = generate_fixed(args.length, args.pattern)

    trace = {
        "actions": actions,
        "seed": args.seed,
        "pattern": args.pattern,
        "length": len(actions),
        "frames_per_step": args.frames_per_step,
        "reduced_action_set": True,
    }

    out_path = args.output
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(trace, f, indent=2)

    print(f"Wrote {len(actions)} actions to {out_path}")


if __name__ == "__main__":
    main()
