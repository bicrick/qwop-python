"""
Replay an action trace (e.g. from reference) through the Python env only.

Useful to verify: if the reference's actions work on Python physics,
the issue is observation/model. If they don't, the issue is physics.
"""
import argparse
import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_python_env import run_python_env


def main():
    parser = argparse.ArgumentParser(description="Replay trace through Python env")
    parser.add_argument("trace", help="Path to trace JSON")
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()

    with open(args.trace) as f:
        data = json.load(f)
    actions = data["actions"]
    seed = data.get("seed", 42)
    frames_per_step = data.get("frames_per_step", 4)
    reduced = data.get("reduced_action_set", True)

    if args.max_steps:
        actions = actions[: args.max_steps]

    traj = list(
        run_python_env(actions, reduced=reduced, frames_per_step=frames_per_step, quiet=True)
    )
    if traj:
        _, final_score, game_over = traj[-1]
        print(f"Replayed {len(traj)} steps")
        print(f"  Final distance: {final_score:.1f}m")
        print(f"  Game over: {game_over}")
        print(f"  (Trace was from {'reference' if 'source' not in data else data.get('source', '?')})")
    else:
        print("No steps executed")


if __name__ == "__main__":
    main()
