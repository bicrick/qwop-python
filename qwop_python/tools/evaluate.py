# =============================================================================
# Copyright 2023 Simeon Manolov <s.manolloff@gmail.com>.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""
Headless evaluation of a saved SB3 model.

Reports HUD-clock metrics (aligned with real HTML/JS QWOP):
  - time: info['time'] = game.score_time (+1/30 per update; Box2D still steps 0.04)
  - distance: metres (torso x / 10)
  - speed_mps: distance/time for the episode (honest m/s on the HUD clock)
  - is_success / stuck / truncated

Do not use info['avgspeed'] for WR claims — see doc/TRANSFER_AND_METRICS.md.
"""

from __future__ import annotations

import glob
import json
import os
import statistics
import time
from typing import Any

import gymnasium as gymnasium
from gymnasium.wrappers import TimeLimit

from . import common
from .spectate import load_model


def _resolve_model_file(pattern: str) -> str:
    if os.path.isfile(pattern):
        return pattern
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError("No model file matched: %s" % pattern)
    return matches[-1]


def evaluate(cfg: dict[str, Any]) -> dict[str, Any]:
    model_file = _resolve_model_file(cfg["model_file"])
    model_mod = cfg.get("model_mod", "stable_baselines3")
    model_cls = cfg.get("model_cls", "PPO")
    n_episodes = int(cfg.get("n_episodes", 100))
    seed = cfg.get("seed")
    max_episode_steps = int(cfg.get("max_episode_steps", 2500))
    deterministic = bool(cfg.get("deterministic", True))
    render = bool(cfg.get("render", False))
    out_json = cfg.get("out_json")

    model = load_model(model_mod, model_cls, model_file)

    env = gymnasium.make("local/QWOP-v1")
    env = TimeLimit(env, max_episode_steps=max_episode_steps)

    human_wr_s = float(cfg.get("human_wr_seconds", 45.530))
    finish_distance_m = float(cfg.get("finish_distance_m", 100.0))

    episodes: list[dict[str, Any]] = []
    t0 = time.time()

    try:
        for ep in range(n_episodes):
            ep_seed = None if seed is None else int(seed) + ep
            obs, info = env.reset(seed=ep_seed)
            terminated = False
            truncated = False
            ep_reward = 0.0
            steps = 0

            while not (terminated or truncated):
                action, _ = model.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = env.step(action)
                ep_reward += float(reward)
                steps += 1
                if render:
                    env.render()

            distance = float(info.get("distance", 0.0))
            hud_time = float(info.get("time", 0.0))
            # Episode-mean speed from HUD clock (honest claim metric).
            speed_episode = (
                distance / hud_time if hud_time > 0 else 0.0
            )
            rolling_speed = float(
                info.get("speed_mps", info.get("avgspeed", 0.0))
            )
            is_success = float(info.get("is_success", 0.0)) == 1.0
            stuck = bool(info.get("stuck", False))
            fallen = bool(info.get("fallen", False))
            beats_wr = (
                is_success
                and distance >= finish_distance_m
                and hud_time > 0
                and hud_time < human_wr_s
            )

            row = {
                "episode": ep,
                "seed": ep_seed,
                "steps": steps,
                "time": hud_time,
                "distance": distance,
                "speed_mps": speed_episode,
                "speed_mps_rolling": rolling_speed,
                "avgspeed_legacy": float(info.get("avgspeed", 0.0)),
                "is_success": is_success,
                "fallen": fallen,
                "stuck": stuck,
                "truncated": truncated,
                "beats_human_wr": beats_wr,
                "total_reward": ep_reward,
            }
            episodes.append(row)

            status = (
                "SUCCESS"
                if is_success
                else ("STUCK" if stuck else ("TRUNC" if truncated else "FALL"))
            )
            print(
                "ep=%03d  %s  time=%.3fs  dist=%.2fm  speed=%.3f m/s  steps=%d"
                % (ep, status, hud_time, distance, speed_episode, steps)
            )
    finally:
        env.close()

    wall = time.time() - t0
    successes = [e for e in episodes if e["is_success"]]
    times = [e["time"] for e in episodes]
    dists = [e["distance"] for e in episodes]
    speeds = [e["speed_mps"] for e in episodes]
    success_times = [e["time"] for e in successes]

    summary = {
        "model_file": model_file,
        "n_episodes": n_episodes,
        "max_episode_steps": max_episode_steps,
        "human_wr_seconds": human_wr_s,
        "wall_seconds": wall,
        "success_rate": len(successes) / n_episodes if n_episodes else 0.0,
        "n_success": len(successes),
        "n_stuck": sum(1 for e in episodes if e["stuck"]),
        "n_fallen": sum(1 for e in episodes if e["fallen"] and not e["is_success"]),
        "n_truncated": sum(1 for e in episodes if e["truncated"] and not e["stuck"]),
        "n_beats_human_wr": sum(1 for e in episodes if e["beats_human_wr"]),
        "mean_time_s": statistics.mean(times) if times else 0.0,
        "mean_distance_m": statistics.mean(dists) if dists else 0.0,
        "mean_speed_mps": statistics.mean(speeds) if speeds else 0.0,
        "best_success_time_s": min(success_times) if success_times else None,
        "mean_success_time_s": (
            statistics.mean(success_times) if success_times else None
        ),
    }

    print("\n=== Eval summary (HUD clock = browser scoreTime) ===")
    print("model: %s" % model_file)
    print(
        "episodes=%d  success_rate=%.1f%%  stuck=%d  trunc=%d"
        % (
            n_episodes,
            100.0 * summary["success_rate"],
            summary["n_stuck"],
            summary["n_truncated"],
        )
    )
    print(
        "mean time=%.3fs  mean dist=%.2fm  mean speed=%.3f m/s"
        % (
            summary["mean_time_s"],
            summary["mean_distance_m"],
            summary["mean_speed_mps"],
        )
    )
    if summary["best_success_time_s"] is not None:
        print(
            "best success time=%.3fs (human WR %.3fs)  beats_wr=%d"
            % (
                summary["best_success_time_s"],
                human_wr_s,
                summary["n_beats_human_wr"],
            )
        )
    else:
        print("no successful finishes")
    print("wall=%.1fs" % wall)

    result = {"summary": summary, "episodes": episodes}
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w") as f:
            json.dump(result, f, indent=2)
        print("Wrote %s" % out_json)

    return result
