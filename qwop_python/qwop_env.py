"""
QWOP Gymnasium Environment

Wraps the QWOP game in a Gymnasium-compatible interface for RL training.
Designed for maximum speed with headless mode (no rendering).

Observation: 60-dim float32 vector (12 body parts x 5 values each)
Action: Discrete(16) or Discrete(9) with reduced_action_set
Reward: Configurable. "velocity" = Δdistance/Δtime minus time cost; "distance" = metres
gained per step (encourages consistent forward progress; speed can be layered later).
Plus terminal bonuses in both modes.
"""

import time
import numpy as np
import gymnasium as gymnasium
from gymnasium import spaces

from .game import QWOPGame
from .game_js import QWOPGameJS
from .observations import ObservationExtractor
from .actions import ActionMapper
from .data import PHYSICS_TIMESTEP, SCREEN_WIDTH, SCREEN_HEIGHT, OBS_PANEL_WIDTH


class QWOPEnv(gymnasium.Env):
    """
    QWOP Gymnasium environment for RL training.

    The environment runs headlessly by default (no rendering) for maximum
    training speed. Physics runs at fixed 0.04s timesteps (25 Hz).

    Args:
        frames_per_step: Number of physics ticks per env step (default: 1)
                        frames_per_step=4 means each action lasts 0.16s
        reduced_action_set: If True, use 9 actions instead of 16 (default: False)
        failure_cost: Penalty for falling (default: 10.0)
        success_reward: Bonus for completing the course (default: 50.0)
        time_cost_mult: Multiplier for time cost in reward (default: 10.0)
        speed_rew_mult: Multiplier for velocity in reward (default: 0.01)
        reward_mode: "velocity" (current) or "distance" (reward per metre gained)
        distance_rew_mult: Scale for distance-delta reward when reward_mode=="distance" (default: 1.0)
        time_cost_mult_distance: Time cost in distance mode (default: 0.0; set >0 to penalize slow progress)
        reward_dt_mode: "sim" = use actual sim time for reward dt (default); "protocol_30hz" =
            use 30 Hz protocol clock (dt = frames_per_step/300) for reward to match qwop-gym.
        seed: Random seed for deterministic physics (default: None)
        render_mode: None (headless) or "human" (Pygame window)
        backend: "pybox2d" (default) or "js". If "js", runs physics in Planck.js via PyMiniRacer
            (no browser; requires mini-racer and qwop_python/js/planck.min.js).
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        frames_per_step=1,
        reduced_action_set=False,
        failure_cost=10.0,
        success_reward=50.0,
        time_cost_mult=10.0,
        speed_rew_mult=0.01,
        reward_mode="velocity",
        distance_rew_mult=1.0,
        time_cost_mult_distance=0.0,
        reward_dt_mode="sim",
        seed=None,
        render_mode=None,
        show_observation_panel=False,
        backend="pybox2d",
    ):
        super().__init__()

        self.render_mode = render_mode
        self.show_observation_panel = show_observation_panel
        self.backend = backend
        headless = render_mode is None
        if backend == "js":
            self.game = QWOPGameJS(seed=seed, verbose=False, headless=headless)
        else:
            self.game = QWOPGame(seed=seed, verbose=False, headless=headless)
        self.game.initialize()

        self.obs_extractor = ObservationExtractor()
        self.action_mapper = ActionMapper(reduced_action_set=reduced_action_set)

        self.frames_per_step = frames_per_step
        self.failure_cost = failure_cost
        self.success_reward = success_reward
        self.time_cost_mult = time_cost_mult
        self.speed_rew_mult = speed_rew_mult
        self.reward_mode = reward_mode
        self.distance_rew_mult = distance_rew_mult
        self.time_cost_mult_distance = time_cost_mult_distance
        self.reward_dt_mode = reward_dt_mode

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
        self._distance_buffer_size = 10

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

        raw_obs = self.obs_extractor.extract_raw(self.game.physics)
        obs = self.obs_extractor.normalize_observation(raw_obs)
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

        reward = self._calc_reward()
        self._total_reward += reward
        terminated = self.game.game_state.game_ended
        info = self._build_info()

        self._last_obs = obs
        self._last_raw_obs = raw_obs
        self._last_info = info
        self._last_action = action
        self._episode_steps += 1

        # Update distance buffer for rolling stats (matches qwop-gym FN_UPDATE_STATS).
        # Append phase: buf = [oldest, ..., newest] -> use ds = buf[-1] - buf[0].
        # Sliding phase: buf = [newest, ..., oldest] -> use ds = buf[0] - buf[-1].
        dist = self.game.game_state.score
        if len(self._distance_buffer) < self._distance_buffer_size:
            self._distance_buffer.append(dist)
        else:
            self._distance_buffer.pop()
            self._distance_buffer.insert(0, dist)

        return obs, reward, terminated, False, info
    
    def _calc_reward(self):
        """
        Calculate reward. Mode "velocity": velocity-based minus time cost.
        Mode "distance": reward per metre gained (encourages consistent forward
        progress); speed can be encouraged later.

        Uses actual simulation time (score_time delta) so reward scale matches the
        physics. qwop-gym uses game-reported time (reaction.time - last_reaction.time);
        we do the same conceptually: dt = score_time - _last_time. This keeps velocity
        and time cost consistent with the real step duration (frames_per_step * 0.04s)
        and avoids inflating the velocity term / under-penalizing time, which breaks
        QRDQN's return distribution.

        When reward_dt_mode == "protocol_30hz", dt = frames_per_step * (1/30) / 10
        (matches qwop-gym's 30 Hz clock / 25 Hz physics split). Otherwise dt = sim time delta.

        velocity mode:
          reward = velocity * speed_rew_mult - time_cost + terminal_bonus
          velocity = (distance - last_distance) / dt
          time_cost = time_cost_mult * dt / frames_per_step
        distance mode:
          reward = ds * distance_rew_mult - time_cost_distance + terminal_bonus
          time_cost_distance = time_cost_mult_distance * dt / frames_per_step
        terminal_bonus = success_reward if success, -failure_cost if fall

        Returns:
            Float reward value
        """
        dist = self.game.game_state.score  # metres (torso x / 10)
        time_val = self.game.score_time
        ds = dist - self._last_distance

        if self.reward_dt_mode == "protocol_30hz":
            # Match qwop-gym: 30 Hz clock (time = scoreTime/10, scoreTime += stepsize*(1/30) per step)
            dt = self.frames_per_step * (1 / 30) / 10
            dt = max(dt, 1e-8)
        else:
            # Use actual sim time so reward scale matches physics
            dt = time_val - self._last_time
            dt = max(dt, 1e-8)

        if self.reward_mode == "distance":
            time_cost_distance = (
                self.time_cost_mult_distance * dt / self.frames_per_step
            )
            reward = ds * self.distance_rew_mult - time_cost_distance
        else:
            velocity = ds / dt
            reward = velocity * self.speed_rew_mult - (
                self.time_cost_mult * dt / self.frames_per_step
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
        if self.reward_dt_mode != "protocol_30hz":
            self._last_time = time_val

        return float(reward)
    
    def _build_info(self):
        """
        Build info dictionary with metadata.
        
        Returns:
            Dictionary with game state information
        """
        distance = self.game.game_state.score
        time_val = self.game.score_time
        # avgspeed: cumulative to match qwop-gym (reaction.distance / reaction.time -> 10*m/s)
        avgspeed = (10.0 * distance / time_val) if time_val > 0 else 0.0
        is_success = 1.0 if (
            self.game.game_state.game_ended
            and self.game.game_state.jump_landed
            and not self.game.game_state.fallen
        ) else 0.0

        # Match qwop-gym time scale when using protocol clock (time = scoreTime/10)
        info_time = time_val / 10.0 if self.reward_dt_mode == "protocol_30hz" else time_val

        return {
            'time': info_time,
            'distance': distance,
            'avgspeed': avgspeed,
            'is_success': is_success,
            'fallen': self.game.game_state.fallen,
            'jumped': self.game.game_state.jumped,
            'jump_landed': self.game.game_state.jump_landed,
            'episode_steps': self._episode_steps,
            'total_reward': self._total_reward,
            'episode_start_time': self._episode_start_time,
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
