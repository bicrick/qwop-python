"""Convert kurodo timeline.csv to a full-16 .rec and replay it.

Clock assumption
----------------
Video timeline is 60 fps. Each env step with frames_per_step=1 applies one
discrete action and calls game.update() once. That advances HUD score_time by
SCORE_TIME_STEP = 1/30 s (one physics/HUD update, not four). So each recorded
action is held for 1/30 s = 2 video frames.

The race window is video t=2.0 through the last press at 47.4 s (pre-roll
omitted). Each action is the majority key tuple in that 2-frame bin. A 1-1
tie is broken by the sample nearest the bin midpoint; the midpoint of a
2-frame bin is the later frame, so a press that starts on the second video
frame is kept rather than dropped as none.
"""
from __future__ import annotations

import csv
import os
from collections import Counter

os.chdir("/workspace/qwop-python")

from gymnasium.envs.registration import registry
import gymnasium as gym

from qwop_python.actions import ActionMapper
from qwop_python.tools import common

TIMELINE = "/workspace/qwop-wr-extract/timeline.csv"
REC_PATH = "/workspace/qwop-python/data/recordings/kurodo_wr_full.rec"

FPS_VIDEO = 60
HUD_HZ = 30
RACE_START_SEC = 2.0
LAST_PRESS_SEC = 47.4
SEED = 42


def load_rows():
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
    return rows


def by_video_frame(rows):
    by_frame = {}
    for t, q, w, o, p in rows:
        fi = int(round(t * FPS_VIDEO))
        by_frame[fi] = (bool(q), bool(w), bool(o), bool(p))
    return by_frame


def sample_actions(by_frame, frames_per_step, mapper):
    video_frames_per_action = FPS_VIDEO // HUD_HZ * frames_per_step
    start_frame = int(round(RACE_START_SEC * FPS_VIDEO))
    last_press_frame = int(round(LAST_PRESS_SEC * FPS_VIDEO))
    rel = last_press_frame - start_frame
    n_actions = rel // video_frames_per_action + 1
    end_frame = start_frame + n_actions * video_frames_per_action

    actions = []
    raw_counter = Counter()
    mapped_counter = Counter()
    unmapped = []

    for i in range(n_actions):
        f0 = start_frame + i * video_frames_per_action
        f1 = f0 + video_frames_per_action
        samples = [(f, by_frame[f]) for f in range(f0, f1) if f in by_frame]
        if not samples:
            raise SystemExit("no samples in action %d frames %d:%d" % (i, f0, f1))
        states = [s for _, s in samples]
        counts = Counter(states)
        top = max(counts.values())
        modes = [s for s, c in counts.items() if c == top]
        if len(modes) == 1:
            chosen = modes[0]
        else:
            mid = (f0 + f1 - 1) / 2.0

            def tie_key(state, samples=samples, mid=mid):
                dists = [abs(f - mid) for f, st in samples if st == state]
                # nearer first; on equal distance prefer the later frame
                return (min(dists), -max(f for f, st in samples if st == state))

            chosen = min(modes, key=tie_key)

        idx = mapper.action_from_keys(*chosen)
        if idx is None:
            unmapped.append((i, chosen))
            raise SystemExit("unmapped keys at action %d: %s" % (i, chosen))
        raw_counter[chosen] += 1
        mapped_counter[idx] += 1
        actions.append(idx)

    meta = {
        "frames_per_step": frames_per_step,
        "video_frames_per_action": video_frames_per_action,
        "start_frame": start_frame,
        "last_press_frame": last_press_frame,
        "end_frame": end_frame,
        "n_actions": n_actions,
        "hud_duration_s": n_actions * frames_per_step / HUD_HZ,
        "window": (
            start_frame / FPS_VIDEO,
            end_frame / FPS_VIDEO,
        ),
        "raw_counter": raw_counter,
        "mapped_counter": mapped_counter,
        "unmapped": unmapped,
    }
    return actions, meta


def write_rec(path, actions):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("seed=%d\n" % SEED)
        f.write("\n".join(str(a) for a in actions))
        f.write("\n*\n")


def register_and_replay(frames_per_step, rec_path):
    env_kwargs = common.expand_env_kwargs(
        {
            "__include__": "config/env.yml",
            "frames_per_step": frames_per_step,
            "reduced_action_set": False,
        }
    )
    env_kwargs.pop("render_mode", None)
    print("env_kwargs", env_kwargs)

    env_id = "local/QWOP-v1"
    if env_id in registry:
        del registry[env_id]
    common.register_env(env_kwargs, env_wrappers=[])

    rec = common.load_recording(rec_path)
    actions = rec["episodes"][0]["actions"]
    assert rec["seed"] == SEED
    assert rec["episodes"][0]["skip"] is False

    env = gym.make("local/QWOP-v1")
    try:
        assert env.action_space.n == 16, env.action_space
        unwrapped = env.unwrapped
        print(
            "frames_per_step",
            unwrapped.frames_per_step,
            "n_actions_space",
            unwrapped.action_mapper.num_actions,
            "reduced",
            unwrapped.action_mapper.reduced_action_set,
        )
        assert unwrapped.frames_per_step == frames_per_step
        assert unwrapped.action_mapper.reduced_action_set is False

        obs, info0 = env.reset(seed=rec["seed"])
        print(
            "reset info",
            {k: info0.get(k) for k in ("time", "distance", "fallen", "is_success")},
        )

        last_info = info0
        terminated_at = None
        truncated_flag = False
        n_stepped = 0
        peak_distance = info0.get("distance") or 0.0
        for i, raw_action in enumerate(actions):
            action = int(raw_action)
            obs, reward, terminated, truncated, info = env.step(action)
            n_stepped += 1
            last_info = info
            dist = info.get("distance") or 0.0
            if dist > peak_distance:
                peak_distance = dist
            if terminated or truncated:
                terminated_at = i
                truncated_flag = bool(truncated)
                break
            if n_stepped % 200 == 0:
                print(
                    "progress step",
                    n_stepped,
                    "time",
                    info.get("time"),
                    "distance",
                    info.get("distance"),
                    "fallen",
                    info.get("fallen"),
                )

        result = {
            "n_stepped": n_stepped,
            "n_recorded": len(actions),
            "terminated_at_action_index": terminated_at,
            "truncated": truncated_flag,
            "peak_distance": peak_distance,
            "game_ended": unwrapped.game.game_state.game_ended,
            "info": {
                k: last_info.get(k)
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
                )
            },
        }
        return result
    finally:
        env.close()


def print_mapping(mapper, actions, meta):
    print("full actions:")
    for i, name in enumerate(mapper.get_all_action_names()):
        print("  %d: %s %s" % (i, name, mapper.action_to_keys[i]))
    print(
        "start_frame=%s last_press_frame=%s n_actions=%s fps=%s video_frames_per_action=%s"
        % (
            meta["start_frame"],
            meta["last_press_frame"],
            meta["n_actions"],
            meta["frames_per_step"],
            meta["video_frames_per_action"],
        )
    )
    print("window video t=[%.5f, %.5f)" % meta["window"])
    print("HUD duration if completed = %.5fs" % meta["hud_duration_s"])
    print("raw majority combos:")
    for k, v in meta["raw_counter"].most_common():
        print(" ", k, v, "->", mapper.action_from_keys(*k), mapper.get_action_name(mapper.action_from_keys(*k)))
    print("mapped action counts:")
    for i, name in enumerate(mapper.get_all_action_names()):
        print("  %d %s: %d" % (i, name, meta["mapped_counter"][i]))
    print("first 16", actions[:16], [mapper.get_action_name(a) for a in actions[:16]])
    print("last 8", actions[-8:], [mapper.get_action_name(a) for a in actions[-8:]])
    print("unmapped", len(meta["unmapped"]))


def main():
    mapper = ActionMapper(reduced_action_set=False)
    assert mapper.num_actions == 16
    rows = load_rows()
    frames = by_video_frame(rows)

    actions, meta = sample_actions(frames, frames_per_step=1, mapper=mapper)
    print_mapping(mapper, actions, meta)
    write_rec(REC_PATH, actions)
    print("wrote", REC_PATH, "lines", 1 + len(actions) + 1)

    print("=== REPLAY frames_per_step=1 ===")
    result = register_and_replay(1, REC_PATH)
    print("--- REPLAY fps=1 ---")
    for k, v in result.items():
        print("%s=%s" % (k, v))
    dist = result["info"].get("distance") or 0.0
    print("finish_100m", float(dist) >= 100.0)

    fallen = bool(result["info"].get("fallen"))
    early = fallen and (
        result["n_stepped"] < 150
        or float(dist) < 5.0
        or float(result["info"].get("time") or 0) < 5.0
    )
    print("fell_immediately", early)

    if early:
        print("=== extra try frames_per_step=4 full action set ===")
        actions4, meta4 = sample_actions(frames, frames_per_step=4, mapper=mapper)
        print_mapping(mapper, actions4, meta4)
        rec4 = "/tmp/kurodo_wr_full_fps4.rec"
        write_rec(rec4, actions4)
        print("wrote temp", rec4)
        result4 = register_and_replay(4, rec4)
        print("--- REPLAY fps=4 ---")
        for k, v in result4.items():
            print("%s=%s" % (k, v))
        dist4 = result4["info"].get("distance") or 0.0
        print("finish_100m", float(dist4) >= 100.0)
        print(
            "fell_immediately",
            bool(result4["info"].get("fallen"))
            and (
                result4["n_stepped"] < 50
                or float(dist4) < 5.0
                or float(result4["info"].get("time") or 0) < 5.0
            ),
        )


if __name__ == "__main__":
    main()
