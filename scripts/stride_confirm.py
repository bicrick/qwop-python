import os, sys
from collections import Counter
sys.path.insert(0, "/workspace/qwop-venv/lib/python3.13/site-packages")
sys.path.insert(0, "/workspace/qwop-python")
os.chdir("/workspace/qwop-python")
from qwop_python.actions import ActionMapper
from qwop_python.qwop_env import QWOPEnv

path = "/workspace/qwop-python/data/recordings/kurodo_gait_best.rec"
lines = open(path).read().splitlines()
print("header", lines[0], "nlines", len(lines), "tail", lines[-3:])
acts = [int(x) for x in lines[1:] if x.strip() and x.strip() != "*"]
m = ActionMapper(reduced_action_set=False)
print("unique", sorted(set(acts)))
print("names", Counter(m.get_action_name(a) for a in acts).most_common())
env = QWOPEnv(frames_per_step=1, reduced_action_set=False, render_mode=None)
assert env.action_space.n == 16 and env.action_mapper.reduced_action_set is False
env.reset(seed=42)
last = None
for a in acts:
    obs, reward, terminated, truncated, info = env.step(int(a))
    last = info
    if terminated or truncated:
        break
print("distance", last.get("distance"))
print("time", last.get("time"))
print("fallen", last.get("fallen"))
print("is_success", last.get("is_success"))
print("jump_landed", last.get("jump_landed"))
print("jumped", last.get("jumped"))
print("split_10", last.get("split_10m_time"))
print("split_50", last.get("split_50m_time"))
print("split_100", last.get("split_100m_time"))
print("game_ended", env.game.game_state.game_ended)
env.close()
