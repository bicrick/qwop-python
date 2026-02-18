"""
QWOP Collision Detection System

Implements Box2D contact callbacks for collision detection:
- Foot + Track: Jump detection, landing detection, score updates
- Upper body + Track: Fall detection, game over

All logic is 1:1 with the original QWOP game.
"""

from Box2D import b2ContactListener, b2WorldManifold

from data import (
    WORLD_SCALE,
    SAND_PIT_AT,
    JUMP_TRIGGER_OFFSET,
    IMPACT_SOUND_THRESHOLD
)


class GameState:
    """
    Shared game state container for collision detection.
    
    This class holds all the flags and values that the collision listener
    needs to read and mutate. In Stage 6, this will be owned by game.py.
    
    Attributes:
        game_over: Whether game has ended (player fell or completed)
        game_ended: Whether end-game sequence has been triggered
        fallen: Whether player has fallen (upper body touched ground)
        jumped: Whether player has triggered jump sequence (foot past 19780)
        jump_landed: Whether player has landed in sand pit (foot past 20000)
        score: Current score in meters (torso x position / 10)
        high_score: Best score achieved
        impact_speed: Last collision impact velocity (for sound selection)
    """
    
    def __init__(self):
        self.game_over = False
        self.game_ended = False
        self.fallen = False
        self.jumped = False
        self.jump_landed = False
        self.score = 0.0
        self.high_score = 0.0
        self.impact_speed = 0.0


class QWOPContactListener(b2ContactListener):
    """
    Box2D contact listener for QWOP collision detection.
    
    Implements BeginContact to detect:
    - Foot touching track (normal running, jump trigger, landing)
    - Upper body touching track (fall detection)
    
    All logic matches original QWOP.js lines 912-954.
    """
    
    def __init__(self, game_state):
        """
        Initialize contact listener with game state.
        
        Args:
            game_state: GameState instance to read/mutate during collisions
        """
        b2ContactListener.__init__(self)
        self.game_state = game_state
    
    def BeginContact(self, contact):
        """
        Called when two fixtures begin touching.
        
        Implements exact logic from QWOP_FUNCTIONS_EXACT.md lines 191-310:
        1. Extract fixture/body data and userData strings
        2. Get world manifold contact points
        3. Find rightmost contact point for distance tracking
        4. Check for foot + track collision (jump/landing)
        5. Check for upper body + track collision (fall)
        
        Args:
            contact: b2Contact object from Box2D
        """
        # 1. Extract collision data
        fixtureA = contact.fixtureA
        fixtureB = contact.fixtureB
        bodyA = fixtureA.body
        bodyB = fixtureB.body
        userDataA = bodyA.userData
        userDataB = bodyB.userData
        
        # Skip if either body has no userData
        if userDataA is None or userDataB is None:
            return
        
        # 2. Get world manifold and contact points
        # PyBox2D returns worldManifold with points as tuples (x, y)
        worldManifold = contact.worldManifold
        points = worldManifold.points
        
        # 3. Find rightmost contact point (for distance tracking)
        # Points are tuples (x, y) in PyBox2D
        maxX = -100000
        for point in points:
            # Handle both tuple and object access
            point_x = point[0] if isinstance(point, tuple) else point.x
            if point_x > maxX:
                maxX = point_x
        
        # Get Y position of first contact point
        if len(points) > 0:
            contactY = points[0][1] if isinstance(points[0], tuple) else points[0].y
        else:
            contactY = 0
        
        # 4. Match original QWOP fixture ordering exactly for 1:1 agent transfer
        # Original: s=fixtureB.body, i=fixtureA.body, n=userDataB, r=userDataA
        # Foot: ("leftFoot"==n || "rightFoot"==r) && "track"==r
        #   -> requires userDataA=="track", and (userDataB=="leftFoot" OR userDataB=="rightFoot" when r=track)
        #   -> When track==r (A=track): leftFoot==n catches B=leftFoot. rightFoot==r is always false (r=track).
        #   -> Original ONLY catches (A=track, B=leftFoot). rightFoot is never caught.
        # Fall: (rightForearm|leftForearm|rightArm|leftArm|head)==n && "track"==r
        #   -> requires A=track, B=upper body part
        
        if userDataA != "track":
            return
        
        userDataB_val = userDataB
        body_part_body = bodyB
        track_body = bodyA
        
        # 5. FOOT + TRACK: original only handles (A=track, B=leftFoot)
        if userDataB_val == "leftFoot":
            self._handle_foot_contact(maxX, contactY)
        # 6. UPPER BODY + TRACK: fall detection
        elif userDataB_val in ["head", "leftArm", "rightArm", "leftForearm", "rightForearm"]:
            self._handle_fall_contact(maxX, contactY, body_part_body, track_body)
    
    def _handle_foot_contact(self, maxX, contactY):
        """
        Handle foot touching track (normal running, jump detection, landing).
        
        Logic from QWOP_FUNCTIONS_EXACT.md lines 224-260:
        - Jump trigger at x > 19780 (sandPitAt - 220)
        - Landing trigger at x > 20000 (sandPitAt)
        - Score updates
        
        Args:
            maxX: Rightmost contact point X in world coordinates
            contactY: Contact point Y in world coordinates
        """
        gs = self.game_state
        
        # Skip if game ended or already fallen (original checks gameOver and fallen)
        if gs.game_ended or gs.fallen:
            return
        
        # Jump detection (approaching sand pit)
        if not gs.jumped and maxX * WORLD_SCALE > (SAND_PIT_AT - JUMP_TRIGGER_OFFSET):
            gs.jumped = True
            print(f"✓ Jump triggered at x={maxX * WORLD_SCALE:.1f}")
        
        # Landing detection (in sand pit)
        if gs.jumped and not gs.jump_landed:
            if maxX * WORLD_SCALE > SAND_PIT_AT:
                gs.jump_landed = True
                print(f"✓ Landing detected at x={maxX * WORLD_SCALE:.1f}")
                
                # Update score
                gs.score = round(maxX) / 10
                if gs.score > gs.high_score:
                    gs.high_score = gs.score
                    print(f"✓ New high score: {gs.high_score:.1f}m")
    
    def _handle_fall_contact(self, maxX, contactY, body_part_body, track_body):
        """
        Handle upper body touching track (fall detection).
        
        Logic from QWOP_FUNCTIONS_EXACT.md lines 263-310:
        - Set fallen = True
        - Calculate impact velocity
        - Update score (finalize)
        - Mark as landed if jumped
        
        Args:
            maxX: Rightmost contact point X in world coordinates
            contactY: Contact point Y in world coordinates
            body_part_body: The body part that hit the ground
            track_body: The track body
        """
        gs = self.game_state
        
        # Skip if already fallen
        if gs.fallen:
            return
        
        gs.fallen = True
        print(f"✗ Player fell at x={maxX * WORLD_SCALE:.1f}")
        
        # Calculate impact velocity (for sound selection)
        velocityA = body_part_body.linearVelocity
        velocityB = track_body.linearVelocity
        relative_velocity = (velocityA[0] - velocityB[0], velocityA[1] - velocityB[1])
        gs.impact_speed = (relative_velocity[0]**2 + relative_velocity[1]**2)**0.5
        
        # Determine impact sound (for future audio implementation)
        if gs.impact_speed > IMPACT_SOUND_THRESHOLD:
            sound = "crunch"  # Hard impact
        else:
            sound = "ehh"  # Soft impact
        print(f"  Impact velocity: {gs.impact_speed:.2f} m/s (sound: {sound})")
        
        # If jumped but not landed, count as landing
        if gs.jumped and not gs.jump_landed:
            gs.jump_landed = True
        
        # Update score (finalize)
        gs.score = round(maxX) / 10
        if gs.score > gs.high_score:
            gs.high_score = gs.score
            print(f"  Final score: {gs.score:.1f}m (high: {gs.high_score:.1f}m)")
    
    def EndContact(self, contact):
        """
        Called when two fixtures stop touching.
        
        Original QWOP has no logic here (empty function).
        """
        pass
