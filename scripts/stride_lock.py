"""Replay the current best gait and a tight grid; save only a verified run."""
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


def spec_cross(q_off=0.32, p_on=0.05, p_off=0.26, w_on=0.45, w_off=0.82, o_on=0.48, o_off=0.66):
    return [("q", 0.0, q_off), ("p", p_on, min(p_off, q_off)), ("w", w_on, w_off), ("o", o_on, min(o_off, w_off))]


def build(period, spec, delay, shift, horizon, pose):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    pose_n = 0
    pose_a = 0
    if pose:
        pose_n = int(round(pose[1] / dt))
        pose_a = {"W": ax(0, 1, 0, 0), "WO": ax(0, 1, 1, 0), "Q": ax(1, 0, 0, 0)}[pose[0]]
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


def replay(env, actions, seed=42):
    env.frames_per_step = 1
    obs, info = env.reset(seed=seed)
    peak = float(info.get("distance") or 0.0)
    last = info
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
        "seed": seed,
    }


def load_rec(path):
    lines = open(path).read().splitlines()
    assert lines[0].startswith("seed=")
    acts = []
    for line in lines[1:]:
        if line.strip() == "*":
            break
        if line.strip():
            acts.append(int(line))
    return acts


def write_rec(path, actions):
    with open(path, "w") as f:
        f.write("seed=42\n")
        f.write("\n".join(str(a) for a in actions))
        f.write("\n*\n")


def better(a, b):
    if a is None:
        return True
    if b["peak"] > a["peak"] + 1e-9:
        return True
    if abs(b["peak"] - a["peak"]) < 1e-9 and b["time"] > a["time"]:
        return True
    return False


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

    saved = load_rec(BEST_REC)
    r1 = replay(env, saved, 42)
    r2 = replay(env, saved, 42)
    print("SAVED_REPLAY_1", r1, flush=True)
    print("SAVED_REPLAY_2", r2, flush=True)

    best_rec = {"tag": "saved_file", **r1}
    best_actions = saved
    if r2["peak"] > r1["peak"]:
        best_rec = {"tag": "saved_file", **r2}

    jobs = []
    for period in (0.95, 1.0, 1.05, 1.1, 1.15):
        for delay in (0.0, 0.1, 0.2):
            for pose_s in (0.2, 0.25, 0.3, 0.35, 0.4):
                jobs.append((period, delay, ("WO", pose_s), spec_cross(), "cross"))
    # calf length tweaks at the 1.05 / WO 0.3 point
    for o_off in (0.58, 0.62, 0.70):
        for p_off in (0.20, 0.26, 0.30):
            jobs.append((1.05, 0.0, ("WO", 0.3), spec_cross(p_off=p_off, o_off=o_off), "cross_calf"))

    print("jobs", len(jobs), flush=True)
    h = 28.0
    for n, (period, delay, pose, spec, kind) in enumerate(jobs, 1):
        actions = build(period, spec, delay, 0.5, h, pose)
        r = replay(env, actions, 42)
        rec = {
            "tag": kind,
            "period": period,
            "delay": delay,
            "shift": 0.5,
            "pose": pose,
            **r,
        }
        if better(best_rec, rec):
            best_rec = rec
            best_actions = actions
            print("BEST", rec, flush=True)
        elif n % 20 == 0:
            print("n", n, "best", best_rec["peak"], best_rec.get("period"), best_rec.get("pose"), flush=True)

    # If still upright at 28s, continue that exact parameter set to 55s.
    if best_rec.get("period") and (not best_rec["fallen"]) and best_rec["time"] >= 27:
        actions = build(best_rec["period"], spec_cross(), best_rec["delay"], 0.5, 55.0, best_rec["pose"])
        r = replay(env, actions, 42)
        print("EXTEND", r, flush=True)
        rec = {**best_rec, **r, "horizon": 55.0}
        if r["peak"] + 1e-9 >= best_rec["peak"]:
            best_rec = rec
            best_actions = actions

    # Verify the sequence we are about to save, twice.
    v1 = replay(env, best_actions, 42)
    v2 = replay(env, best_actions, 42)
    print("VERIFY1", v1, flush=True)
    print("VERIFY2", v2, flush=True)
    # Report the lower of the two verifies so we do not over-claim.
    verified = v1 if v1["peak"] <= v2["peak"] else v2
    write_rec(BEST_REC, best_actions)
    # one more replay of the file on disk
    disk = replay(env, load_rec(BEST_REC), 42)
    print("DISK", disk, flush=True)
    out = {
        "params": {k: best_rec.get(k) for k in ("tag", "period", "delay", "shift", "pose")},
        "verify_1": v1,
        "verify_2": v2,
        "disk_replay": disk,
        "report_peak": disk["peak"],
        "report_distance": disk["distance"],
        "report_time": disk["time"],
        "report_fallen": disk["fallen"],
    }
    with open("/tmp/stride_lock.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("FINAL_DISK", disk, flush=True)
    env.close()


if __name__ == "__main__":
    main()
