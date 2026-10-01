"""Gait search with a fresh env per trial so Box2D reset noise cannot inflate distance."""
import json
import os
import sys

sys.path.insert(0, "/workspace/qwop-venv/lib/python3.13/site-packages")
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")

from qwop_python.actions import ActionMapper
from qwop_python.qwop_env import QWOPEnv

MAPPER = ActionMapper(reduced_action_set=False)
BEST_REC = "/workspace/qwop-python/data/recordings/kurodo_gait_best.rec"


def ax(q, w, o, p):
    if q and w:
        w = False
    if o and p:
        p = False
    idx = MAPPER.action_from_keys(bool(q), bool(w), bool(o), bool(p))
    if idx is None:
        raise RuntimeError((q, w, o, p))
    return idx


def make_env():
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
    return env


def build(period, spec, delay, shift, horizon, pose):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    pose_n = 0
    pose_a = 0
    if pose:
        pose_n = int(round(pose[1] / dt))
        pose_a = {"W": ax(0, 1, 0, 0), "WO": ax(0, 1, 1, 0), "Q": ax(1, 0, 0, 0), "O": ax(0, 0, 1, 0)}[pose[0]]
    delay_n = int(round(float(delay) / dt))
    actions = []
    for i in range(n):
        if i < pose_n:
            actions.append(pose_a)
            continue
        t = (i + 0.5) * dt - pose_n * dt - delay_n * dt
        if t < 0:
            actions.append(0)
            continue
        phase = (t / period + shift) % 1.0
        st = {k: False for k in "qwop"}
        for key, on, off in spec:
            if on <= phase < off:
                st[key] = True
        actions.append(ax(st["q"], st["w"], st["o"], st["p"]))
    return actions


def replay(actions):
    env = make_env()
    try:
        env.reset(seed=42)
        peak = 0.0
        last = None
        stepped = 0
        term = None
        for a in actions:
            obs, reward, terminated, truncated, info = env.step(int(a))
            stepped += 1
            last = info
            d = float(info.get("distance") or 0.0)
            if d > peak:
                peak = d
            if terminated or truncated:
                term = stepped - 1
                break
        return {
            "steps": stepped,
            "term": term,
            "peak": peak,
            "distance": float(last.get("distance") or 0.0),
            "time": float(last.get("time") or 0.0),
            "fallen": bool(last.get("fallen")),
            "split_10": last.get("split_10m_time"),
            "split_50": last.get("split_50m_time"),
            "split_100": last.get("split_100m_time"),
        }
    finally:
        env.close()


def write_rec(path, actions):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("seed=42\n")
        f.write("\n".join(str(a) for a in actions))
        f.write("\n*\n")


def cross(q_off=0.32, p_on=0.05, p_off=0.26, w_on=0.45, w_off=0.82, o_on=0.48, o_off=0.66):
    return [("q", 0.0, q_off), ("p", p_on, p_off), ("w", w_on, w_off), ("o", o_on, o_off)]


def sameleg():
    # Mode-bin same-leg QO then WP
    return [("q", 0.00, 0.42), ("o", 0.12, 0.32), ("w", 0.42, 1.00), ("p", 0.70, 0.90)]


def main():
    jobs = []
    for period in (0.9, 1.0, 1.05, 1.15, 1.3, 1.5, 1.77, 2.1):
        for delay in (0.0, 0.15, 0.3, 0.5):
            for pose in (None, ("WO", 0.2), ("WO", 0.3), ("WO", 0.4), ("W", 0.25)):
                jobs.append(("cross", period, delay, 0.5, pose, cross()))
    for period in (1.05, 1.5, 1.77):
        for delay in (0.0, 0.3):
            for shift in (0.0, 0.5):
                jobs.append(("sameleg", period, delay, shift, None, sameleg()))
                jobs.append(("sameleg", period, delay, shift, ("WO", 0.3), sameleg()))

    print("jobs", len(jobs), flush=True)
    best = None
    best_actions = None
    rows = []
    h = 22.0
    for n, (kind, period, delay, shift, pose, spec) in enumerate(jobs, 1):
        actions = build(period, spec, delay, shift, h, pose)
        r = replay(actions)
        rec = {
            "kind": kind,
            "period": period,
            "delay": delay,
            "shift": shift,
            "pose": pose,
            **r,
        }
        rows.append(rec)
        if best is None or r["peak"] > best["peak"] + 1e-9 or (
            abs(r["peak"] - best["peak"]) < 1e-9 and r["time"] > best["time"]
        ):
            best = rec
            best_actions = actions
            print("BEST", rec, flush=True)
        elif n % 20 == 0:
            print("n", n, "best", best["peak"], best["kind"], best["period"], best["pose"], flush=True)

    rows.sort(key=lambda r: (r["peak"], r["time"]), reverse=True)
    print("TOP8", flush=True)
    for r in rows[:8]:
        print(r, flush=True)

    # Phase tweaks around the winner, still fresh env, longer horizon if already > 3m
    winner = rows[0]
    tweaks = []
    if winner["kind"] == "cross":
        for q_off in (0.28, 0.32, 0.36):
            for p_off in (0.20, 0.26, 0.30):
                for o_off in (0.60, 0.66, 0.72):
                    tweaks.append(cross(q_off=q_off, p_off=p_off, o_off=o_off))
    print("tweaks", len(tweaks), flush=True)
    h2 = 30.0
    for spec in tweaks:
        actions = build(winner["period"], spec, winner["delay"], winner["shift"], h2, winner["pose"])
        r = replay(actions)
        rec = {**winner, **r, "stage": "tweak"}
        if r["peak"] > best["peak"] + 1e-9:
            best = rec
            best_actions = actions
            print("BEST", rec, flush=True)

    # Official long replay of the best parameters we can regenerate.
    # If the winning row is a tweak, best_actions is that sequence already
    # built for h2. Extend by regenerating default or the last spec.
    print("REGEN_BEST", best, flush=True)
    # Extend stored actions if the episode was still going: rebuild from
    # winner params with default cross/sameleg unless a tweak won.
    # Always replay best_actions as the official short result, then if not
    # fallen and time is at the horizon, we already used that horizon.
    official = replay(best_actions)
    print("OFFICIAL_SHORT", official, flush=True)

    # Build a 45s sequence from the winning parameter set using the spec
    # family. For tweak winners, best_actions is the one to save; if still
    # upright at horizon, the saved sequence is only as long as that horizon.
    write_rec(BEST_REC, best_actions)
    disk = replay(open_actions(BEST_REC))
    print("DISK", disk, flush=True)
    with open("/tmp/stride_fresh.json", "w") as f:
        json.dump({"best": best, "official_short": official, "disk": disk, "top8": rows[:8]}, f, indent=2, default=str)
    print("WROTE", BEST_REC, "n", len(best_actions), flush=True)


def open_actions(path):
    lines = open(path).read().splitlines()
    acts = []
    for line in lines[1:]:
        if line.strip() == "*":
            break
        if line.strip():
            acts.append(int(line))
    return acts


if __name__ == "__main__":
    main()
