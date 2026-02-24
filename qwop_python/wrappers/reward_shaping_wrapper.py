"""
Reward Shaping Wrapper

Adds additional reward signals to encourage good form and discourage bad behaviors:
- Posture penalty: Penalizes low torso height (discourages scooting)
- Energy penalty: Penalizes frequent action changes (discourages jitter)
- Joint limit penalty: Penalizes extreme joint angles (discourages splits)

Based on qwop-wr's reward shaping approach.
"""

import numpy as np
import gymnasium as gymnasium
from gymnasium import spaces


class RewardShapingWrapper(gymnasium.Wrapper):
    """
    Wraps QWOP environment with additional reward shaping.
    
    The wrapper adds several auxiliary reward components to the base reward:
    
    1. Posture Penalty: Negative reward when torso is too low
       - Discourages "scooting" behavior where agent drags body on ground
       - Formula: -posture_weight * max(0, posture_threshold - torso_height)
       
    2. Energy Penalty: Negative reward for changing actions
       - Discourages rapid jittering between actions
       - Formula: -energy_weight * (action != last_action)
       
    3. Joint Limit Penalty: Negative reward for extreme joint angles
       - Discourages doing splits or other extreme poses
       - Formula: -joint_weight * num_joints_at_limit
    
    Args:
        env: QWOP environment to wrap
        posture_weight: Weight for posture penalty (default: 0.1)
        posture_threshold: Torso height threshold in meters (default: 0.5)
        energy_weight: Weight for energy penalty (default: 0.01)
        joint_weight: Weight for joint limit penalty (default: 0.05)
        joint_limit_threshold: Fraction of limit to trigger penalty (default: 0.9)
    """
    
    def __init__(
        self,
        env,
        posture_weight=0.1,
        posture_threshold=0.5,
        energy_weight=0.01,
        joint_weight=0.05,
        joint_limit_threshold=0.9
    ):
        super().__init__(env)
        
        self.posture_weight = posture_weight
        self.posture_threshold = posture_threshold
        self.energy_weight = energy_weight
        self.joint_weight = joint_weight
        self.joint_limit_threshold = joint_limit_threshold
        
        # Track previous action for energy penalty
        self.last_action = None
        
        # Track shaped rewards for info
        self.shaped_reward_components = {
            'base': 0.0,
            'posture': 0.0,
            'energy': 0.0,
            'joint': 0.0,
        }
    
    def reset(self, **kwargs):
        """Reset environment and tracking variables."""
        self.last_action = None
        self.shaped_reward_components = {
            'base': 0.0,
            'posture': 0.0,
            'energy': 0.0,
            'joint': 0.0,
        }
        return self.env.reset(**kwargs)
    
    def step(self, action):
        """
        Take step with reward shaping.
        
        Args:
            action: Action to take
            
        Returns:
            observation, shaped_reward, terminated, truncated, info
        """
        # Take base step
        obs, base_reward, terminated, truncated, info = self.env.step(action)
        
        # Calculate shaped reward components
        posture_penalty = self._calculate_posture_penalty()
        energy_penalty = self._calculate_energy_penalty(action)
        joint_penalty = self._calculate_joint_penalty()
        
        # Total shaped reward
        shaped_reward = (
            base_reward +
            posture_penalty +
            energy_penalty +
            joint_penalty
        )
        
        # Store components in info
        self.shaped_reward_components = {
            'base': base_reward,
            'posture': posture_penalty,
            'energy': energy_penalty,
            'joint': joint_penalty,
            'total': shaped_reward,
        }
        info['shaped_rewards'] = self.shaped_reward_components.copy()
        
        # Update tracking
        self.last_action = action
        
        return obs, shaped_reward, terminated, truncated, info
    
    def _calculate_posture_penalty(self):
        """
        Calculate penalty for low torso posture.
        
        Returns:
            Float penalty (negative or zero)
        """
        # Get torso body from physics world
        torso = self.env.game.physics.get_body('torso')
        if torso is None:
            return 0.0
        
        # Get torso height (y position)
        torso_height = torso.worldCenter[1]
        
        # Penalty if below threshold (y is negative upward in Box2D)
        # Lower y means higher position, so we penalize high y values
        if torso_height > -self.posture_threshold:
            penalty = -self.posture_weight * (self.posture_threshold + torso_height)
            return penalty
        
        return 0.0
    
    def _calculate_energy_penalty(self, action):
        """
        Calculate penalty for changing actions.
        
        Args:
            action: Current action
            
        Returns:
            Float penalty (negative or zero)
        """
        if self.last_action is None:
            return 0.0
        
        # Penalize action changes
        if action != self.last_action:
            return -self.energy_weight
        
        return 0.0
    
    def _calculate_joint_penalty(self):
        """
        Calculate penalty for joints at extreme angles.
        
        Returns:
            Float penalty (negative or zero)
        """
        # Get all joints from physics world
        joints = self.env.game.physics.joints
        
        penalty = 0.0
        num_at_limit = 0
        
        for joint_name, joint in joints.items():
            # Check if joint has limits (Box2D uses limits property)
            try:
                lower_limit = joint.lowerLimit
                upper_limit = joint.upperLimit
            except AttributeError:
                # Joint doesn't have limits
                continue
            
            # Check if limits are enabled (if limits are equal, they're disabled)
            if abs(upper_limit - lower_limit) < 1e-6:
                continue
            
            # Get current angle
            angle = joint.angle
            
            # Calculate distance from limits
            limit_range = upper_limit - lower_limit
            
            # Check if close to limits
            dist_from_lower = abs(angle - lower_limit)
            dist_from_upper = abs(angle - upper_limit)
            
            threshold_dist = limit_range * (1.0 - self.joint_limit_threshold)
            
            if dist_from_lower < threshold_dist or dist_from_upper < threshold_dist:
                num_at_limit += 1
        
        if num_at_limit > 0:
            penalty = -self.joint_weight * num_at_limit
        
        return penalty


class VelocityIncentiveWrapper(gymnasium.Wrapper):
    """
    Adds exponential velocity bonuses to encourage high speeds.
    
    Based on qwop-wr's velocity incentive wrapper which uses exponential
    rewards to heavily favor faster running speeds.
    
    Formula: velocity_weight * (velocity ** velocity_exponent)
    
    Example with exponent=2.5, weight=2.0:
    - 5 m/s:  112 reward/step
    - 8 m/s:  362 reward/step (3.2x)
    - 12 m/s: 995 reward/step (8.9x)
    
    Args:
        env: QWOP environment to wrap
        velocity_weight: Multiplier for velocity reward (default: 2.0)
        velocity_exponent: Exponent for velocity (default: 2.5)
    """
    
    def __init__(
        self,
        env,
        velocity_weight=2.0,
        velocity_exponent=2.5
    ):
        super().__init__(env)
        
        self.velocity_weight = velocity_weight
        self.velocity_exponent = velocity_exponent
        
        self.last_distance = 0.0
        self.last_time = 0.0
    
    def reset(self, **kwargs):
        """Reset environment and tracking variables."""
        obs, info = self.env.reset(**kwargs)
        self.last_distance = 0.0
        self.last_time = 0.0
        return obs, info
    
    def step(self, action):
        """
        Take step with velocity incentive.
        
        Args:
            action: Action to take
            
        Returns:
            observation, incentivized_reward, terminated, truncated, info
        """
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        # Use avgspeed (smoothed over 100-frame buffer) when available to avoid oscillation rewards
        dist = info['distance']
        t = info['time']
        dt = max(t - self.last_time, 1e-8)
        instant_velocity = (dist - self.last_distance) / dt
        velocity = info.get('avgspeed', instant_velocity)
        if velocity < 0:
            velocity = 0.0
        
        # Exponential velocity bonus
        if velocity > 0:
            velocity_bonus = self.velocity_weight * (velocity ** self.velocity_exponent)
        else:
            velocity_bonus = 0.0
        
        # Add to reward
        incentivized_reward = reward + velocity_bonus
        
        # Add to info
        if 'shaped_rewards' not in info:
            info['shaped_rewards'] = {}
        info['shaped_rewards']['velocity_bonus'] = velocity_bonus
        info['velocity'] = velocity
        
        # Update tracking
        self.last_distance = dist
        self.last_time = t
        
        return obs, incentivized_reward, terminated, truncated, info


class ProgressiveVelocityIncentiveWrapper(VelocityIncentiveWrapper):
    """
    Progressive velocity incentive that ramps up over training.

    Gradually increases velocity bonus weights as training progresses via
    set_progress(progress_remaining) called by VelocityRewardSchedulerCallback.
    Allows the agent to first maintain competence, then optimize for speed.

    Args:
        env: QWOP environment to wrap
        initial_velocity_weight: Starting weight for velocity bonus
        final_velocity_weight: Final weight for velocity bonus
        initial_exponent: Starting exponent for velocity
        final_exponent: Final exponent for velocity
        ramp_fraction: Fraction of training over which to ramp (default: 0.5)
    """

    def __init__(
        self,
        env,
        initial_velocity_weight=0.5,
        final_velocity_weight=2.0,
        initial_exponent=1.5,
        final_exponent=2.5,
        ramp_fraction=0.5,
    ):
        super().__init__(
            env,
            velocity_weight=initial_velocity_weight,
            velocity_exponent=initial_exponent,
        )
        self.initial_velocity_weight = initial_velocity_weight
        self.final_velocity_weight = final_velocity_weight
        self.initial_exponent = initial_exponent
        self.final_exponent = final_exponent
        self.ramp_fraction = ramp_fraction
        self._progress_remaining = 1.0

    def set_progress(self, progress_remaining: float):
        """Update weights based on training progress. Called by VelocityRewardSchedulerCallback."""
        self._progress_remaining = progress_remaining
        ramp_progress = min(1.0, (1.0 - progress_remaining) / self.ramp_fraction)
        self.velocity_weight = (
            self.initial_velocity_weight
            + ramp_progress * (self.final_velocity_weight - self.initial_velocity_weight)
        )
        self.velocity_exponent = (
            self.initial_exponent
            + ramp_progress * (self.final_exponent - self.initial_exponent)
        )
