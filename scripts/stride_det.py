import os
import sys
sys.path.insert(0, "/workspace/qwop-venv/lib/python3.13/site-packages")
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")
from qwop_python.actions import ActionMapper
from qwop_python.qwop_env import QWOPEnv

MAPPER = ActionMapper(reduced_action_set=False)

def ax(q, w, o, p):
    if q and w:
        w = False
    if o and p:
        p = False
    return MAPPER.action_from_keys(bool(q), bool(w), bool(o), bool(p))

def build():
    spec = [("q", 0.0, 0.32), ("p", 0.05, 0.26), ("w", 0.45, 0.82), ("o", 0.48, 0.66)]
    period, delay, shift, pose_s = 1.05, 0.0, 0.5, 0.3
    dt = 1.0 / 30.0
    n = int(round(20.0 / dt))
    pose_n = int(round(pose_s / dt))
    pose_a = ax(0, 1, 1, 0)
    actions = []
    for i in range(n):
        if i < pose_n:
            actions.append(pose_a)
            continue
        t = (i + 0.5) * dt - pose_n * dt
        phase = (t / period + shift) % 1.0
        st = {k: False for k in "qwop"}
        for key, on, off in spec:
            if on <= phase < off:
                st[key] = True
        actions.append(ax(st["q"], st["w"], st["o"], st["p"]))
    return actions

def make_env():
    return QWOPEnv(frames_per_step=1, reduced_action_set=False, render_mode=None)

def run(env, actions):
    env.frames_per_step = 1
    env.reset(seed=42)
    peak = 0.0
    last = None
    for a in actions:
        obs, reward, terminated, truncated, info = env.step(int(a))
        last = info
        d = float(info.get("distance") or 0.0)
        if d > peak:
            peak = d
        if terminated or truncated:
            break
    return peak, last.get("distance"), last.get("time"), last.get("fallen")

actions = build()
print("reuse same env")
env = make_env()
for i in range(4):
    print(i, run(env, actions))
env.close()

print("fresh env each")
for i in range(3):
    env = make_env()
    print(i, run(env, actions))
    env.close()
