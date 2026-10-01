import os
import sys
sys.path.insert(0, "/workspace/qwop-venv/lib/python3.13/site-packages")
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")
from qwop_python.qwop_env import QWOPEnv
print("imported")
env = QWOPEnv(frames_per_step=1, reduced_action_set=False, render_mode=None)
print("n", env.action_space.n, env.action_mapper.reduced_action_set)
obs, info = env.reset(seed=42)
print("reset", info.get("distance"), info.get("time"), info.get("fallen"))
peak = float(info.get("distance") or 0.0)
last = info
term_i = None
for i in range(180):
    phase = (i % 54) / 54.0
    if phase < 0.12:
        a = 1
    elif phase < 0.32:
        a = 6
    elif phase < 0.42:
        a = 1
    elif phase < 0.70:
        a = 2
    elif phase < 0.90:
        a = 9
    else:
        a = 2
    obs, reward, terminated, truncated, info = env.step(a)
    d = float(info.get("distance") or 0.0)
    if d > peak:
        peak = d
    last = info
    if terminated or truncated:
        term_i = i
        break
print("steps", term_i if term_i is not None else 120, "peak", peak, "dist", last.get("distance"), "time", last.get("time"), "fallen", last.get("fallen"))
env.close()
