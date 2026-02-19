"""
QWOP Observation Extraction - RL Interface

Extracts observations from the physics world in the exact format used by QWOPGYM.
Produces a 60-float normalized observation vector matching the JavaScript implementation.

Observation structure:
- 12 body parts × 5 values each = 60 floats
- Per body part: [pos_x, pos_y, angle, vel_x, vel_y]
- All values normalized to [-1, 1] range
"""

import numpy as np


class Normalizer:
    """
    Normalizes values to [-1, 1] range using center-based normalization.
    
    Formula: (value - center) / maxdev
    Where: center = (min + max) / 2, maxdev = max - center
    
    Matches the normalization in QWOPGYM's Normalizable class.
    """
    
    def __init__(self, limit_min, limit_max):
        """
        Initialize normalizer with value range.
        
        Args:
            limit_min: Minimum expected value
            limit_max: Maximum expected value
        """
        self.limit_min = float(limit_min)
        self.limit_max = float(limit_max)
        self.center = (limit_min + limit_max) / 2.0
        self.maxdev = limit_max - self.center
        
        # Track actual min/max seen (for debugging)
        self.min_seen = 0.0
        self.max_seen = 0.0
    
    def normalize(self, value):
        """
        Normalize a value to [-1, 1] range.
        
        Args:
            value: Raw value to normalize
            
        Returns:
            Normalized value (will be clamped to [-1, 1])
        """
        norm = (value - self.center) / self.maxdev
        
        # Track extremes for debugging
        if value > self.max_seen:
            self.max_seen = value
        elif value < self.min_seen:
            self.min_seen = value
        
        return norm
    
    def denormalize(self, norm):
        """
        Convert normalized value back to original scale.
        
        Args:
            norm: Normalized value in [-1, 1]
            
        Returns:
            Original scale value
        """
        return norm * self.maxdev + self.center


class ObservationExtractor:
    """
    Extracts RL observations from QWOP physics world.
    
    Produces a 60-float numpy array matching QWOPGYM's observation format:
    - 12 body parts in specific order
    - 5 values per body part: [pos_x, pos_y, angle, vel_x, vel_y]
    - All values normalized to [-1, 1]
    
    Body part order (must match QWOPGYM exactly):
    torso, head, leftArm, leftCalf, leftFoot, leftForearm, leftThigh,
    rightArm, rightCalf, rightFoot, rightForearm, rightThigh
    """
    
    # Body parts in exact order from QWOPGYM extensions.js
    BODY_PART_ORDER = [
        'torso', 'head', 'leftArm', 'leftCalf', 'leftFoot', 'leftForearm',
        'leftThigh', 'rightArm', 'rightCalf', 'rightFoot', 'rightForearm',
        'rightThigh'
    ]
    
    def __init__(self):
        """
        Initialize observation extractor with normalizers.
        
        Normalization ranges from QWOPGYM:
        - pos_x: [-10, 1050]
        - pos_y: [-10, 10]
        - angle: [-6, 6] radians
        - vel_x: [-20, 60]
        - vel_y: [-25, 60]
        """
        self.pos_x = Normalizer(-10, 1050)
        self.pos_y = Normalizer(-10, 10)
        self.angle = Normalizer(-6, 6)
        self.vel_x = Normalizer(-20, 60)
        self.vel_y = Normalizer(-25, 60)
    
    def extract_raw(self, physics_world):
        """
        Extract raw (unnormalized) observation from physics world.
        
        Args:
            physics_world: PhysicsWorld instance
            
        Returns:
            numpy array of 60 floats (unnormalized)
        """
        obs = np.zeros(60, dtype=np.float32)
        
        for i, body_name in enumerate(self.BODY_PART_ORDER):
            body = physics_world.get_body(body_name)
            if body is None:
                raise ValueError(f"Body part '{body_name}' not found in physics world")
            
            # Extract position, angle, velocity
            # CRITICAL: Use worldCenter (not position) to match JavaScript's getPosition()
            pos = body.worldCenter
            angle = body.angle
            vel = body.linearVelocity
            
            # Store in observation array (5 values per body part)
            idx = i * 5
            obs[idx] = pos[0]      # x position
            obs[idx + 1] = pos[1]  # y position
            obs[idx + 2] = angle   # angle (radians)
            obs[idx + 3] = vel[0]  # x velocity
            obs[idx + 4] = vel[1]  # y velocity
        
        return obs
    
    def normalize_observation(self, raw_obs):
        """
        Normalize raw observation to [-1, 1] range.
        
        Args:
            raw_obs: Raw 60-float observation array
            
        Returns:
            Normalized observation clamped to [-1, 1]
        """
        norm_obs = np.zeros(60, dtype=np.float32)
        
        # Normalize each body part's 5 values
        for i in range(0, 60, 5):
            norm_obs[i] = self.pos_x.normalize(raw_obs[i])
            norm_obs[i + 1] = self.pos_y.normalize(raw_obs[i + 1])
            norm_obs[i + 2] = self.angle.normalize(raw_obs[i + 2])
            norm_obs[i + 3] = self.vel_x.normalize(raw_obs[i + 3])
            norm_obs[i + 4] = self.vel_y.normalize(raw_obs[i + 4])
        
        # Clamp to [-1, 1] (matches QWOPGYM behavior)
        np.clip(norm_obs, -1, 1, out=norm_obs)
        
        return norm_obs
    
    def extract(self, physics_world):
        """
        Extract normalized observation from physics world.
        
        Args:
            physics_world: PhysicsWorld instance
            
        Returns:
            numpy array of 60 float32 values, normalized to [-1, 1]
        """
        raw_obs = self.extract_raw(physics_world)
        return self.normalize_observation(raw_obs)
    
    def get_normalizer_stats(self):
        """
        Get statistics about observed value ranges (for debugging).
        
        Returns:
            dict with min/max seen for each normalizer
        """
        return {
            'pos_x': {'min': self.pos_x.min_seen, 'max': self.pos_x.max_seen, 
                      'range': [self.pos_x.limit_min, self.pos_x.limit_max]},
            'pos_y': {'min': self.pos_y.min_seen, 'max': self.pos_y.max_seen,
                      'range': [self.pos_y.limit_min, self.pos_y.limit_max]},
            'angle': {'min': self.angle.min_seen, 'max': self.angle.max_seen,
                      'range': [self.angle.limit_min, self.angle.limit_max]},
            'vel_x': {'min': self.vel_x.min_seen, 'max': self.vel_x.max_seen,
                      'range': [self.vel_x.limit_min, self.vel_x.limit_max]},
            'vel_y': {'min': self.vel_y.min_seen, 'max': self.vel_y.max_seen,
                      'range': [self.vel_y.limit_min, self.vel_y.limit_max]},
        }
