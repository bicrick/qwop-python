import os
import sys
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")
from qwop_python.qwop_env import QWOPEnv
env = QWOPEnv(frames_per_step=1, reduced_action_set=False, render_mode=None)
print("actions", env.action_space.n, "reduced", env.action_mapper.reduced_action_set)
obs, info = env.reset(seed=42)
print("reset", info.get("distance"), info.get("time"), info.get("fallen"))
peak = 0.0
last = info
for i in range(90):
    a = 6 if (i % 53) < 16 else (9 if (i % 53) >= 30 else (1 if (i % 53) < 22 else 2))
    obs, reward, terminated, truncated, info = env.step(a)
    d = float(info.get("distance") or 0.0)
    if d > peak:
        peak = d
    last = info
    if terminated or truncated:
        print("term", i)
        break
print("peak", peak, "dist", last.get("distance"), "time", last.get("time"), "fallen", last.get("fallen"))
env.close()
