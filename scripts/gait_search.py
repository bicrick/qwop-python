"""Parameterized open-loop QWOP stride inferred from kurodo timeline, not timestamps.

Steady long-cycle mode (Q-rise aligned, median period ~1.77s video/HUD):
  0.00-0.10 Q
  0.10-0.30 QO   same-leg
  0.30-0.40 Q
  0.40-0.70 W
  0.70-0.90 WP   same-leg
  0.90-1.00 W

Short ~0.37s QP blips are treated as corrections, not the base stride.
Race-open WO before the first Q is a start pose, not part of the cycle.
"""
from __future__ import annotations

import os
import sys

os.chdir("/workspace/qwop-python")
sys.path.insert(0, "/workspace/qwop-python")

from qwop_python.actions import ActionMapper
from qwop_python.qwop_env import QWOPEnv

MAPPER = ActionMapper(reduced_action_set=False)
assert MAPPER.num_actions == 16

# Named phase specs: list of (key, on, off) fractions. Intervals are half-open [on, off).
# Q/W and O/P must not overlap; if they do, Q beats W and O beats P (sim if/else).
SPECS = {
    # Mode-bin same-leg stride
    "sameleg": [
        ("q", 0.00, 0.42),
        ("o", 0.12, 0.32),
        ("w", 0.42, 1.00),
        ("p", 0.70, 0.90),
    ],
    # Same-leg with a short thigh gap and slightly earlier calves
    "sameleg_gap": [
        ("q", 0.00, 0.38),
        ("o", 0.08, 0.28),
        ("w", 0.48, 0.95),
        ("p", 0.68, 0.88),
    ],
    # Same-leg, calves later in each thigh hold
    "sameleg_latecalf": [
        ("q", 0.00, 0.45),
        ("o", 0.18, 0.38),
        ("w", 0.45, 1.00),
        ("p", 0.72, 0.92),
    ],
    # Opening-cycle style: QP then WO (cross), kept as an alternate template
    "cross": [
        ("q", 0.00, 0.32),
        ("p", 0.05, 0.26),
        ("w", 0.42, 0.80),
        ("o", 0.46, 0.65),
    ],
    # Equal halves, calf in the middle of each thigh
    "halves": [
        ("q", 0.00, 0.45),
        ("o", 0.12, 0.32),
        ("w", 0.50, 0.95),
        ("p", 0.62, 0.82),
    ],
}


def in_iv(phase, on, off):
    phase = phase % 1.0
    if on <= off:
        return on <= phase < off
    return phase >= on or phase < off


def keys_at(phase, spec, phase_shift=0.0):
    ph = (phase + phase_shift) % 1.0
    state = {"q": False, "w": False, "o": False, "p": False}
    for key, on, off in spec:
        if in_iv(ph, on, off):
            state[key] = True
    if state["q"] and state["w"]:
        state["w"] = False
    if state["o"] and state["p"]:
        state["p"] = False
    return state


def action_at(phase, spec, phase_shift=0.0):
    st = keys_at(phase, spec, phase_shift)
    idx = MAPPER.action_from_keys(st["q"], st["w"], st["o"], st["p"])
    if idx is None:
        raise RuntimeError("unmapped %s" % st)
    return idx


def build_actions(period, spec, start_delay, phase_shift, hud_horizon, frames_per_step=1, start_pose=None):
    """Sample the gait at each action-step midpoint on the HUD clock."""
    dt = frames_per_step / 30.0
    n = int(hud_horizon / dt + 0.5)
    actions = []
    pose_steps = 0
    if start_pose:
        pose_name, pose_s = start_pose
        pose_steps = int(round(pose_s / dt))
        pose_idx = {
            "none": 0,
            "WO": MAPPER.action_from_keys(False, True, True, False),
            "W": MAPPER.action_from_keys(False, True, False, False),
            "O": MAPPER.action_from_keys(False, False, True, False),
            "Q": MAPPER.action_from_keys(True, False, False, False),
        }[pose_name]
    delay_steps = int(round(start_delay / dt))
    for i in range(n):
        if i < pose_steps:
            actions.append(pose_idx)
            continue
        t_mid = (i + 0.5) * dt
        t_gait = t_mid - pose_steps * dt - delay_steps * dt
        if t_gait < 0:
            actions.append(0)
            continue
        phase = (t_gait / period) % 1.0
        actions.append(action_at(phase, spec, phase_shift=0.0))
        # phase_shift applied inside action_at via keys; pass through period phase
        # redo with shift:
        actions[-1] = action_at(t_gait / period, spec, phase_shift=phase_shift)
    return actions


def replay(env, actions, frames_per_step):
    env.frames_per_step = frames_per_step
    obs, info0 = env.reset(seed=42)
    peak = float(info0.get("distance") or 0.0)
    last = info0
    stepped = 0
    term_i = None
    for i, a in enumerate(actions):
        obs, reward, terminated, truncated, info = env.step(int(a))
        stepped += 1
        last = info
        dist = float(info.get("distance") or 0.0)
        if dist > peak:
            peak = dist
        if terminated or truncated:
            term_i = i
            break
        # keep going if still up; caller sets horizon
    return {
        "n_stepped": stepped,
        "n_recorded": len(actions),
        "terminated_at": term_i,
        "peak_distance": peak,
        "distance": float(last.get("distance") or 0.0),
        "time": float(last.get("time") or 0.0),
        "fallen": bool(last.get("fallen")),
        "is_success": last.get("is_success"),
        "split_10": last.get("split_10m_time"),
        "split_50": last.get("split_50m_time"),
        "split_100": last.get("split_100m_time"),
    }


def write_rec(path, actions):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("seed=42\n")
        f.write("\n".join(str(a) for a in actions))
        f.write("\n*\n")


def main():
    env = QWOPEnv(
        frames_per_step=1,
        reduced_action_set=False,
        failure_cost=10,
        success_reward=50,
        time_cost_mult=10,
        distance_rew_mult=10.0,
        speed_rew_mult=0.2,
        render_mode=None,
    )
    assert env.action_space.n == 16
    assert env.action_mapper.reduced_action_set is False

    periods = [1.2, 1.4, 1.55, 1.7, 1.77, 1.9, 2.1, 2.4]
    delays = [0.0, 0.2, 0.5, 1.0]
    shifts = [0.0, 0.5]  # start on Q-half or W-half
    templates = ["sameleg", "sameleg_gap", "sameleg_latecalf", "halves", "cross"]
    poses = [None, ("WO", 0.30)]

    results = []
    best = None
    best_actions = None
    n_done = 0

    # Coarse grid: period x template x start_delay x phase_shift, no extra pose.
    # Horizon 12s HUD first; extend winners.
    jobs = []
    for name in templates:
        for period in periods:
            for delay in delays:
                for shift in shifts:
                    jobs.append((name, period, delay, shift, None))

    print("jobs", len(jobs), flush=True)
    HORIZON = 12.0
    for name, period, delay, shift, pose in jobs:
        spec = SPECS[name]
        actions = build_actions(period, spec, delay, shift, HORIZON, 1, pose)
        r = replay(env, actions, 1)
        rec = {
            "template": name,
            "period": period,
            "delay": delay,
            "shift": shift,
            "pose": pose[0] if pose else "none",
            **r,
        }
        results.append(rec)
        n_done += 1
        score = rec["peak_distance"]
        better = best is None or score > best["peak_distance"] + 1e-9 or (
            abs(score - best["peak_distance"]) < 1e-9 and rec["time"] > best["time"]
        )
        if better:
            best = rec
            best_actions = actions
            print("NEW BEST", rec, flush=True)
        elif n_done % 40 == 0:
            print("progress", n_done, "best", best["peak_distance"], best["template"], best["period"], flush=True)

    print("COARSE_DONE", n_done, "best", best, flush=True)

    # Refine around best if it beat 1.7, else still refine a little around top peak
    # and also try start poses on the top settings.
    top = sorted(results, key=lambda r: (r["peak_distance"], r["time"]), reverse=True)[:8]
    print("TOP8", flush=True)
    for r in top:
        print(r, flush=True)

    refine = []
    seen = set()
    for r in top[:5]:
        for dp in (-0.15, -0.08, -0.04, 0.04, 0.08, 0.15):
            for dd in (-0.15, 0.0, 0.15, 0.4):
                for dsh in (0.0, -0.05, 0.05, 0.1):
                    key = (
                        r["template"],
                        round(r["period"] + dp, 3),
                        round(max(0.0, r["delay"] + dd), 3),
                        round((r["shift"] + dsh) % 1.0, 3),
                        "none",
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    refine.append(key)
        # start pose variants of the exact top setting
        for pose in (("WO", 0.25), ("WO", 0.4), ("W", 0.3), ("O", 0.25)):
            refine.append(
                (
                    r["template"],
                    r["period"],
                    r["delay"],
                    r["shift"],
                    pose,
                )
            )

    print("refine jobs", len(refine), flush=True)
    horizon = 20.0 if (best and best["peak_distance"] >= 1.5) else 12.0
    if best and best["peak_distance"] >= 5.0:
        horizon = 30.0
    for item in refine:
        name, period, delay, shift, pose = item
        if period < 0.6:
            continue
        spec = SPECS[name]
        actions = build_actions(period, spec, delay, shift, horizon, 1, pose)
        r = replay(env, actions, 1)
        rec = {
            "template": name,
            "period": period,
            "delay": delay,
            "shift": shift,
            "pose": pose[0] if pose else "none",
            "pose_s": None if pose is None else pose[1],
            **r,
        }
        results.append(rec)
        if rec["peak_distance"] > best["peak_distance"] + 1e-6:
            best = rec
            best_actions = actions
            print("NEW BEST", rec, flush=True)

    # If anything is promising, rerun best with a long horizon so distance is real not a 12s cap
    print("LONG rerun best", best, flush=True)
    long_h = 45.0
    if best["peak_distance"] >= 8.0:
        long_h = 90.0
    pose = None
    if best.get("pose") not in (None, "none"):
        pose = (best["pose"], best.get("pose_s") or 0.3)
    spec = SPECS[best["template"]]
    long_actions = build_actions(
        best["period"], spec, best["delay"], best["shift"], long_h, 1, pose
    )
    long_r = replay(env, long_actions, 1)
    print("LONG RESULT", long_r, flush=True)
    best_actions = long_actions
    best = {**best, **long_r, "long_horizon": long_h}

    out = "/workspace/qwop-python/data/recordings/kurodo_gait_best.rec"
    write_rec(out, best_actions)
    print("WROTE", out, "n", len(best_actions), flush=True)

    # dump results csv
    import json
    with open("/tmp/gait_search_results.json", "w") as f:
        json.dump({"best": best, "results": results}, f)
    print("N_RESULTS", len(results), flush=True)
    env.close()


if __name__ == "__main__":
    main()
