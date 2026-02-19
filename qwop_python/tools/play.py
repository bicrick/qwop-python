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

import time
import pygame
import gymnasium as gym

from . import common


def play(seed, run_id, fps, reset_delay=1):
    """Interactive play using env. Supports recording via RecordWrapper in config."""
    env = gym.make("local/QWOP-v1", seed=seed)

    try:
        obs, info = env.reset()
        clock = pygame.time.Clock()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    elif event.key in (pygame.K_r, pygame.K_SPACE):
                        obs, info = env.reset()

            action_mapper = env.unwrapped.action_mapper
            q = pygame.key.get_pressed()[pygame.K_q]
            w = pygame.key.get_pressed()[pygame.K_w]
            o = pygame.key.get_pressed()[pygame.K_o]
            p = pygame.key.get_pressed()[pygame.K_p]
            action = action_mapper.action_from_keys(q=q, w=w, o=o, p=p)
            if action is None:
                action = 0

            obs, reward, terminated, truncated, info = env.step(action)
            env.render()
            clock.tick(fps)

            if terminated or truncated:
                if reset_delay > 0:
                    time.sleep(reset_delay)
                obs, info = env.reset()
    finally:
        env.close()
