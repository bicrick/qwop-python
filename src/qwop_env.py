"""
QWOP Gymnasium Environment

Wraps the QWOP game in a Gymnasium-compatible interface for RL training.
Designed for maximum speed with headless mode (no rendering).

Observation: 60-dim float32 vector (12 body parts × 5 values each)
Action: Discrete(16) or Discrete(9) with reduced_action_set
Reward: Velocity-based (Δdistance/Δtime) minus time cost, plus terminal bonuses
"""

import numpy as np
import gymnasium as gymnasium
from gymnasium import spaces

from game import QWOPGame
from observations import ObservationExtractor
from actions import ActionMapper
from data import PHYSICS_TIMESTEP


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
        seed: Random seed for deterministic physics (default: None)
    """
    
    metadata = {"render_modes": []}
    
    def __init__(
        self,
        frames_per_step=1,
        reduced_action_set=False,
        failure_cost=10.0,
        success_reward=50.0,
        time_cost_mult=10.0,
        seed=None
    ):
        super().__init__()
        
        # Create game in headless mode (no rendering, no prints)
        self.game = QWOPGame(seed=seed, verbose=False, headless=True)
        self.game.initialize()
        
        # Create observation extractor and action mapper
        self.obs_extractor = ObservationExtractor()
        self.action_mapper = ActionMapper(reduced_action_set=reduced_action_set)
        
        # Environment parameters
        self.frames_per_step = frames_per_step
        self.failure_cost = failure_cost
        self.success_reward = success_reward
        self.time_cost_mult = time_cost_mult
        
        # Define observation and action spaces
        n_actions = self.action_mapper.num_actions
        self.observation_space = spaces.Box(
            shape=(60,),
            low=-1.0,
            high=1.0,
            dtype=np.float32
        )
        self.action_space = spaces.Discrete(n_actions)
        
        # Reward tracking
        self._last_distance = 0.0
        self._last_time = 0.0
        self._episode_steps = 0
    
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
        
        # Reset game
        self.game.reset(seed=seed)
        self.game.start()  # Set first_click=True so physics runs immediately
        
        # Reset tracking
        self._last_distance = 0.0
        self._last_time = 0.0
        self._episode_steps = 0
        
        # Get initial observation
        obs = self.obs_extractor.extract(self.game.physics)
        info = self._build_info()
        
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
        
        # Get observation
        obs = self.obs_extractor.extract(self.game.physics)
        
        # Calculate reward
        reward = self._calc_reward()
        
        # Check termination
        terminated = self.game.game_state.game_ended
        
        # Build info
        info = self._build_info()
        
        self._episode_steps += 1
        
        return obs, reward, terminated, False, info
    
    def _calc_reward(self):
        """
        Calculate reward based on velocity and time cost.
        
        Reward = velocity - time_cost + terminal_bonus
        where:
          velocity = (distance - last_distance) / (time - last_time)
          time_cost = time_cost_mult * dt / frames_per_step
          terminal_bonus = success_reward if success, -failure_cost if fall
        
        Returns:
            Float reward value
        """
        # Get current distance and time
        dist = self.game.game_state.score  # metres (torso x / 10)
        t = self.game.score_time  # seconds
        
        # Calculate velocity
        dt = max(t - self._last_time, 1e-8)  # Avoid division by zero
        velocity = (dist - self._last_distance) / dt
        
        # Base reward: velocity minus time cost
        reward = velocity - (self.time_cost_mult * dt / self.frames_per_step)
        
        # Terminal bonuses/penalties
        if self.game.game_state.game_ended:
            if self.game.game_state.jump_landed and not self.game.game_state.fallen:
                # Successfully cleared the course
                reward += self.success_reward
            else:
                # Fell
                reward -= self.failure_cost
        
        # Update tracking for next step
        self._last_distance = dist
        self._last_time = t
        
        return float(reward)
    
    def _build_info(self):
        """
        Build info dictionary with metadata.
        
        Returns:
            Dictionary with game state information
        """
        return {
            'distance': self.game.game_state.score,
            'time': self.game.score_time,
            'fallen': self.game.game_state.fallen,
            'jumped': self.game.game_state.jumped,
            'jump_landed': self.game.game_state.jump_landed,
            'episode_steps': self._episode_steps,
        }
    
    def close(self):
        """Clean up resources."""
        pass


# Register environment with gymnasium
try:
    from gymnasium.envs.registration import register
    
    register(
        id='QWOP-v0',
        entry_point='qwop_env:QWOPEnv',
        max_episode_steps=1000,
    )
except:
    # Registration might fail if already registered
    pass
