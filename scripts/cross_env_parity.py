#!/usr/bin/env python3
"""
Cross-env parity: run same seed + actions in qwop-gym (browser) and qwop-python, compare step-by-step.

Requires qwop-gym installed and Chrome + chromedriver. Exit 0 only if within tolerance.

Usage:
  python scripts/cross_env_parity.py --browser /path/to/chrome --driver /path/to/chromedriver [--seed 42] [--steps 80]
  Add --verbose to print reward and info (time, distance, avgspeed) each step for both envs (gym vs py).
  Add --backend js to use the JS (Planck/PyMiniRacer) backend for qwop-python instead of PyBox2D.
"""

import argparse
import os
import sys

import numpy as np

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Relaxed for cross-env: browser Box2D vs PyBox2D/Planck; divergence compounds over steps
CROSS_RTOL = 2e-2
CROSS_ATOL = 1e-1
# JS backend: browser Box2D vs Planck.js are different engines; allow larger obs drift per step (divergence compounds)
CROSS_ATOL_JS = 3e-1
# Reward and info floats diverge when trajectory diverges; use looser tolerance
REWARD_RTOL = 5e-1
REWARD_ATOL = 1e-1
INFO_RTOL = 5e-1
INFO_ATOL = 1e-1


def _obs_diagnostics(obs_g, obs_p, label="obs"):
    """Print diagnostics when obs mismatch (shape, max diff, sample)."""
    diff = np.asarray(obs_g, dtype=np.float64) - np.asarray(obs_p, dtype=np.float64)
    abs_diff = np.abs(diff)
    err = sys.stderr
    print(f"  {label} shape gym={np.shape(obs_g)} py={np.shape(obs_p)}", file=err)
    print(f"  {label} max_abs_diff={float(np.max(abs_diff)):.6e} mean_abs_diff={float(np.mean(abs_diff)):.6e}", file=err)
    print(f"  {label} gym[:5]={np.asarray(obs_g).ravel()[:5]}", file=err)
    print(f"  {label} py[:5] ={np.asarray(obs_p).ravel()[:5]}", file=err)


def main():
    p = argparse.ArgumentParser(description="Cross-env parity: qwop-gym vs qwop-python")
    p.add_argument("--browser", required=True, help="Path to Chrome (or Chromium) executable")
    p.add_argument("--driver", required=True, help="Path to chromedriver executable")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--steps", type=int, default=80, help="Max steps (and action list length)")
    p.add_argument("--frames-per-step", type=int, default=4)
    p.add_argument("--verbose", "-v", action="store_true", help="Print reward and info (time, distance, avgspeed) each step for both envs")
    p.add_argument("--backend", choices=("pybox2d", "js"), default="pybox2d", help="qwop-python backend: pybox2d (default) or js (Planck/PyMiniRacer)")
    args = p.parse_args()

    try:
        from qwop_gym.envs.v1.qwop_env import QwopEnv as QwopEnvGym
    except ImportError:
        print("Error: qwop-gym not installed. pip install -e /path/to/qwop-gym", file=sys.stderr)
        sys.exit(2)

    from qwop_python import QWOPEnv as QWOPEnvPython

    seed = args.seed
    frames_per_step = args.frames_per_step
    max_steps = args.steps
    actions = [0, 1, 2, 0, 1, 0, 2, 1] * (max_steps // 8 + 1)
    actions = actions[:max_steps]

    env_gym = None
    env_py = None
    try:
        env_gym = QwopEnvGym(
            browser=args.browser,
            driver=args.driver,
            seed=seed,
            frames_per_step=frames_per_step,
            reduced_action_set=True,
            game_in_browser=False,
            t_for_terminate=False,
        )
        env_py = QWOPEnvPython(
            seed=seed,
            frames_per_step=frames_per_step,
            reduced_action_set=True,
            reward_dt_mode="protocol_30hz",
            backend=args.backend,
        )

        obs_g, _ = env_gym.reset(seed=seed)
        obs_p, _ = env_py.reset(seed=seed)

        obs_atol = CROSS_ATOL_JS if args.backend == "js" else CROSS_ATOL
        if not np.allclose(obs_g, obs_p, rtol=CROSS_RTOL, atol=obs_atol):
            print("FAIL: initial obs mismatch", file=sys.stderr)
            _obs_diagnostics(obs_g, obs_p, "initial_obs")
            sys.exit(1)

        for step in range(len(actions)):
            action = actions[step]
            obs_g, r_g, term_g, trunc_g, info_g = env_gym.step(action)
            obs_p, r_p, term_p, trunc_p, info_p = env_py.step(action)

            if args.verbose:
                t_g = info_g.get("time", None)
                t_p = info_p.get("time", None)
                d_g = info_g.get("distance", None)
                d_p = info_p.get("distance", None)
                a_g = info_g.get("avgspeed", None)
                a_p = info_p.get("avgspeed", None)
                print(f"step {step} action={action} reward gym={r_g} py={r_p}  time gym={t_g} py={t_p}  dist gym={d_g} py={d_p}  avgspeed gym={a_g} py={a_p}")

            if not np.allclose(obs_g, obs_p, rtol=CROSS_RTOL, atol=obs_atol):
                print(f"FAIL: step {step} obs mismatch", file=sys.stderr)
                _obs_diagnostics(obs_g, obs_p, f"step{step}_obs")
                sys.exit(1)
            if not np.isclose(r_g, r_p, rtol=REWARD_RTOL, atol=REWARD_ATOL):
                print(f"FAIL: step {step} reward gym={r_g} py={r_p} (diff={float(r_g)-float(r_p):.6e})", file=sys.stderr)
                sys.exit(1)
            if term_g != term_p or trunc_g != trunc_p:
                print(f"FAIL: step {step} done mismatch gym=({term_g},{trunc_g}) py=({term_p},{trunc_p})", file=sys.stderr)
                sys.exit(1)

            for key in ("time", "distance", "avgspeed"):
                if key in info_g and key in info_p:
                    if not np.isclose(info_g[key], info_p[key], rtol=INFO_RTOL, atol=INFO_ATOL):
                        print(f"FAIL: step {step} info[{key}] {info_g[key]} vs {info_p[key]}", file=sys.stderr)
                        sys.exit(1)
            if "is_success" in info_g and "is_success" in info_p:
                if info_g["is_success"] != info_p["is_success"]:
                    print(f"FAIL: step {step} info[is_success] {info_g['is_success']} vs {info_p['is_success']}", file=sys.stderr)
                    sys.exit(1)

            if term_g or trunc_g:
                break

        print(f"OK: {step + 1} steps matched (obs, reward, done, info within tolerance: obs rtol={CROSS_RTOL} atol={obs_atol}; reward rtol={REWARD_RTOL} atol={REWARD_ATOL})")
    finally:
        if env_gym is not None:
            env_gym.close()
        if env_py is not None:
            env_py.close()


if __name__ == "__main__":
    main()
