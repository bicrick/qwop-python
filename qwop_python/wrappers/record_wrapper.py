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

import os
import gymnasium as gym


class RecordWrapper(gym.Wrapper):
    """Records episodes to .rec files for replay / BC (load_recordings format)."""

    def __init__(self, env, rec_file, overwrite, max_time, min_distance):
        super().__init__(env)

        if os.path.exists(rec_file) and not overwrite:
            raise Exception("rec_file already exists: %s" % rec_file)

        dirname = os.path.dirname(rec_file)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        print("Recording to %s" % rec_file)
        self.rec_file = rec_file
        self.handle = open(rec_file, "w")
        seedval = getattr(env.unwrapped, "seedval", None)
        self.handle.write("seed=%d\n" % (seedval if seedval is not None else 0))
        self.overwrite = overwrite
        self.max_time = max_time or 999
        self.min_distance = min_distance or 0
        self.actions = []
        self.discarded_episodes = []
        self.n_recorded = 0
        self.n_discarded = 0

    def reset(self, **kwargs):
        self.actions = []
        return self.env.reset(**kwargs)

    def rewrite_seed_header(self, seed):
        """Replace the file header with the actual recording seed (before any eps)."""
        if self.handle is None:
            return
        if self.n_recorded or self.n_discarded or self.actions:
            raise RuntimeError("rewrite_seed_header must be called before recording")
        self.handle.close()
        with open(self.rec_file, "w") as f:
            f.write("seed=%d\n" % int(seed))
        self.handle = open(self.rec_file, "a")
        self.env.unwrapped.seedval = int(seed)

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.actions.append(str(int(action)))

        # Natural episode end (fall / finish). Also treat truncation as end so
        # TimeLimit wrappers do not leave a stale action buffer.
        if terminated or truncated:
            ep_info = "episode with time=%.2f" % info["time"]
            ep_info += " and distance=%.2f" % info["distance"]
            incomplete = False

            if incomplete:
                print("Discarded %s (incomplete)" % ep_info)
                self.discarded_episodes.append(self.actions)
                self.n_discarded += 1
            elif info["time"] > self.max_time:
                print("Discarded %s (max_time exceeded)" % ep_info)
                self.discarded_episodes.append(self.actions)
                self.n_discarded += 1
            elif info["distance"] < self.min_distance:
                print("Discarded %s (min_distance not reached)" % ep_info)
                self.discarded_episodes.append(self.actions)
                self.n_discarded += 1
            else:
                if len(self.discarded_episodes) > 0:
                    print("Dump %d discarded episodes" % len(self.discarded_episodes))
                    episodes = [ep + ["X"] for ep in self.discarded_episodes]
                    actions = [a for ep in episodes for a in ep]
                    self.handle.write("\n".join(actions) + "\n")
                    self.discarded_episodes = []

                self.handle.write("\n".join(self.actions) + "\n*\n")
                self.handle.flush()
                self.n_recorded += 1
                print("Recorded %s" % ep_info)

            self.actions = []
        elif info.get("manual_restart"):
            self.actions = []

        return obs, reward, terminated, truncated, info

    def close(self):
        if getattr(self, "handle", None) is not None:
            try:
                self.handle.flush()
                self.handle.close()
            finally:
                self.handle = None
        env = getattr(self, "env", None)
        if env is not None:
            return env.close()
