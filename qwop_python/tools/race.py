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
import copy
import gymnasium as gym

from . import common
from .spectate import load_model
from ..data import SCREEN_WIDTH, SCREEN_HEIGHT


HEADER_HEIGHT = 24
RACE_PANEL_WIDTH = 400


def _expand_and_merge_env_kwargs(base, overrides):
    """Expand base (with __include__) and merge model overrides. Returns new dict."""
    base_copy = copy.deepcopy(base)
    merged = common.expand_env_kwargs(base_copy) | (overrides or {})
    merged["render_mode"] = None
    return merged


def _to_time_str(seconds):
    """Format seconds as MM:SS.T"""
    m = int(seconds // 60)
    sec = int(seconds % 60)
    tenth = int((seconds - int(seconds)) * 10) % 10
    return f"{m:02d}:{sec:02d}.{tenth}"


def _draw_race_panel(screen, x, y, name_a, name_b, stats, info_a=None, info_b=None):
    """Draw the center stats panel with game-style styling and column-separated layout."""
    import pygame

    panel_w = RACE_PANEL_WIDTH
    panel_h = HEADER_HEIGHT + SCREEN_HEIGHT

    pad = 6
    col_label = 100
    col_a = 100
    col_b = 100
    cell_h = 18

    pygame.font.init()
    title_font = pygame.font.SysFont("verdana", 14, bold=True)
    header_font = pygame.font.SysFont("verdana", 12, bold=True)
    value_font = pygame.font.SysFont("verdana", 11)
    micro_font = pygame.font.SysFont("verdana", 10)

    bg_dark = (28, 30, 34)
    border = (70, 75, 85)
    text_primary = (240, 242, 245)
    text_muted = (160, 165, 175)
    accent_a = (100, 180, 120)
    accent_b = (100, 150, 200)

    pygame.draw.rect(screen, bg_dark, (x, y, panel_w, panel_h))
    pygame.draw.rect(screen, border, (x, y, panel_w, panel_h), 2)
    divider_x = x + pad + col_label + col_a + 2
    pygame.draw.line(screen, border, (divider_x, y + pad), (divider_x, y + panel_h - pad), 1)

    row_y = y + pad

    title = title_font.render("RACE STATS", True, text_primary)
    screen.blit(title, (x + (panel_w - title.get_width()) // 2, row_y))
    row_y += cell_h + 4

    pygame.draw.line(screen, border, (x + pad, row_y), (x + panel_w - pad, row_y), 1)
    row_y += pad + 2

    col_a_x = x + pad + col_label + 4
    col_b_x = x + pad + col_label + col_a + 4

    def _row(label, val_a, val_b, label_color=None):
        nonlocal row_y
        lc = label_color or text_muted
        surf_l = value_font.render(str(label), True, lc)
        surf_a = value_font.render(str(val_a), True, text_primary)
        surf_b = value_font.render(str(val_b), True, text_primary)
        screen.blit(surf_l, (x + pad, row_y + 2))
        screen.blit(surf_a, (col_a_x, row_y + 2))
        screen.blit(surf_b, (col_b_x, row_y + 2))
        row_y += cell_h

    total_runs = stats.get("total_runs", 0)
    decisive = stats.get("decisive_races", 0)
    wins_a = stats.get("wins_a", 0)
    wins_b = stats.get("wins_b", 0)
    completes_a = stats.get("completes_a", 0)
    completes_b = stats.get("completes_b", 0)
    falls_a = stats.get("falls_a", 0)
    falls_b = stats.get("falls_b", 0)
    times_a = stats.get("completion_times_a", [])
    times_b = stats.get("completion_times_b", [])
    speeds_a = stats.get("completion_speeds_a", [])
    speeds_b = stats.get("completion_speeds_b", [])

    win_pct_a = (100 * wins_a / decisive) if decisive > 0 else 0
    win_pct_b = (100 * wins_b / decisive) if decisive > 0 else 0
    complete_pct_a = (100 * completes_a / total_runs) if total_runs > 0 else 0
    complete_pct_b = (100 * completes_b / total_runs) if total_runs > 0 else 0
    avg_time_a = sum(times_a) / len(times_a) if times_a else 0
    avg_time_b = sum(times_b) / len(times_b) if times_b else 0
    best_time_a = min(times_a) if times_a else 0
    best_time_b = min(times_b) if times_b else 0
    avg_speed_a = sum(speeds_a) / len(speeds_a) if speeds_a else 0
    avg_speed_b = sum(speeds_b) / len(speeds_b) if speeds_b else 0

    header_a = header_font.render(name_a, True, accent_a)
    header_b = header_font.render(name_b, True, accent_b)
    screen.blit(header_a, (col_a_x, row_y - 2))
    screen.blit(header_b, (col_b_x, row_y - 2))
    row_y += cell_h
    pygame.draw.line(screen, border, (x + pad, row_y), (x + panel_w - pad, row_y), 1)
    row_y += pad

    _row("Wins", wins_a, wins_b)
    _row("Win %", f"{win_pct_a:.0f}%", f"{win_pct_b:.0f}%")
    _row("Completes", f"{completes_a} ({complete_pct_a:.0f}%)", f"{completes_b} ({complete_pct_b:.0f}%)")
    _row("Falls", falls_a, falls_b)
    row_y += 4
    _row("Avg time", _to_time_str(avg_time_a) if times_a else "-", _to_time_str(avg_time_b) if times_b else "-")
    _row("Best time", _to_time_str(best_time_a) if times_a else "-", _to_time_str(best_time_b) if times_b else "-")
    _row("Avg speed", f"{avg_speed_a:.1f} m/s" if speeds_a else "-", f"{avg_speed_b:.1f} m/s" if speeds_b else "-")

    row_y += 8
    pygame.draw.line(screen, border, (x + pad, row_y), (x + panel_w - pad, row_y), 1)
    row_y += pad + 2
    races_text = value_font.render(f"Decisive races: {decisive}  |  Total runs: {total_runs}", True, text_muted)
    screen.blit(races_text, (x + pad, row_y + 2))
    row_y += cell_h

    if info_a and info_b:
        row_y += 36
        pygame.draw.line(screen, border, (x + pad, row_y), (x + panel_w - pad, row_y), 1)
        row_y += pad + 2
        live_header = micro_font.render("Current race", True, text_muted)
        screen.blit(live_header, (x + pad, row_y))
        row_y += cell_h
        d_a = info_a.get("distance", 0)
        d_b = info_b.get("distance", 0)
        t_a = info_a.get("time", 0)
        t_b = info_b.get("time", 0)
        s_a = info_a.get("avgspeed", 0)
        s_b = info_b.get("avgspeed", 0)
        _row("Distance", f"{d_a:.1f}m", f"{d_b:.1f}m")
        _row("Time", _to_time_str(t_a), _to_time_str(t_b))
        _row("Speed", f"{s_a:.1f} m/s", f"{s_b:.1f} m/s")


def _check_pygame_quit():
    """Process pygame events and raise UserQuitRequested if user closed the window."""
    import pygame

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            raise common.UserQuitRequested()


def race(cfg):
    fps = cfg.get("fps", 30)
    reset_delay = cfg.get("reset_delay", 1)
    steps_per_step = cfg.get("steps_per_step", 4)

    model_a_cfg = cfg.get("model_a", {})
    model_b_cfg = cfg.get("model_b", {})
    if not model_a_cfg or not model_b_cfg:
        raise ValueError("race config requires model_a and model_b")

    base_env = cfg.get("base_env_kwargs", cfg.get("env_kwargs", {}))
    env_wrappers = cfg.get("env_wrappers", [])

    kwargs_a = _expand_and_merge_env_kwargs(base_env, model_a_cfg.get("env_kwargs", {}))
    kwargs_b = _expand_and_merge_env_kwargs(base_env, model_b_cfg.get("env_kwargs", {}))

    common.register_env(kwargs_a, env_wrappers, env_id="local/QWOP-race-A")
    common.register_env(kwargs_b, env_wrappers, env_id="local/QWOP-race-B")

    model_a = load_model(
        model_a_cfg.get("mod", "stable_baselines3"),
        model_a_cfg.get("cls", "PPO"),
        model_a_cfg["file"],
    )
    model_b = load_model(
        model_b_cfg.get("mod", "stable_baselines3"),
        model_b_cfg.get("cls", "PPO"),
        model_b_cfg["file"],
    )

    name_a = model_a_cfg.get("name", "Model A")
    name_b = model_b_cfg.get("name", "Model B")

    env_a = gym.make("local/QWOP-race-A")
    env_b = gym.make("local/QWOP-race-B")

    import pygame
    from ..renderer import QWOPRenderer

    pygame.init()
    total_width = SCREEN_WIDTH + RACE_PANEL_WIDTH + SCREEN_WIDTH
    total_height = HEADER_HEIGHT + SCREEN_HEIGHT
    screen = pygame.display.set_mode((total_width, total_height))
    pygame.display.set_caption("QWOP Race")

    surface_a = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surface_b = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer_a = QWOPRenderer(surface_a)
    renderer_b = QWOPRenderer(surface_b)

    clock = common.Clock(fps)
    stats = {
        "wins_a": 0,
        "wins_b": 0,
        "decisive_races": 0,
        "total_runs": 0,
        "completes_a": 0,
        "completes_b": 0,
        "falls_a": 0,
        "falls_b": 0,
        "completion_times_a": [],
        "completion_times_b": [],
        "completion_speeds_a": [],
        "completion_speeds_b": [],
    }

    try:
        while True:
            seed = common.gen_seed()
            obs_a, info_a = env_a.reset(seed=seed)
            obs_b, info_b = env_b.reset(seed=seed)

            terminated_a = False
            terminated_b = False

            while not (terminated_a and terminated_b):
                _check_pygame_quit()

                if not terminated_a:
                    action_a, _ = model_a.predict(obs_a)
                if not terminated_b:
                    action_b, _ = model_b.predict(obs_b)

                for _ in range(steps_per_step):
                    _check_pygame_quit()

                    if not terminated_a:
                        obs_a, _, terminated_a, _, info_a = env_a.step(action_a)
                        env_a.unwrapped.game._update_camera()
                    if not terminated_b:
                        obs_b, _, terminated_b, _, info_b = env_b.step(action_b)
                        env_b.unwrapped.game._update_camera()

                    renderer_a.render(env_a.unwrapped.game)
                    renderer_b.render(env_b.unwrapped.game)
                    screen.blit(surface_a, (0, HEADER_HEIGHT))
                    screen.blit(surface_b, (SCREEN_WIDTH + RACE_PANEL_WIDTH, HEADER_HEIGHT))
                    header_font = pygame.font.SysFont("verdana", 18, bold=True)
                    header_a = header_font.render(name_a, True, (255, 255, 255))
                    header_b = header_font.render(name_b, True, (255, 255, 255))
                    screen.fill((30, 30, 30), (0, 0, SCREEN_WIDTH, HEADER_HEIGHT))
                    screen.fill((30, 30, 30), (SCREEN_WIDTH + RACE_PANEL_WIDTH, 0, SCREEN_WIDTH, HEADER_HEIGHT))
                    screen.blit(header_a, (10, 4))
                    screen.blit(header_b, (SCREEN_WIDTH + RACE_PANEL_WIDTH + 10, 4))
                    _draw_race_panel(screen, SCREEN_WIDTH, 0, name_a, name_b, stats, info_a, info_b)
                    pygame.display.flip()
                    clock.tick()
                    if terminated_a and terminated_b:
                        break

            success_a = info_a.get("is_success", 0) == 1.0
            success_b = info_b.get("is_success", 0) == 1.0
            fallen_a = info_a.get("fallen", False)
            fallen_b = info_b.get("fallen", False)

            stats["total_runs"] += 1
            if success_a:
                stats["completes_a"] += 1
                stats["completion_times_a"].append(info_a.get("time", 0))
                stats["completion_speeds_a"].append(info_a.get("avgspeed", 0))
            else:
                stats["falls_a"] += 1
            if success_b:
                stats["completes_b"] += 1
                stats["completion_times_b"].append(info_b.get("time", 0))
                stats["completion_speeds_b"].append(info_b.get("avgspeed", 0))
            else:
                stats["falls_b"] += 1

            if success_a and success_b:
                time_a = info_a.get("time", float("inf"))
                time_b = info_b.get("time", float("inf"))
                if time_a < time_b:
                    stats["wins_a"] += 1
                    stats["decisive_races"] += 1
                elif time_b < time_a:
                    stats["wins_b"] += 1
                    stats["decisive_races"] += 1
            elif success_a and fallen_b:
                stats["wins_a"] += 1
                stats["decisive_races"] += 1
            elif fallen_a and success_b:
                stats["wins_b"] += 1
                stats["decisive_races"] += 1

            time.sleep(reset_delay)
    except common.UserQuitRequested:
        pass
    finally:
        env_a.close()
        env_b.close()
        pygame.quit()
