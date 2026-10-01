"""Extend the fresh-env 14m cross gait and refine the spec that cleared 10m."""
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


def spec(q_off=0.28, p_on=0.05, p_off=0.30, w_on=0.45, w_off=0.82, o_on=0.48, o_off=0.66):
    return [("q", 0.0, q_off), ("p", p_on, p_off), ("w", w_on, w_off), ("o", o_on, o_off)]


def build(period, sp, delay, shift, horizon, pose=None):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    pose_n = 0
    pose_a = 0
    if pose:
        pose_n = int(round(pose[1] / dt))
        pose_a = ax(0, 1, 1, 0) if pose[0] == "WO" else ax(0, 1, 0, 0)
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
        assert env.action_space.n == 16
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
    base = spec()
    # Confirm the decoded 14m spec at 30s, twice.
    a = build(1.0, base, 0.0, 0.5, 30.0, None)
    r1 = replay(a)
    r2 = replay(a)
    print("CONFIRM30", r1, flush=True)
    print("CONFIRM30b", r2, flush=True)

    jobs = []
    for period in (0.92, 0.96, 1.0, 1.04, 1.08):
        for delay in (0.0, 0.1):
            for q_off, p_off, o_off in (
                (0.28, 0.30, 0.66),
                (0.28, 0.28, 0.66),
                (0.26, 0.30, 0.66),
                (0.28, 0.30, 0.62),
                (0.30, 0.30, 0.66),
            ):
                jobs.append((period, delay, spec(q_off=q_off, p_off=p_off, o_off=o_off)))

    print("jobs", len(jobs), flush=True)
    best = {"peak": -1}
    best_actions = a
    best_meta = {"period": 1.0, "delay": 0.0, "shift": 0.5, "pose": None, "spec": "q0.28 p0.05-0.30 w0.45-0.82 o0.48-0.66"}
    h = 36.0
    for n, (period, delay, sp) in enumerate(jobs, 1):
        actions = build(period, sp, delay, 0.5, h, None)
        r = replay(actions)
        if r["peak"] > best["peak"] + 1e-9 or (
            abs(r["peak"] - best.get("peak", -1)) < 1e-9 and r.get("time", 0) > best.get("time", 0)
        ):
            best = r
            best_actions = actions
            best_meta = {
                "period": period,
                "delay": delay,
                "shift": 0.5,
                "pose": None,
                "spec": sp,
            }
            print("BEST", best_meta, r, flush=True)
        elif n % 15 == 0:
            print("n", n, "best", best["peak"], best_meta["period"], flush=True)

    # Extend winner to 70s. If still moving and not fallen, continue to 120s.
    print("EXTEND_META", best_meta, flush=True)
    sp = best_meta["spec"] if isinstance(best_meta["spec"], list) else base
    long_a = build(best_meta["period"], sp, best_meta["delay"], 0.5, 70.0, None)
    long_r = replay(long_a)
    print("LONG70", long_r, flush=True)
    use_a, use_r = long_a, long_r
    if long_r["fallen"] is False and long_r["distance"] >= 10.0:
        longer = build(best_meta["period"], sp, best_meta["delay"], 0.5, 120.0, None)
        longer_r = replay(longer)
        print("LONG120", longer_r, flush=True)
        if longer_r["peak"] + 1e-9 >= long_r["peak"]:
            use_a, use_r = longer, longer_r
            if longer_r["fallen"] is False and longer_r["distance"] >= 40.0:
                finish = build(best_meta["period"], sp, best_meta["delay"], 0.5, 220.0, None)
                finish_r = replay(finish)
                print("LONG220", finish_r, flush=True)
                if finish_r["peak"] + 1e-9 >= longer_r["peak"]:
                    use_a, use_r = finish, finish_r

    write_rec(BEST_REC, use_a)
    # fresh replay of the file
    lines = open(BEST_REC).read().splitlines()
    acts = [int(x) for x in lines[1:] if x.strip() and x.strip() != "*"]
    disk = replay(acts)
    print("DISK", disk, flush=True)
    out = {"meta": {k: best_meta[k] for k in ("period", "delay", "shift", "pose")},
           "spec": sp, "long": use_r, "disk": disk, "n": len(use_a)}
    with open("/tmp/stride_extend.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("WROTE", BEST_REC, "n", len(use_a), flush=True)


if __name__ == "__main__":
    main()
