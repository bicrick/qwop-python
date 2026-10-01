"""Refine the cross-gait that stayed up past the literal 1.7m replay."""
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


def action_index(q, w, o, p):
    if q and w:
        w = False
    if o and p:
        p = False
    idx = MAPPER.action_from_keys(q, w, o, p)
    if idx is None:
        raise RuntimeError((q, w, o, p))
    return idx


def cross_spec(q_off=0.32, p_on=0.05, p_off=0.26, w_on=0.45, w_off=0.82, o_on=0.48, o_off=0.66):
    return [("q", 0.0, q_off), ("p", p_on, p_off), ("w", w_on, w_off), ("o", o_on, o_off)]


def build(period, spec, delay, shift, horizon, pose):
    dt = 1.0 / 30.0
    n = int(round(horizon / dt))
    pose_n = 0
    pose_a = 0
    if pose:
        pose_n = int(round(pose[1] / dt))
        name = pose[0]
        if name == "W":
            pose_a = action_index(False, True, False, False)
        elif name == "WO":
            pose_a = action_index(False, True, True, False)
        elif name == "Q":
            pose_a = action_index(True, False, False, False)
        else:
            pose_a = 0
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
        st = {"q": False, "w": False, "o": False, "p": False}
        for key, on, off in spec:
            if on <= phase < off:
                st[key] = True
        actions.append(action_index(st["q"], st["w"], st["o"], st["p"]))
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
        d = float(info.get("distance") or 0.0)
        if d > peak:
            peak = d
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


def consider(best, rec, actions):
    if best is None or rec["peak"] > best[0]["peak"] + 1e-9 or (
        abs(rec["peak"] - best[0]["peak"]) < 1e-9 and rec["time"] > best[0]["time"]
    ):
        print("BEST", rec, flush=True)
        return (rec, actions)
    return best


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

    # Confirm the two refine winners at the same horizon used then.
    checks = [
        ("cross", 1.15, 0.0, 0.5, ("WO", 0.3), 16.0, cross_spec()),
        ("cross", 1.5, 0.6, 0.5, ("W", 0.25), 16.0, cross_spec()),
        ("cross", 1.5, 0.6, 0.5, ("W", 0.3), 16.0, cross_spec()),
    ]
    best = None
    print("confirm", flush=True)
    for name, period, delay, shift, pose, h, spec in checks:
        actions = build(period, spec, delay, shift, h, pose)
        r = replay(env, actions)
        rec = {"kind": name, "period": period, "delay": delay, "shift": shift, "pose": pose, "horizon": h, **r}
        print("CHECK", rec, flush=True)
        best = consider(best, rec, actions)

    # Local grid around the upright cross settings.
    jobs = []
    for period in (1.05, 1.15, 1.25, 1.35, 1.45, 1.5, 1.6, 1.7):
        for delay in (0.0, 0.3, 0.45, 0.6, 0.8):
            for pose in (("W", 0.15), ("W", 0.25), ("W", 0.35), ("WO", 0.2), ("WO", 0.3), None):
                jobs.append((period, delay, 0.5, pose, cross_spec()))
    # small phase nudges on the 1.5 / 0.6 / W0.25 point
    base = cross_spec()
    for dq in (-0.04, 0.04):
        for dp in (-0.04, 0.04):
            jobs.append((1.5, 0.6, 0.5, ("W", 0.25), cross_spec(q_off=0.32 + dq, p_off=0.26 + dp)))
    for dw in (-0.04, 0.04):
        jobs.append((1.5, 0.6, 0.5, ("W", 0.25), cross_spec(w_on=0.45 + dw, o_on=0.48 + dw)))

    print("jobs", len(jobs), flush=True)
    h = 18.0
    for n, (period, delay, shift, pose, spec) in enumerate(jobs, 1):
        actions = build(period, spec, delay, shift, h, pose)
        r = replay(env, actions)
        rec = {
            "kind": "cross",
            "period": period,
            "delay": delay,
            "shift": shift,
            "pose": pose,
            "horizon": h,
            **r,
        }
        best = consider(best, rec, actions)
        if n % 40 == 0:
            print("n", n, "best", best[0]["peak"], best[0]["period"], best[0]["delay"], best[0]["pose"], flush=True)

    # Extend the winner. If still up, go longer.
    rec, actions = best
    print("EXTEND_FROM", rec, flush=True)
    pose = rec["pose"]
    spec = rec.get("spec") if False else cross_spec()
    # phase-nudge jobs stored spec only in actions already evaluated; winner
    # from phase nudge would not match default cross_spec. Re-run exact
    # winner by regenerating from stored fields when spec is default.
    # If peak came from a phase-nudge job, the stored actions are the exact sequence.
    long_h = 50.0
    # Prefer regenerating only when pose/period match a default-spec job.
    # Always replay the stored actions first for  the already-built horizon,
    # then rebuild default spec and also replay stored actions padded? 
    # Stored actions are length of their horizon. Extend by appending more
    # of the same gait clock.
    # Rebuild using the parameters we know. For phase-nudge winners, rec
    # has no spec; in that case use the stored action prefix and continue
    # with default only if pose matches. Safer: encode spec on rec.

    # Re-search the best rec's parameters by replaying a 50s generation
    # with the same pose/period/delay/shift and default cross spec, AND
    # if the stored action list is longer than that would differ, also
    # continue from stored actions by looping the cyclic portion.
    long_actions = build(rec["period"], cross_spec(), rec["delay"], rec["shift"], long_h, rec["pose"])
    long_r = replay(env, long_actions)
    print("LONG_DEFAULT_SPEC", long_r, flush=True)
    if long_r["peak"] + 1e-9 >= rec["peak"]:
        best = ({**rec, **long_r, "horizon": long_h}, long_actions)
    else:
        # stored actions were better at short horizon; extend by repeating
        # the cyclic tail after pose+delay using default spec anyway, but
        # keep the stored sequence as the saved rec if long is worse.
        # Try a few nearby pose durations at 50s with the winning period.
        print("short horizon winner did not repeat on default rebuild; scanning pose at 50s", flush=True)
        for pose in (rec["pose"], ("W", 0.2), ("W", 0.25), ("W", 0.3), ("WO", 0.25), ("WO", 0.3)):
            for delay in (rec["delay"], rec["delay"] - 0.1, rec["delay"] + 0.1):
                acts = build(rec["period"], cross_spec(), max(0.0, delay), rec["shift"], long_h, pose)
                rr = replay(env, acts)
                print("scan", rec["period"], delay, pose, rr["peak"], rr["distance"], rr["time"], rr["fallen"], flush=True)
                cand = {
                    "kind": "cross",
                    "period": rec["period"],
                    "delay": delay,
                    "shift": rec["shift"],
                    "pose": pose,
                    "horizon": long_h,
                    **rr,
                }
                best = consider(best, cand, acts)

    rec, actions = best
    if rec["time"] < 40 and not rec["fallen"] and rec["peak"] >= 4.0:
        acts = build(rec["period"], cross_spec(), rec["delay"], rec["shift"], 70.0, rec["pose"])
        rr = replay(env, acts)
        print("LONGER", rr, flush=True)
        cand = {**rec, **rr, "horizon": 70.0}
        if rr["peak"] + 1e-9 >= rec["peak"]:
            best = (cand, acts)

    rec, actions = best
    write_rec(BEST_REC, actions)
    summary = {"best": rec, "n_actions": len(actions), "rec": BEST_REC}
    with open("/tmp/stride_refine_best.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("WROTE", BEST_REC, "n", len(actions), flush=True)
    print("FINAL", rec, flush=True)
    env.close()


if __name__ == "__main__":
    main()
