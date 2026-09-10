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
    INITIAL_CAMERA_Y,
    SCORE_TIME_STEP,
    HURDLES_ENABLED,
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
    
    def __init__(self, seed=None, verbose=True, headless=False, hurdles_enabled=None):
        """
        Initialize QWOP game.
        
        Creates all subsystems but does not initialize physics yet.
        Call initialize() after construction to set up the physics world.
        
        Args:
            seed: Optional seed for deterministic behavior (for RL compatibility)
            verbose: If True, print game events (default: True)
            headless: If True, skip non-physics extras (speed audio buffer) for faster
                training. Camera_x MUST still update — ground segment repositioning
                depends on it. Skipping camera in headless stalls the track ~18m.
            hurdles_enabled: If set, override data.HURDLES_ENABLED for this instance
        """
        self.verbose = verbose
        self.headless = headless
        if hurdles_enabled is None:
            hurdles_enabled = HURDLES_ENABLED
        self.hurdles_enabled = bool(hurdles_enabled)
        
        # Core subsystems
        self.physics = PhysicsWorld(
            verbose=verbose, hurdles_enabled=self.hurdles_enabled
        )
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
            dt: Ignored for the HUD clock. Real QWOP advances scoreTime by 1/30
                per update while Box2D always steps 0.04; we match that drive.
                Kept as an argument for call-site compatibility.
        """
        # Step 1: Score time update — HUD clock (JS scoreTime += 1/30), not
        # PHYSICS_TIMESTEP. Physics still steps a fixed 0.04 below.
        if not self.pause and not self.game_state.game_ended:
            self.score_time += SCORE_TIME_STEP
        
        # Step 3: Floor repositioning (infinite scrolling)
        self._reposition_ground_segments()
        
        # Step 4: Head stabilization torque (critical for balance)
        if not self.game_state.fallen:
            head = self.physics.get_body('head')
            if head is not None:
                torque = HEAD_TORQUE_FACTOR * (head.angle + HEAD_TORQUE_OFFSET)
                head.ApplyTorque(torque, True)
        
        # Step 5: Speed tracking (rolling average for future audio / UI)
        # Safe to skip in headless — not required for physics or ground scroll.
        if not self.headless:
            head = self.physics.get_body('head')
            if head is not None:
                self.speed_array.append(head.linearVelocity[0])
                if len(self.speed_array) > SPEED_ARRAY_MAX:
                    self.speed_array.pop(0)
                self.average_speed = sum(self.speed_array) / len(self.speed_array) if self.speed_array else 0.0
        
        # Step 6: Control input processing
        self.controls.apply()
        
        # Step 8: Physics simulation step (fixed 0.04s timestep)
        if self.first_click and not self.pause:
            self.physics.step()
        
        # Step 9: Camera follow logic
        # ALWAYS update camera_x even when headless. _reposition_ground_segments()
        # keys off camera_x; without it the track stops scrolling and the runner
        # stalls around ~18m with no feet/track contact for further progress.
        # camera_y is cheap and kept in sync for parity; no pygame blit/UI here.
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
    
    def _max_abs_body_velocity(self):
        """
        Max absolute linear (x/y) or angular velocity across player bodies.

        Used by settle_spawn to detect when the athlete has come to rest.
        """
        max_v = 0.0
        for body in self.physics.bodies.values():
            lv = body.linearVelocity
            max_v = max(max_v, abs(lv[0]), abs(lv[1]), abs(body.angularVelocity))
        return max_v

    def settle_spawn(self, max_steps=20, velocity_threshold=0.08, min_steps=6):
        """
        Plant the athlete at rest after spawn (sim-to-real transfer).

        Python Box2D and browser QWOP both spawn with feet floating. Free-fall
        then first contact diverge across Box2D ports and cause early faceplants
        on transfer. With keys up, run a few physics steps (same head torque as
        normal update), early-exit when velocities are small, then zero velocities
        and race clocks so the episode starts planted at t=0.

        Does not change friction coefficients or the race PHYSICS_TIMESTEP /
        SCORE_TIME_STEP drive — only a pre-episode settle.

        Args:
            max_steps: Cap on settle physics steps (default 20)
            velocity_threshold: Early-exit when max abs body velocity is below
                this (default 0.08)
            min_steps: Minimum steps before early-exit is allowed (default 6)
        """
        # Keys up; allow physics to run (same as post-reset race start).
        self.controls.reset()
        self.pause = False
        self.first_click = True

        for step_i in range(max_steps):
            # Same head stabilization torque as update() — critical for balance.
            if not self.game_state.fallen:
                head = self.physics.get_body("head")
                if head is not None:
                    torque = HEAD_TORQUE_FACTOR * (head.angle + HEAD_TORQUE_OFFSET)
                    head.ApplyTorque(torque, True)

            # Keys up → motors zeroed; still call apply for parity with update().
            self.controls.apply()
            self.physics.step()

            # Keep track under the athlete while they drop onto the ground.
            self._reposition_ground_segments()
            self._update_camera()

            if step_i + 1 >= min_steps and self._max_abs_body_velocity() < velocity_threshold:
                break

        # Hard stop residual motion from contact / solver noise.
        for body in self.physics.bodies.values():
            body.linearVelocity = (0.0, 0.0)
            body.angularVelocity = 0.0

        # Race clocks start at zero from the planted pose (not mid free-fall).
        self.score_time = 0.0
        self.game_state.score = 0.0
        self.speed_array = []
        self.average_speed = 0.0
        self._update_camera()

        if self.verbose:
            print(
                f"✓ Spawn settled after physics steps "
                f"(max |v|={self._max_abs_body_velocity():.4f})"
            )

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
