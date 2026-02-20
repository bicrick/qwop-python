"""
QWOP Game Logic - Main Game Loop and State Management

Orchestrates all subsystems (physics, collision, controls) and implements
the complete game update loop matching the original QWOP's exact sequence.

This is the "brain" of the game that owns the main update loop.
"""

import math

from .physics import PhysicsWorld
from .collision import GameState, QWOPContactListener
from .controls import ControlsHandler
from .data import (
    WORLD_SCALE,
    SCREEN_WIDTH,
    HEAD_TORQUE_FACTOR,
    HEAD_TORQUE_OFFSET,
    SPEED_ARRAY_MAX,
    CAMERA_VERTICAL_THRESHOLD,
    CAMERA_VERTICAL_OFFSET,
    CAMERA_HORIZONTAL_OFFSET,
    INITIAL_CAMERA_X,
    INITIAL_CAMERA_Y
)


class QWOPGame:
    """
    Main QWOP game class that manages the complete game state and update loop.
    
    This class:
    - Owns and coordinates all subsystems (physics, collision, controls)
    - Implements the 11-step update loop from the original QWOP
    - Manages game state (pause, first_click, score_time)
    - Handles camera system
    - Provides reset functionality
    
    The update loop sequence exactly matches QWOP_FUNCTIONS_EXACT.md lines 10-189.
    """
    
    def __init__(self, seed=None, verbose=True, headless=False):
        """
        Initialize QWOP game.
        
        Creates all subsystems but does not initialize physics yet.
        Call initialize() after construction to set up the physics world.
        
        Args:
            seed: Optional seed for deterministic behavior (for RL compatibility)
            verbose: If True, print game events (default: True)
            headless: If True, skip camera/speed tracking for faster training (default: False)
        """
        self.verbose = verbose
        self.headless = headless
        
        # Core subsystems
        self.physics = PhysicsWorld(verbose=verbose)
        self.game_state = GameState()
        self.contact_listener = QWOPContactListener(self.game_state, verbose=verbose)
        self.controls = ControlsHandler(self.physics)
        
        # Game state flags
        self.pause = False
        self.first_click = False  # Set to True when game starts
        self.help_up = False  # Help overlay visible (pauses game)
        
        # Timing
        self.score_time = 0.0  # Time elapsed in seconds
        
        # Speed tracking (for future audio implementation)
        self.speed_array = []
        self.average_speed = 0.0
        
        # Camera state
        self.camera_x = INITIAL_CAMERA_X  # -200 pixels
        self.camera_y = INITIAL_CAMERA_Y  # -200 pixels
        self.camera_offset = CAMERA_HORIZONTAL_OFFSET  # -14
        
        # RNG seed (for RL compatibility)
        self.seed = seed
        if seed is not None:
            # Box2D is deterministic by default, but we store the seed
            # in case any future features need RNG
            import random
            import numpy as np
            random.seed(seed)
            np.random.seed(seed)
    
    def initialize(self):
        """
        Initialize the physics world and wire up collision detection.
        
        Call this once at game startup after construction.
        """
        if self.verbose:
            print("=" * 70)
            print("QWOP GAME INITIALIZATION")
            print("=" * 70)
        
        # Initialize physics (creates world, ground, bodies, joints)
        self.physics.initialize()
        
        # Wire up collision detection
        self.physics.set_contact_listener(self.contact_listener)
        
        if self.verbose:
            print("=" * 70)
            print("✓ QWOP Game Ready!")
            print("=" * 70)
            print()
    
    def start(self):
        """
        Start the game (called when user first presses a key or starts playing).
        
        Sets first_click = True which enables physics simulation.
        """
        if not self.first_click:
            self.first_click = True
            if self.verbose:
                print("✓ Game started!")

    def toggle_help(self):
        """Toggle help overlay. When shown, pauses the game."""
        self.help_up = not self.help_up
        self.pause = self.help_up
    
    def update(self, dt):
        """
        Main game update loop - runs once per frame.
        
        Implements the exact 11-step sequence from original QWOP's update(dt):
        1. Score time update
        2. [Skip accelerometer - mobile only]
        3. Floor repositioning (infinite scrolling)
        4. Head stabilization torque
        5. Speed tracking
        6. Control input processing
        7. [Skip UI sprite updates - rendering concern]
        8. Physics simulation step
        9. Camera follow logic
        10. Score calculation
        11. Game end check
        
        Args:
            dt: Delta time in seconds (typically 1/60 = 0.0167s for 60 FPS)
        """
        # Step 1: Score time update
        if not self.pause and not self.game_state.game_ended:
            self.score_time += dt
        
        # Step 3: Floor repositioning (infinite scrolling)
        self._reposition_ground_segments()
        
        # Step 4: Head stabilization torque (min.js 868: -4 * (angle + .2))
        if not self.game_state.fallen:
            head = self.physics.get_body('head')
            if head is not None:
                torque = HEAD_TORQUE_FACTOR * (head.angle + HEAD_TORQUE_OFFSET)
                head.ApplyTorque(torque, True)
        
        # Step 5: Speed tracking (rolling average for future audio)
        # Skip in headless mode for performance
        if not self.headless:
            head = self.physics.get_body('head')
            if head is not None:
                self.speed_array.append(head.linearVelocity[0])
                if len(self.speed_array) > SPEED_ARRAY_MAX:
                    self.speed_array.pop(0)
                self.average_speed = sum(self.speed_array) / len(self.speed_array) if self.speed_array else 0.0
        
        # Step 6: Control input processing
        self.controls.apply()
        
        # Step 8: Physics simulation step (min.js 905: step(.04, 5, 5))
        if self.first_click and not self.pause:
            self.physics.step()
        
        # Step 9: Camera follow logic
        # Skip in headless mode for performance
        if not self.headless:
            self._update_camera()
        
        # Step 10: Score calculation (freeze when game ended to prevent shifting)
        if not self.game_state.jump_landed and not self.game_state.game_ended:
            torso = self.physics.get_body('torso')
            if torso is not None:
                self.game_state.score = round(torso.worldCenter[0]) / 10
        
        # Step 11: Game end check
        if self.game_state.jump_landed and not self.game_state.game_ended:
            self.pause = True
            self.end_game()
        elif not self.game_state.jump_landed and not self.game_state.game_ended and self.game_state.fallen:
            self.end_game()
    
    def _reposition_ground_segments(self):
        """
        Reposition ground segments for infinite scrolling.
        
        Each segment moves to stay ahead of the camera, creating the illusion
        of an infinite track. Uses the exact formula from the original QWOP.
        """
        for i, ground_body in enumerate(self.physics.ground_segments):
            new_x = (math.floor(self.camera_x / SCREEN_WIDTH) + i) * SCREEN_WIDTH / WORLD_SCALE
            
            # Only update if position changed (avoids unnecessary updates)
            if abs(new_x - ground_body.position[0]) > 0.001:
                ground_body.position = (new_x, ground_body.position[1])
    
    def _update_camera(self):
        """
        Update camera position to follow the player.
        
        Camera behavior from QWOP_FUNCTIONS_EXACT.md lines 152-175:
        - Horizontal: Follows torso x position (when not fallen)
        - Vertical: Follows torso y when jumping high (y < -5)
        """
        if not self.first_click:
            return
        
        torso = self.physics.get_body('torso')
        if torso is None:
            return
        
        world_center = torso.worldCenter
        
        # Vertical camera follow (when jumping high)
        if world_center[1] < CAMERA_VERTICAL_THRESHOLD:  # y < -5
            self.camera_y = world_center[1] * WORLD_SCALE + CAMERA_VERTICAL_OFFSET
        
        # Horizontal camera follow (normal running, not when fallen)
        elif not self.game_state.fallen:
            self.camera_x = (world_center[0] + self.camera_offset) * WORLD_SCALE
    
    def end_game(self):
        """
        Handle game over.
        
        Called when:
        - Player falls (upper body touches ground)
        - Player successfully lands in sand pit after jump
        """
        if self.game_state.game_ended:
            return
        
        self.game_state.game_ended = True
        
        # Update high score if needed
        if self.game_state.score > self.game_state.high_score:
            self.game_state.high_score = self.game_state.score
        
        if self.verbose:
            print()
            print("=" * 70)
            print("GAME OVER")
            print("=" * 70)
            print(f"Final Score: {self.game_state.score:.1f} metres")
            print(f"Time: {self.score_time:.1f} seconds")
            print(f"High Score: {self.game_state.high_score:.1f} metres")
            
            if self.game_state.jump_landed and not self.game_state.fallen:
                print("Status: SUCCESS! You cleared the hurdle!")
            else:
                print("Status: Fell")
            
            print("=" * 70)
            print()
    
    def reset(self, seed=None):
        """
        Reset the game to initial state.
        
        Called when user presses 'R' key to restart, or by RL environment.
        
        Args:
            seed: Optional new seed for deterministic behavior
        
        Resets:
        - Physics (destroys and recreates player bodies/joints)
        - Game state (all flags, score, high score preserved)
        - Controls (all keys released)
        - Camera position
        - Timing
        """
        if self.verbose:
            print()
            print("Resetting game...")
        
        # Update seed if provided
        if seed is not None:
            self.seed = seed
            import random
            import numpy as np
            random.seed(seed)
            np.random.seed(seed)
        elif self.seed is not None:
            # Re-seed with same seed for deterministic resets
            import random
            import numpy as np
            random.seed(self.seed)
            np.random.seed(self.seed)
        
        # Reset controls
        self.controls.reset()
        
        # Reset physics (destroys and recreates player)
        self.physics.reset()
        
        # Reset game state (creates new instance)
        old_high_score = self.game_state.high_score
        self.game_state = GameState()
        self.game_state.high_score = old_high_score  # Preserve high score
        
        # Update contact listener to use new game state
        self.contact_listener.game_state = self.game_state
        
        # Reset game flags (keep first_click True - user already started, don't show intro again)
        self.pause = False
        self.first_click = True
        self.help_up = False
        
        # Reset timing
        self.score_time = 0.0
        
        # Reset speed tracking
        self.speed_array = []
        self.average_speed = 0.0
        
        # Reset camera (matches JS line 849: set_x(-10 * l.worldScale))
        self.camera_x = INITIAL_CAMERA_X
        self.camera_y = INITIAL_CAMERA_Y
        
        if self.verbose:
            print("✓ Game reset complete")
            print()
