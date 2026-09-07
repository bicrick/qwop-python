"""
QWOP Gymnasium Environment

Wraps the QWOP game in a Gymnasium-compatible interface for RL training.
Designed for maximum speed with headless mode (no rendering).

Observation: 60-dim float32 vector (12 body parts x 5 values each)
Action: Discrete(16) or Discrete(9) with reduced_action_set
Reward: Distance-based (meters traveled) plus velocity, minus time cost, plus terminal bonuses
"""

import time
import numpy as np
import gymnasium as gymnasium
from gymnasium import spaces

from .game import QWOPGame
from .observations import ObservationExtractor
from .actions import ActionMapper
from .data import PHYSICS_TIMESTEP, SCORE_TIME_STEP, SCREEN_WIDTH, SCREEN_HEIGHT, OBS_PANEL_WIDTH


class QWOPEnv(gymnasium.Env):
    """
    QWOP Gymnasium environment for RL training.

    The environment runs headlessly by default (no rendering) for maximum
    training speed. Box2D steps at fixed 0.04s; the HUD/score clock advances
    by 1/30 s per update (matching real HTML/JS QWOP).

    Args:
        frames_per_step: Number of physics ticks per env step (default: 1)
                        frames_per_step=4 means each action lasts 4 updates
        reduced_action_set: If True, use 9 actions instead of 16 (default: False)
        failure_cost: Penalty for falling (default: 10.0)
        success_reward: Bonus for completing the course (default: 50.0)
        time_cost_mult: Multiplier for time cost in reward (default: 10.0)
        distance_rew_mult: Multiplier for distance traveled in reward (default: 10.0)
        speed_rew_mult: Multiplier for velocity in reward (default: 0.2)
        seed: Random seed for deterministic physics (default: None)
        render_mode: None (headless) or "human" (Pygame window)
        hurdles_enabled: If set, override data.HURDLES_ENABLED (default off).
            Set True for browser-parity runs with the mid-track hurdle.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        frames_per_step=1,
        reduced_action_set=False,
        failure_cost=10.0,
        success_reward=50.0,
        time_cost_mult=10.0,
        distance_rew_mult=10.0,
        speed_rew_mult=0.2,
        seed=None,
        render_mode=None,
        show_observation_panel=False,
        hurdles_enabled=None,
    ):
        super().__init__()

        self.render_mode = render_mode
        self.show_observation_panel = show_observation_panel
        headless = render_mode is None
        self.game = QWOPGame(
            seed=seed, verbose=False, headless=headless, hurdles_enabled=hurdles_enabled
        )
        self.game.initialize()

        self.obs_extractor = ObservationExtractor()
        self.action_mapper = ActionMapper(reduced_action_set=reduced_action_set)

        self.frames_per_step = frames_per_step
        self.failure_cost = failure_cost
        self.success_reward = success_reward
        self.time_cost_mult = time_cost_mult
        self.distance_rew_mult = distance_rew_mult
        self.speed_rew_mult = speed_rew_mult

        n_actions = self.action_mapper.num_actions
        self.observation_space = spaces.Box(
            shape=(60,),
            low=-1.0,
            high=1.0,
            dtype=np.float32
        )
        self.action_space = spaces.Discrete(n_actions)

        self._last_distance = 0.0
        self._last_time = 0.0
        self._episode_steps = 0
        self._total_reward = 0.0
        self._episode_start_time = 0.0
        self._distance_buffer = []
        self._distance_buffer_size = 100  # Larger window to prevent oscillation from yielding positive velocity reward
        # Mid-race split marks (metres). Times filled with physics score_time on first cross.
        # Needed for WR iteration: Kurodo insight — WR is mid-race, not start.
        self._split_marks_m = (10.0, 50.0, 100.0)
        self._split_times = {m: None for m in self._split_marks_m}

        self.seedval = int(seed) if seed is not None else None
        self._last_obs = None
        self._last_raw_obs = None
        self._last_info = None
        self._last_action = 0
        self._screen = None
        self._game_surface = None
        self._renderer = None
        if render_mode == "human":
            import pygame
            pygame.init()
            width = (SCREEN_WIDTH + OBS_PANEL_WIDTH) if show_observation_panel else SCREEN_WIDTH
            self._screen = pygame.display.set_mode(
                (width, SCREEN_HEIGHT)
            )
            pygame.display.set_caption("QWOP - Python")
            self._game_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            from .renderer import QWOPRenderer
            self._renderer = QWOPRenderer(self._game_surface)
    
    def reset(self, seed=None, options=None):
        """
        Reset environment to initial state.

        Args:
            seed: Optional seed for deterministic reset
            options: Additional options (unused)

        Returns:
            observation: 60-dim float32 array
            info: Dictionary with metadata
        """
        super().reset(seed=seed)

        if seed is not None:
            self.seedval = int(seed)

        self.game.reset(seed=seed)
        self.game.start()

        self._last_distance = 0.0
        self._last_time = 0.0
        self._episode_steps = 0
        self._total_reward = 0.0
        self._episode_start_time = time.time()
        self._distance_buffer = []
        self._split_times = {m: None for m in self._split_marks_m}

        raw_obs = self.obs_extractor.extract_raw(self.game.physics)
        obs = self.obs_extractor.normalize_observation(raw_obs)
        self._update_split_times()
        info = self._build_info()
        self._last_obs = obs
        self._last_raw_obs = raw_obs
        self._last_info = info
        self._last_action = 0

        return obs, info
    
    def step(self, action):
        """
        Take one environment step.
        
        Args:
            action: Integer action index
            
        Returns:
            observation: 60-dim float32 array
            reward: Float reward
            terminated: Whether episode ended
            truncated: Whether episode was truncated (always False)
            info: Dictionary with metadata
        """
        # Apply action
        self.action_mapper.apply_action(action, self.game.controls)
        
        # Run physics for frames_per_step ticks
        for _ in range(self.frames_per_step):
            if not self.game.game_state.game_ended:
                self.game.update(dt=PHYSICS_TIMESTEP)
        
        # Get observation (raw for display, normalized for RL)
        raw_obs = self.obs_extractor.extract_raw(self.game.physics)
        obs = self.obs_extractor.normalize_observation(raw_obs)

        # Update distance buffer before reward (so _calc_reward can use smoothed velocity)
        dist = self.game.game_state.score
        if len(self._distance_buffer) < self._distance_buffer_size:
            self._distance_buffer.append(dist)
        else:
            self._distance_buffer.pop()
            self._distance_buffer.insert(0, dist)

        reward = self._calc_reward()
        self._total_reward += reward
        terminated = self.game.game_state.game_ended
        self._update_split_times()
        info = self._build_info()

        self._last_obs = obs
        self._last_raw_obs = raw_obs
        self._last_info = info
        self._last_action = action
        self._episode_steps += 1

        return obs, reward, terminated, False, info

    def _update_split_times(self):
        """
        Record physics score_time when distance first crosses 10 / 50 / 100 m.

        Uses game.score_time (real physics seconds), not protocol-scaled reward time.
        Values stay sticky once set so episode-end Monitor info has the splits.
        """
        distance = self.game.game_state.score
        score_time = self.game.score_time
        for mark in self._split_marks_m:
            if self._split_times[mark] is None and distance >= mark:
                self._split_times[mark] = float(score_time)
    
    def _calc_reward(self):
        """
        Calculate reward based on distance, velocity, and time cost.

        Uses protocol-scale dt to match qwop-wr / qwop-gym RL logs:
          protocol_time = HUD_scoreTime / 10
        where HUD scoreTime advances by SCORE_TIME_STEP (1/30) per update.
        Box2D still steps PHYSICS_TIMESTEP (0.04); do not confuse the two.

        Velocity is SMOOTHED over the distance buffer when len(buffer) >= 2 to prevent
        oscillation/jitter from generating spurious rewards when the agent is stationary.

        Reward = distance_rew_mult * ds + velocity * speed_rew_mult - time_cost + terminal_bonus
        where:
          ds = distance - last_distance (meters traveled)
          velocity = smoothed over buffer when available, else instantaneous
          time_cost = time_cost_mult * dt_protocol / frames_per_step
          dt_protocol = frames_per_step * (1/30) / 10  (matches qwop-wr extensions.js)
          terminal_bonus = success_reward if success, -failure_cost if fall

        Returns:
            Float reward value
        """
        dist = self.game.game_state.score  # metres (torso x / 10)
        ds = dist - self._last_distance

        # Protocol-scale dt: qwop-gym logs time = scoreTime/10
        dt_protocol = self.frames_per_step * SCORE_TIME_STEP / 10
        dt_protocol = max(dt_protocol, 1e-8)

        # Use smoothed velocity over buffer when available (prevents oscillation exploitation)
        buf = self._distance_buffer
        if len(buf) >= 2:
            if len(buf) < self._distance_buffer_size:
                # Growing: buf = [oldest, ..., newest]
                ds_smooth = buf[-1] - buf[0]
            else:
                # Full: buf = [newest, oldest, ..., second_newest]
                ds_smooth = buf[0] - buf[1]
            dt_smooth = (len(buf) - 1) * dt_protocol
            velocity = ds_smooth / dt_smooth if dt_smooth > 0 else 0.0
        else:
            velocity = ds / dt_protocol
        reward = (
            self.distance_rew_mult * ds
            + velocity * self.speed_rew_mult
            - (self.time_cost_mult * dt_protocol / self.frames_per_step)
        )
        
        # Terminal bonuses/penalties
        if self.game.game_state.game_ended:
            if self.game.game_state.jump_landed and not self.game.game_state.fallen:
                # Successfully cleared the course
                reward += self.success_reward
            else:
                # Fell
                reward -= self.failure_cost
        
        self._last_distance = dist

        return float(reward)
    
    def _rolling_distance_delta(self):
        """
        Metres gained over the distance buffer window.

        Buffer layout matches _calc_reward:
          - Growing: [oldest, ..., newest] → ds = newest - oldest
          - Full:    [newest, oldest, ..., second_newest] → ds = newest - oldest
        """
        buf = self._distance_buffer
        if len(buf) < 2:
            return 0.0
        if len(buf) < self._distance_buffer_size:
            return buf[-1] - buf[0]
        return buf[0] - buf[1]

    def _build_info(self):
        """
        Build info dictionary with metadata.

        ``time`` is HUD seconds (`game.score_time`), matching real HTML/JS
        QWOP: +SCORE_TIME_STEP (1/30) per update while Box2D steps 0.04.
        Human WR 45.530s is on this clock. qwop-gym RL protocol time ≈ time/10.

        ``distance`` is metres (torso world-x / 10).

        Success (`is_success`) is land-based: jump_landed and not fallen
        (sand-pit land / JS endGame). This differs from qwop-gym's common
        ``distance >= 100`` escape criterion — see TRANSFER_AND_METRICS.md.

        Speed fields:
          - ``speed_mps``: metres / HUD-seconds over the rolling buffer (or
            distance/time). Prefer this for claims.
          - ``avgspeed``: legacy qwop-gym ``FN_UPDATE_STATS`` formula
            ``10 * ds / dt_box2d``. Because ``distance`` is already in metres,
            that factor of 10 makes avgspeed ~Box2D-world-units/s
            (~10x too high vs metres/s). Kept for API compatibility;
            do not use it for reward shaping or WR claims.
        """
        distance = self.game.game_state.score
        time_val = self.game.score_time
        buf = self._distance_buffer
        n_intervals = max(len(buf) - 1, 1)
        dt_hud = SCORE_TIME_STEP * self.frames_per_step * n_intervals
        # Legacy avgspeed denominator used Box2D dt (pre-HUD-alignment).
        dt_box2d = PHYSICS_TIMESTEP * self.frames_per_step * n_intervals

        if len(buf) >= 2:
            ds = self._rolling_distance_delta()
            # Honest m/s on the HUD clock (comparable to browser scoreTime).
            speed_mps = ds / (dt_hud or 1.0)
            # Legacy qwop-gym formula (intentionally ~10x high vs m/s).
            # Uses historical buffer endpoints (buf[0]-buf[-1]) and Box2D dt.
            ds_legacy = buf[0] - buf[-1]
            avgspeed = 10 * ds_legacy / (dt_box2d or 1.0)
        else:
            speed_mps = distance / time_val if time_val > 0 else 0.0
            avgspeed = speed_mps

        is_success = 1.0 if (
            self.game.game_state.game_ended
            and self.game.game_state.jump_landed
            and not self.game.game_state.fallen
        ) else 0.0

        # -1.0 = mark not reached this episode (Monitor needs a numeric info keyword)
        split_10 = self._split_times[10.0]
        split_50 = self._split_times[50.0]
        split_100 = self._split_times[100.0]

        return {
            'time': time_val,
            'distance': distance,
            'speed_mps': speed_mps,
            'avgspeed': avgspeed,
            'is_success': is_success,
            'fallen': self.game.game_state.fallen,
            'jumped': self.game.game_state.jumped,
            'jump_landed': self.game.game_state.jump_landed,
            'episode_steps': self._episode_steps,
            'total_reward': self._total_reward,
            'episode_start_time': self._episode_start_time,
            'split_10m_time': float(split_10) if split_10 is not None else -1.0,
            'split_50m_time': float(split_50) if split_50 is not None else -1.0,
            'split_100m_time': float(split_100) if split_100 is not None else -1.0,
        }
    
    def render(self):
        """Render one frame. Only works when render_mode='human'."""
        if self.render_mode != "human" or self._screen is None or self._renderer is None:
            return None
        import pygame
        self._renderer.render(self.game)
        self._screen.blit(self._game_surface, (0, 0))
        if self.show_observation_panel and self._last_raw_obs is not None:
            info = self._last_info or self._build_info()
            self._renderer.draw_observation_panel(
                self._screen, SCREEN_WIDTH, 0,
                self._last_raw_obs, info
            )
        pygame.display.flip()
        return None

    def get_keys_to_action(self):
        """Return mapping from key tuples to action indices for gymnasium.utils.play."""
        keymap = {}
        for i in range(self.action_mapper.num_actions):
            keys = self.action_mapper.action_to_keys[i]
            key_tuple = tuple(sorted(k.upper() for k, v in keys.items() if v))
            if not key_tuple:
                key_tuple = ()
            keymap[key_tuple] = i
        return keymap

    def close(self):
        """Clean up resources."""
        if self.render_mode == "human":
            import pygame
            pygame.quit()


# Register environment with gymnasium
try:
    from gymnasium.envs.registration import register
    
    register(
        id='QWOP-v0',
        entry_point='qwop_python.qwop_env:QWOPEnv',
        max_episode_steps=1000,
    )
except:
    # Registration might fail if already registered
    pass
