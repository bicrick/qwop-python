"""Last local search around the 89.7m gait, trying to clear 100m."""
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
    return MAPPER.action_from_keys(bool(q), bool(w), bool(o), bool(p))


def build(period, sp, delay, shift, horizon):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    delay_n = int(round(float(delay) / dt))
    actions = []
    for i in range(n):
        t = (i + 0.5) * dt - delay_n * dt
        if t < 0:
            actions.append(0)
            continue
        phase = (t / period + shift) % 1.0
        st = {k: False for k in "qwop"}
        for key, on, off in sp:
            if on <= phase < off:
                st[key] = True
        actions.append(ax(st["q"], st["w"], st["o"], st["p"]))
    return actions


def replay(actions):
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
    with open(path, "w") as f:
        f.write("seed=42\n")
        f.write("\n".join(str(int(a)) for a in actions))
        f.write("\n*\n")


def main():
    jobs = []
    for period in (0.98, 1.0, 1.02, 1.04):
        for delay in (0.05, 0.10, 0.15, 0.20):
            for q_off, p_off, w_off, o_off in (
                (0.28, 0.30, 0.82, 0.66),
                (0.26, 0.30, 0.82, 0.66),
                (0.28, 0.32, 0.84, 0.68),
                (0.28, 0.30, 0.80, 0.64),
            ):
                sp = [
                    ("q", 0.0, q_off),
                    ("p", 0.05, p_off),
                    ("w", 0.45, w_off),
                    ("o", 0.48, o_off),
                ]
                jobs.append((period, delay, sp))

    print("jobs", len(jobs), flush=True)
    best = {"peak": -1.0}
    best_actions = None
    best_meta = None
    h = 140.0
    for n, (period, delay, sp) in enumerate(jobs, 1):
        actions = build(period, sp, delay, 0.5, h)
        r = replay(actions)
        rec = {"period": period, "delay": delay, "spec": sp, **r}
        if r["peak"] > best["peak"] + 1e-9 or (
            abs(r["peak"] - best.get("peak", -1)) < 1e-9 and r.get("distance", 0) > best.get("distance", -1)
        ):
            best = r
            best_actions = actions
            best_meta = rec
            print("BEST", {k: rec[k] for k in ("period", "delay", "peak", "distance", "time", "fallen", "split_10", "split_50", "split_100")}, flush=True)
        elif n % 10 == 0:
            print("n", n, "best", best["peak"], flush=True)

    # If still short of 100 and not fallen at 140, push that one setting further.
    if best_actions is not None and best["fallen"] is False and best["peak"] < 100:
        sp = best_meta["spec"]
        actions = build(best_meta["period"], sp, best_meta["delay"], 0.5, 200.0)
        r = replay(actions)
        print("PUSH200", r, flush=True)
        if r["peak"] + 1e-9 >= best["peak"]:
            best = r
            best_actions = actions
            best_meta = {**best_meta, **r}

    # Keep the previous 89.7 result if this search is worse.
    if best["peak"] < 89.7:
        print("NO_IMPROVE", best, flush=True)
        return

    # Trim rec to the executed prefix (include the terminating step).
    n_keep = best["steps"]
    write_rec(BEST_REC, best_actions[:n_keep])
    lines = open(BEST_REC).read().splitlines()
    acts = [int(x) for x in lines[1:] if x.strip() and x.strip() != "*"]
    disk = replay(acts)
    print("DISK", disk, flush=True)
    print("META", {k: best_meta[k] for k in ("period", "delay", "spec")}, flush=True)
    with open("/tmp/stride_finish.json", "w") as f:
        json.dump({"meta": {k: best_meta[k] for k in ("period", "delay", "spec")}, "disk": disk}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
