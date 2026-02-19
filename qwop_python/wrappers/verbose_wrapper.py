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

import numpy as np
import time
import gymnasium as gym


class VerboseWrapper(gym.Wrapper):
    """On each step, prints action along with some game stats."""

    def __init__(self, env):
        super().__init__(env=env)
        self.n_steps = 0
        self.total_reward = np.float32(0)
        self.last_distance = np.float32(0)
        self.last_time = np.float32(0)
        self.start_time = time.time()
        self.enabled = True

    def reset(self, *args, **kwargs):
        self.n_steps = 0
        self.total_reward = np.float32(0)
        self.last_distance = np.float32(0)
        self.last_time = np.float32(0)
        self.start_time = time.time()
        return self.env.reset(*args, **kwargs)

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)

        if not self.enabled:
            return obs, reward, terminated, truncated, info

        self.n_steps += 1
        self.total_reward += reward

        keys_dict = self.env.unwrapped.action_mapper.action_to_keys[action]
        keys = ""
        keys += "Q" if keys_dict["q"] else "."
        keys += "W" if keys_dict["w"] else "."
        keys += "O" if keys_dict["o"] else "."
        keys += "P" if keys_dict["p"] else "."
        if terminated:
            keys = "XXXX"

        dt = info["time"] - self.last_time
        v = (info["distance"] - self.last_distance) / dt if dt > 0 else 0

        time_str = str(info["time"])
        time_int = int(info["time"])
        time_frac = time_str.split(".")[-1][:1] if "." in time_str else "0"

        print(
            "%-05d | %-4s | %-4s | %-6sm | %-6s m/s | %-6s | %6s.%s s | %-6s"
            % (
                self.n_steps,
                action,
                keys,
                round(info["distance"], 1),
                round(v, 1),
                round(reward, 2),
                time_int,
                time_frac,
                round(self.total_reward, 2),
            )
        )

        elapsed_time = time.time() - self.start_time

        if terminated:
            print("Game over")
            print("Elapsed time (real): %.1f seconds" % elapsed_time)
            print("Elapsed time (game): %.1f seconds" % info["time"])
            print("Distance ran: %.1f m" % info["distance"])
            print("Average speed: %.1f m/s" % info["avgspeed"])
            print("FPS: %.1f" % (self.n_steps / elapsed_time))

        self.last_distance = info["distance"]
        self.last_time = info["time"]

        return obs, reward, terminated, truncated, info

    def disable_verbose_wrapper(self):
        self.enabled = False

    def enable_verbose_wrapper(self):
        self.enabled = True
