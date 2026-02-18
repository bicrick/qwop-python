"""
Compare trajectories between qwop-python and qwop-wr reference environment.

Runs identical action traces through both envs and reports differences.
"""

import argparse
import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from state_extractor import OBS_PARTS
from run_python_env import run_python_env
from run_reference_env import run_reference_env
from action_bridge import action_to_keys, key_sequence_to_actions


def load_trace(path):
    """Load action trace from JSON file. Returns (actions, seed, reduced, frames_per_step)."""
    with open(path) as f:
        data = json.load(f)
    seed = data.get("seed", 42)
    frames_per_step = data.get("frames_per_step", 4)
    reduced = data.get("reduced_action_set", True)
    if "actions" in data:
        return data["actions"], seed, reduced, frames_per_step
    if "key_sequences" in data:
        actions = key_sequence_to_actions(data["key_sequences"])
        return actions, seed, reduced, frames_per_step
    raise ValueError("Trace must have 'actions' or 'key_sequences'")


def compute_diffs(py_state, ref_state, tol_pos, tol_vel):
    """Compute per-body, per-channel differences and check tolerances."""
    assert py_state.shape == ref_state.shape == (60,)
    diffs = []
    max_pos_diff = 0.0
    max_vel_diff = 0.0
    pos_ok = True
    vel_ok = True
    for i in range(12):
        base = i * 5
        px, py, pa, pvx, pvy = py_state[base : base + 5]
        rx, ry, ra, rvx, rvy = ref_state[base : base + 5]
        dx = abs(px - rx)
        dy = abs(py - ry)
        da = abs(pa - ra)
        dvx = abs(pvx - rvx)
        dvy = abs(pvy - rvy)
        max_pos_diff = max(max_pos_diff, dx, dy, da)
        max_vel_diff = max(max_vel_diff, dvx, dvy)
        pos_ok = pos_ok and dx <= tol_pos and dy <= tol_pos and da <= tol_pos
        vel_ok = vel_ok and dvx <= tol_vel and dvy <= tol_vel
        diffs.append(
            {
                "part": OBS_PARTS[i],
                "pos": (dx, dy, da),
                "vel": (dvx, dvy),
            }
        )
    return diffs, max_pos_diff, max_vel_diff, pos_ok, vel_ok


def run_comparison(
    trace_path,
    seed=42,
    tol_position=1e-3,
    tol_velocity=1e-2,
    max_steps=200,
    verbose=True,
    use_reference=True,
):
    """
    Run both envs and compare trajectories.

    Args:
        trace_path: Path to JSON trace file.
        seed: Seed for reference env.
        tol_position: Max acceptable diff for pos/angle.
        tol_velocity: Max acceptable diff for velocities.
        max_steps: Cap steps per env.
        verbose: Print per-step diffs when exceeded.
        use_reference: If False, skip reference env (Python-only check).

    Returns:
        dict with keys: passed, first_divergence_step, max_pos_diff, max_vel_diff,
        py_steps, ref_steps, score_diff, done_mismatch.
    """
    actions, trace_seed, reduced, frames_per_step = load_trace(trace_path)
    seed = seed if seed is not None else trace_seed
    actions = actions[:max_steps]

    py_traj = list(
        run_python_env(
            actions, reduced=reduced, frames_per_step=frames_per_step, quiet=True
        )
    )
    if use_reference:
        try:
            ref_traj = list(
                run_reference_env(
                    actions,
                    seed=seed,
                    reduced=reduced,
                    frames_per_step=frames_per_step,
                    quiet=True,
                )
            )
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "py_steps": len(py_traj),
                "ref_steps": 0,
            }
    else:
        ref_traj = []

    result = {
        "passed": True,
        "first_divergence_step": None,
        "max_pos_diff": 0.0,
        "max_vel_diff": 0.0,
        "py_steps": len(py_traj),
        "ref_steps": len(ref_traj),
        "score_diff": None,
        "done_mismatch": None,
    }

    if not use_reference:
        return result

    n = min(len(py_traj), len(ref_traj))
    for step in range(n):
        py_state, py_score, py_done = py_traj[step]
        ref_state, ref_score, ref_done = ref_traj[step]
        diffs, mx_pos, mx_vel, pos_ok, vel_ok = compute_diffs(
            py_state, ref_state, tol_position, tol_velocity
        )
        result["max_pos_diff"] = max(result["max_pos_diff"], mx_pos)
        result["max_vel_diff"] = max(result["max_vel_diff"], mx_vel)
        if not pos_ok or not vel_ok:
            result["passed"] = False
            if result["first_divergence_step"] is None:
                result["first_divergence_step"] = step
            if verbose:
                print(
                    f"Step {step}: pos_diff={mx_pos:.6f} vel_diff={mx_vel:.6f} "
                    f"(tol_pos={tol_position} tol_vel={tol_velocity})"
                )
                for d in diffs:
                    if max(d["pos"]) > tol_position or max(d["vel"]) > tol_velocity:
                        print(f"  {d['part']}: pos={d['pos']} vel={d['vel']}")
        if py_done != ref_done:
            result["done_mismatch"] = (step, py_done, ref_done)
            result["passed"] = False

    if n > 0:
        py_final = py_traj[n - 1]
        ref_final = ref_traj[n - 1]
        result["score_diff"] = abs(py_final[1] - ref_final[1])

    if len(py_traj) != len(ref_traj):
        result["passed"] = False

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compare qwop-python vs reference env trajectories"
    )
    parser.add_argument(
        "--trace",
        required=True,
        help="Path to JSON trace (actions or key_sequences)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for reference env (default: from trace)",
    )
    parser.add_argument(
        "--tol-position",
        type=float,
        default=1e-3,
        help="Tolerance for position/angle diff",
    )
    parser.add_argument(
        "--tol-velocity",
        type=float,
        default=1e-2,
        help="Tolerance for velocity diff",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=200,
        help="Max steps per env",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Run Python env only (no reference comparison)",
    )
    args = parser.parse_args()

    result = run_comparison(
        args.trace,
        seed=args.seed,
        tol_position=args.tol_position,
        tol_velocity=args.tol_velocity,
        max_steps=args.max_steps,
        verbose=not args.quiet,
        use_reference=not args.python_only,
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(2)

    if args.quiet:
        print("PASS" if result["passed"] else "FAIL")
    else:
        print("\n" + "=" * 60)
        print("COMPARISON RESULT")
        print("=" * 60)
        print(f"Python steps: {result['py_steps']}")
        if result["ref_steps"]:
            print(f"Reference steps: {result['ref_steps']}")
            print(f"Max position diff: {result['max_pos_diff']:.6f}")
            print(f"Max velocity diff: {result['max_vel_diff']:.6f}")
            if result["score_diff"] is not None:
                print(f"Final score diff: {result['score_diff']:.6f}")
            if result["first_divergence_step"] is not None:
                print(f"First divergence: step {result['first_divergence_step']}")
            if result["done_mismatch"]:
                s, pd, rd = result["done_mismatch"]
                print(f"Done mismatch at step {s}: py={pd} ref={rd}")
        print("=" * 60)
        print("PASS" if result["passed"] else "FAIL")
        print("=" * 60)

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
