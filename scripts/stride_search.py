"""Open-loop stride search. Full 16-action set. No expert weights."""
import json
import os
import sys

sys.path.insert(0, "/workspace/qwop-venv/lib/python3.13/site-packages")
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")

from qwop_python.actions import ActionMapper
from qwop_python.qwop_env import QWOPEnv

MAPPER = ActionMapper(reduced_action_set=False)
assert MAPPER.num_actions == 16
OUT = "/tmp/stride_results.jsonl"
BEST_REC = "/workspace/qwop-python/data/recordings/kurodo_gait_best.rec"


def keys_from_spec(phase, spec):
    st = {k: False for k in "qwop"}
    ph = phase % 1.0
    for key, on, off in spec:
        if on <= ph < off:
            st[key] = True
    if st["q"] and st["w"]:
        st["w"] = False
    if st["o"] and st["p"]:
        st["p"] = False
    return st


def action_index(st):
    idx = MAPPER.action_from_keys(st["q"], st["w"], st["o"], st["p"])
    if idx is None:
        raise RuntimeError(st)
    return idx


def make_spec(q_off, w_gap, o_lag, o_len, p_lag, p_len):
    w_on = q_off + w_gap
    w_off = 0.98
    o_on = o_lag
    o_off = min(q_off - 0.02, o_on + o_len)
    p_on = w_on + p_lag
    p_off = min(w_off - 0.02, p_on + p_len)
    if o_off <= o_on or p_off <= p_on or w_on >= 0.9:
        return None
    return [
        ("q", 0.0, q_off),
        ("o", o_on, o_off),
        ("w", w_on, w_off),
        ("p", p_on, p_off),
    ]


def cross_spec():
    return [
        ("q", 0.00, 0.32),
        ("p", 0.05, 0.26),
        ("w", 0.45, 0.82),
        ("o", 0.48, 0.66),
    ]


def build_actions(period, spec, delay, shift, horizon, pose=None):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    pose_n = 0
    pose_a = 0
    if pose:
        pose_n = int(round(pose[1] / dt))
        pose_a = action_index(
            {"WO": {"q": False, "w": True, "o": True, "p": False},
             "W": {"q": False, "w": True, "o": False, "p": False},
             "Q": {"q": True, "w": False, "o": False, "p": False}}[pose[0]]
        )
    delay_n = int(round(delay / dt))
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
        actions.append(action_index(keys_from_spec(phase, spec)))
    return actions


def replay(env, actions):
    env.frames_per_step = 1
    obs, info = env.reset(seed=42)
    peak = float(info.get("distance") or 0.0)
    last = info
    stepped = 0
    term = None
    for i, a in enumerate(actions):
        obs, reward, terminated, truncated, info = env.step(int(a))
        stepped += 1
        last = info
        dist = float(info.get("distance") or 0.0)
        if dist > peak:
            peak = dist
        if terminated or truncated:
            term = i
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
    assert env.action_space.n == 16 and env.action_mapper.reduced_action_set is False

    jobs = []
    for period in (1.4, 1.77, 2.2, 3.0):
        for q_off in (0.38, 0.48):
            for w_gap in (0.0, 0.08):
                for o_lag in (0.08, 0.15):
                    for p_lag in (0.20, 0.28):
                        spec = make_spec(q_off, w_gap, o_lag, 0.18, p_lag, 0.20)
                        if spec is None:
                            continue
                        for delay in (0.0, 0.4):
                            for shift in (0.0, 0.5):
                                jobs.append({
                                    "kind": "sameleg",
                                    "period": period,
                                    "delay": delay,
                                    "shift": shift,
                                    "q_off": q_off,
                                    "w_gap": w_gap,
                                    "o_lag": o_lag,
                                    "p_lag": p_lag,
                                    "spec": spec,
                                    "pose": None,
                                })
    for period in (1.4, 1.77, 2.2, 3.0):
        for delay in (0.0, 0.4):
            for shift in (0.0, 0.5):
                jobs.append({
                    "kind": "cross",
                    "period": period,
                    "delay": delay,
                    "shift": shift,
                    "spec": cross_spec(),
                    "pose": None,
                })

    print("jobs", len(jobs), flush=True)
    best = None
    best_actions = None
    horizon = 10.0
    with open(OUT, "w") as log:
        for n, job in enumerate(jobs, 1):
            actions = build_actions(job["period"], job["spec"], job["delay"], job["shift"], horizon, job["pose"])
            r = replay(env, actions)
            rec = {k: v for k, v in job.items() if k != "spec"}
            rec.update(r)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if best is None or r["peak"] > best["peak"] + 1e-9 or (
                abs(r["peak"] - best["peak"]) < 1e-9 and r["time"] > best["time"]
            ):
                best = rec
                best_actions = actions
                print("BEST", rec, flush=True)
            elif n % 25 == 0:
                print("n", n, "best", best["peak"], best["kind"], best["period"], flush=True)

    print("COARSE", best, flush=True)

    # refine periods and delays around the coarse winner, plus start poses
    refine_src = []
    # reload top
    rows = [json.loads(line) for line in open(OUT)]
    rows.sort(key=lambda r: (r["peak"], r["time"]), reverse=True)
    print("TOP5", flush=True)
    for r in rows[:5]:
        print(r, flush=True)
        refine_src.append(r)

    seen = set()
    extra = []
    for r in refine_src[:3]:
        for dp in (-0.25, -0.1, 0.0, 0.1, 0.25):
            for dd in (0.0, 0.2, 0.6):
                for pose in (None, ("WO", 0.3), ("W", 0.25)):
                    key = (r["kind"], round(r["period"] + dp, 3), round(r["delay"] + dd, 3), r["shift"], pose)
                    if key in seen:
                        continue
                    seen.add(key)
                    extra.append((r, r["period"] + dp, r["delay"] + dd, pose))

    print("refine", len(extra), flush=True)
    rh = 16.0 if best["peak"] >= 1.0 else 12.0
    with open(OUT, "a") as log:
        for r, period, delay, pose in extra:
            if period < 0.7:
                continue
            if r["kind"] == "cross":
                spec = cross_spec()
            else:
                spec = make_spec(r["q_off"], r["w_gap"], r["o_lag"], 0.18, r["p_lag"], 0.20)
            if spec is None:
                continue
            actions = build_actions(period, spec, delay, r["shift"], rh, pose)
            rr = replay(env, actions)
            rec = {
                "kind": r["kind"],
                "period": period,
                "delay": delay,
                "shift": r["shift"],
                "q_off": r.get("q_off"),
                "w_gap": r.get("w_gap"),
                "o_lag": r.get("o_lag"),
                "p_lag": r.get("p_lag"),
                "pose": None if pose is None else pose[0],
                "stage": "refine",
            }
            rec.update(rr)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if rr["peak"] > best["peak"] + 1e-9:
                best = rec
                best_actions = actions
                print("BEST", rec, flush=True)

    long_h = 40.0 if best["peak"] < 8 else 80.0
    if best["kind"] == "cross":
        spec = cross_spec()
    else:
        spec = make_spec(best["q_off"], best["w_gap"], best["o_lag"], 0.18, best["p_lag"], 0.20)
    pose = None
    if best.get("pose") not in (None, "none"):
        pose = (best["pose"], 0.3)
    long_actions = build_actions(best["period"], spec, best["delay"], best["shift"], long_h, pose)
    long_r = replay(env, long_actions)
    print("LONG", long_r, flush=True)
    write_rec(BEST_REC, long_actions)
    summary = {"best_params": {k: best[k] for k in best if k not in ("spec",)}, "long": long_r, "rec": BEST_REC}
    with open("/tmp/stride_best.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("WROTE", BEST_REC, "n_actions", len(long_actions), flush=True)
    env.close()


if __name__ == "__main__":
    main()
