"""Convert kurodo timeline.csv to a reduced-9 .rec and replay it."""
from __future__ import annotations

import csv
import os
from collections import Counter
from itertools import combinations

os.chdir("/workspace/qwop-python")

from gymnasium.envs.registration import registry
import gymnasium as gym

from qwop_python.actions import ActionMapper
from qwop_python.tools import common

TIMELINE = "/workspace/qwop-wr-extract/timeline.csv"
REC_PATH = "/workspace/qwop-python/data/recordings/kurodo_wr.rec"

FPS_VIDEO = 60
HUD_HZ = 30
FRAMES_PER_STEP = 4
RACE_START_SEC = 2.0
LAST_PRESS_SEC = 47.4
SEED = 42

mapper = ActionMapper(reduced_action_set=True)
print("reduced actions:")
for i, name in enumerate(mapper.get_all_action_names()):
    print(f"  {i}: {name} {mapper.action_to_keys[i]}")


def project(q, w, o, p):
    """Map a held key tuple onto the reduced 9-set.

    Exact match if present. Otherwise drop keys (never invent a press) until a
    legal subset remains. Subsets are tried largest-first; within a size,
    combinations() order is q,w,o,p so thighs are kept ahead of calves on ties
    (QO->Q, WP->W).
    """
    q, w, o, p = bool(q), bool(w), bool(o), bool(p)
    exact = mapper.action_from_keys(q, w, o, p)
    if exact is not None:
        return exact, False
    held = [k for k, on in (("q", q), ("w", w), ("o", o), ("p", p)) if on]
    for k in range(len(held) - 1, -1, -1):
        for subset in combinations(held, k):
            cand = mapper.action_from_keys(
                "q" in subset, "w" in subset, "o" in subset, "p" in subset
            )
            if cand is not None:
                return cand, True
    return 0, True


rows = []
with open(TIMELINE) as f:
    for row in csv.DictReader(f):
        rows.append(
            (
                float(row["t_sec"]),
                int(row["q"]),
                int(row["w"]),
                int(row["o"]),
                int(row["p"]),
            )
        )

start_frame = int(round(RACE_START_SEC * FPS_VIDEO))
last_press_frame = int(round(LAST_PRESS_SEC * FPS_VIDEO))
video_frames_per_action = FPS_VIDEO // HUD_HZ * FRAMES_PER_STEP
assert video_frames_per_action == 8

rel = last_press_frame - start_frame
n_actions = rel // video_frames_per_action + 1
end_frame = start_frame + n_actions * video_frames_per_action

print(
    "start_frame=%s last_press_frame=%s n_actions=%s"
    % (start_frame, last_press_frame, n_actions)
)
print(
    "window video t=[%.5f, %.5f)"
    % (start_frame / FPS_VIDEO, end_frame / FPS_VIDEO)
)
print(
    "HUD duration if completed = %.5fs"
    % (n_actions * FRAMES_PER_STEP / HUD_HZ)
)

by_frame = {}
for t, q, w, o, p in rows:
    fi = int(round(t * FPS_VIDEO))
    by_frame[fi] = (q, w, o, p)

actions = []
proj_counter = Counter()
raw_counter = Counter()
mapped_counter = Counter()
n_projected_steps = 0

for i in range(n_actions):
    f0 = start_frame + i * video_frames_per_action
    f1 = f0 + video_frames_per_action
    samples = [by_frame[f] for f in range(f0, f1) if f in by_frame]
    if not samples:
        raise SystemExit("no samples in action %d frames %d:%d" % (i, f0, f1))
    counts = Counter(samples)
    top = max(counts.values())
    modes = [s for s, c in counts.items() if c == top]
    if len(modes) == 1:
        chosen = modes[0]
    else:
        mid = (f0 + f1 - 1) / 2.0

        def tie_key(state):
            dists = [
                abs(f - mid)
                for f in range(f0, f1)
                if f in by_frame and by_frame[f] == state
            ]
            return min(dists)

        chosen = min(modes, key=tie_key)
    raw_counter[chosen] += 1
    idx, projected = project(*chosen)
    if projected:
        n_projected_steps += 1
        proj_counter[(chosen, idx, mapper.get_action_name(idx))] += 1
    mapped_counter[idx] += 1
    actions.append(idx)

print("n_actions=%d projected_steps=%d" % (len(actions), n_projected_steps))
print("raw majority combos:")
for k, v in raw_counter.most_common():
    print(" ", k, v)
print("mapped action counts:")
for i, name in enumerate(mapper.get_all_action_names()):
    print("  %d %s: %d" % (i, name, mapped_counter[i]))
print("projections:")
for k, v in proj_counter.most_common():
    print(" ", k, v)
print(
    "first 12",
    actions[:12],
    [mapper.get_action_name(a) for a in actions[:12]],
)
print(
    "last 8",
    actions[-8:],
    [mapper.get_action_name(a) for a in actions[-8:]],
)

os.makedirs(os.path.dirname(REC_PATH), exist_ok=True)
with open(REC_PATH, "w") as f:
    f.write("seed=%d\n" % SEED)
    f.write("\n".join(str(a) for a in actions))
    f.write("\n*\n")
print("wrote", REC_PATH)

env_kwargs = common.expand_env_kwargs(
    {
        "__include__": "config/env.yml",
        "frames_per_step": 4,
        "reduced_action_set": True,
    }
)
env_kwargs.pop("render_mode", None)
print("env_kwargs", env_kwargs)

env_id = "local/QWOP-v1"
if env_id in registry:
    del registry[env_id]
common.register_env(env_kwargs, env_wrappers=[])

rec = common.load_recording(REC_PATH)
assert rec["seed"] == SEED
assert rec["episodes"][0]["actions"] == actions
assert rec["episodes"][0]["skip"] is False

env = gym.make("local/QWOP-v1")
try:
    assert env.action_space.n == 9, env.action_space
    unwrapped = env.unwrapped
    print(
        "frames_per_step",
        unwrapped.frames_per_step,
        "n_actions",
        unwrapped.action_mapper.num_actions,
    )
    obs, info0 = env.reset(seed=rec["seed"])
    print(
        "reset info",
        {k: info0.get(k) for k in ("time", "distance", "fallen", "is_success")},
    )

    last_info = info0
    terminated_at = None
    truncated_flag = False
    n_stepped = 0
    for i, raw_action in enumerate(rec["episodes"][0]["actions"]):
        action = int(raw_action)
        obs, reward, terminated, truncated, info = env.step(action)
        n_stepped += 1
        last_info = info
        if terminated or truncated:
            terminated_at = i
            truncated_flag = bool(truncated)
            break

    print("--- REPLAY ---")
    print("n_stepped", n_stepped, "n_recorded", len(actions))
    print("terminated_at_action_index", terminated_at)
    print("truncated", truncated_flag)
    for k in (
        "time",
        "distance",
        "fallen",
        "is_success",
        "jump_landed",
        "jumped",
        "split_10m_time",
        "split_50m_time",
        "split_100m_time",
        "episode_steps",
    ):
        print("%s=%s" % (k, last_info.get(k)))
    print("game_ended", unwrapped.game.game_state.game_ended)
    print("finish_100m", float(last_info.get("distance") or 0) >= 100.0)
finally:
    env.close()
