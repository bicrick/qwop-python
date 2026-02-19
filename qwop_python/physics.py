"""
QWOP Physics System - Box2D World Implementation

Creates the complete physics simulation with:
- Box2D world with exact gravity
- Ground/track as static body
- 12 dynamic body parts with exact initial positions and properties
- 11 revolute joints with exact anchors, limits, and motor configurations

All values are 1:1 with the original QWOP game.
"""

from Box2D import (
    b2World, b2Vec2, b2BodyDef, b2FixtureDef, b2PolygonShape,
    b2_dynamicBody, b2_staticBody, b2RevoluteJointDef
)

from .data import (
    GRAVITY, WORLD_SCALE, PHYSICS_TIMESTEP,
    VELOCITY_ITERATIONS, POSITION_ITERATIONS,
    TRACK_Y, TRACK_HALF_HEIGHT, TRACK_FRICTION, TRACK_DENSITY,
    CATEGORY_GROUND, MASK_ALL,
    LEVEL_SIZE, SCREEN_WIDTH,
    BODY_PARTS, JOINTS,
    HURDLES_ENABLED,
    HURDLE_BASE_POS, HURDLE_BASE_SIZE,
    HURDLE_TOP_POS, HURDLE_TOP_SIZE,
    HURDLE_BASE_CATEGORY, HURDLE_BASE_MASK,
    HURDLE_TOP_CATEGORY, HURDLE_TOP_MASK,
    HURDLE_JOINT_ANCHOR_A, HURDLE_JOINT_ANCHOR_B
)


class PhysicsWorld:
    """
    Manages the Box2D physics world for QWOP game.
    
    Creates and maintains:
    - Physics world with gravity
    - Ground/track static body
    - 12 player body parts (dynamic bodies)
    - 11 revolute joints connecting body parts
    """
    
    def __init__(self, verbose=True):
        """Initialize physics world container.
        
        Args:
            verbose: If True, print initialization messages (default: True)
        """
        self.verbose = verbose
        self.world = None
        self.bodies = {}  # Dict of body name -> b2Body
        self.joints = {}  # Dict of joint name -> b2RevoluteJoint
        self.ground_body = None
        self.ground_segments = []  # List of all ground segment bodies
        self.hurdle_base = None  # Hurdle base body
        self.hurdle_top = None  # Hurdle top body
        self.hurdle_joint = None  # Revolute joint connecting hurdle parts
        
    def create_world(self):
        """
        Create Box2D world with exact gravity settings.
        
        Settings:
        - Gravity: (0, 10) m/s² downward
        - doSleep: True (allows bodies to sleep when at rest)
        """
        self.world = b2World(gravity=(0, GRAVITY), doSleep=True)
        if self.verbose:
            print(f"✓ Physics world created with gravity (0, {GRAVITY})")
        
    def create_ground(self):
        """
        Create static ground/track body.
        
        Properties:
        - Position: y = 10.74275 (TRACK_Y)
        - Type: b2_staticBody
        - Shape: Long horizontal box spanning entire level
        - friction = 0.2
        - restitution = 0 (no bounce)
        - density = 30 (doesn't affect static bodies)
        - categoryBits = 1 (CATEGORY_GROUND)
        - maskBits = 65535 (collides with everything)
        - userData = "track"
        
        Creates multiple segments for infinite scrolling support.
        """
        if self.world is None:
            raise RuntimeError("World must be created before ground")
        
        # Create 3 segments (matches JS: for (var h = 0; 3 > h;))
        num_segments = 3
        segment_width = SCREEN_WIDTH / WORLD_SCALE
        
        # Clear ground segments list
        self.ground_segments = []
        
        for i in range(num_segments):
            x_position = i * segment_width
            
            # Create static body definition
            bodyDef = b2BodyDef()
            bodyDef.type = b2_staticBody
            bodyDef.position = (x_position, TRACK_Y)
            bodyDef.angle = 0
            
            # Create body
            body = self.world.CreateBody(bodyDef)
            
            # Create box shape (matches JS: sprite.size from underground.png 640x64)
            shape = b2PolygonShape()
            shape.SetAsBox(segment_width / 2, TRACK_HALF_HEIGHT)
            
            # Create fixture with exact properties
            fixtureDef = b2FixtureDef()
            fixtureDef.shape = shape
            fixtureDef.friction = TRACK_FRICTION
            fixtureDef.restitution = 0  # CRITICAL: No bounce
            fixtureDef.density = TRACK_DENSITY
            fixtureDef.filter.categoryBits = CATEGORY_GROUND
            fixtureDef.filter.maskBits = MASK_ALL
            
            body.CreateFixture(fixtureDef)
            body.userData = "track"
            
            # Store in ground segments list
            self.ground_segments.append(body)
        
        # Store reference to first segment as ground_body (backward compatibility)
        self.ground_body = self.ground_segments[0]
        
        if self.verbose:
            print(f"✓ Ground created: {num_segments} segments at y={TRACK_Y}")
        
    def create_body_part(self, name, config):
        """
        Create a single body part with exact properties.
        
        Args:
            name: Body part name (e.g., "torso", "head", "leftFoot")
            config: Configuration dict from BODY_PARTS
            
        Returns:
            b2Body: The created Box2D body
            
        Body properties from config:
        - position: (x, y) in meters
        - angle: rotation in radians
        - half_width, half_height: box shape half-dimensions
        - friction: surface friction (0.2 for most, 1.5 for feet)
        - density: mass density (1.0 for most, 3.0 for feet)
        - category_bits: collision category (2 for all player parts)
        - mask_bits: collision mask (65533 - prevents self-collision)
        - user_data: identification string
        """
        if self.world is None:
            raise RuntimeError("World must be created before bodies")
        
        # Create dynamic body definition
        bodyDef = b2BodyDef()
        bodyDef.type = b2_dynamicBody
        bodyDef.position = config['position']
        bodyDef.angle = config['angle']
        
        # Create body
        body = self.world.CreateBody(bodyDef)
        
        # Create box shape with exact half-dimensions
        shape = b2PolygonShape()
        shape.SetAsBox(config['half_width'], config['half_height'])
        
        # Create fixture with exact properties
        fixtureDef = b2FixtureDef()
        fixtureDef.shape = shape
        fixtureDef.density = config['density']
        fixtureDef.friction = config['friction']
        fixtureDef.restitution = 0  # CRITICAL: No bounce - all bodies must have this
        fixtureDef.filter.categoryBits = config['category_bits']
        fixtureDef.filter.maskBits = config['mask_bits']
        
        body.CreateFixture(fixtureDef)
        body.userData = config['user_data']
        
        # Store body reference
        self.bodies[name] = body
        
        return body
        
    def create_bodies(self):
        """
        Create all 12 player body parts in correct order.
        
        Order matters for proper hierarchy:
        1. torso (center mass)
        2. head
        3. arms (leftArm, rightArm)
        4. forearms (leftForearm, rightForearm)
        5. thighs (leftThigh, rightThigh)
        6. calves (leftCalf, rightCalf)
        7. feet (leftFoot, rightFoot)
        
        Special properties:
        - Feet: friction=1.5, density=3.0 (3x heavier for stability)
        - All others: friction=0.2, density=1.0
        - All: restitution=0, categoryBits=2, maskBits=65533
        """
        if self.world is None:
            raise RuntimeError("World must be created before bodies")
        
        # Create bodies in order
        body_order = [
            'torso', 'head',
            'leftArm', 'rightArm',
            'leftForearm', 'rightForearm',
            'leftThigh', 'rightThigh',
            'leftCalf', 'rightCalf',
            'leftFoot', 'rightFoot'
        ]
        
        for name in body_order:
            config = BODY_PARTS[name]
            body = self.create_body_part(name, config)
            
            # Verify special properties for feet
            if 'Foot' in name:
                assert config['friction'] == 1.5, f"{name} friction must be 1.5"
                assert config['density'] == 3.0, f"{name} density must be 3.0"
        
        if self.verbose:
            print(f"✓ Created {len(self.bodies)} body parts")
        
    def create_joint(self, name, config):
        """
        Create a single revolute joint with exact properties.
        
        Args:
            name: Joint name (e.g., "neck", "leftHip", "rightKnee")
            config: Configuration dict from JOINTS
            
        Returns:
            b2RevoluteJoint: The created Box2D joint
            
        Joint properties from config:
        - body_a, body_b: names of bodies to connect
        - anchor_a: world anchor point (used for initialization)
        - lower_angle, upper_angle: joint angle limits in radians
        - reference_angle: zero-rotation angle (CRITICAL for motors)
        - enable_motor: whether motor is active
        - max_motor_torque: maximum torque motor can apply
        - motor_speed: initial speed (always 0)
        
        CRITICAL:
        - ALL joints must have enableLimit = True
        - Reference angle is essential for correct motor behavior
        - Initial motor speeds must be 0
        """
        if self.world is None:
            raise RuntimeError("World must be created before joints")
        
        # Get body references
        bodyA = self.bodies[config['body_a']]
        bodyB = self.bodies[config['body_b']]
        
        # Create revolute joint definition
        # Match JS exactly: use per-body world anchors (anchor_a for bodyA, anchor_b for bodyB)
        # JS: localAnchorA = bodyA.getLocalPoint(anchor_a), localAnchorB = bodyB.getLocalPoint(anchor_b)
        jointDef = b2RevoluteJointDef()
        jointDef.bodyA = bodyA
        jointDef.bodyB = bodyB
        anchor_a = b2Vec2(config['anchor_a'][0], config['anchor_a'][1])
        anchor_b = b2Vec2(config['anchor_b'][0], config['anchor_b'][1])
        jointDef.localAnchorA = bodyA.GetLocalPoint(anchor_a)
        jointDef.localAnchorB = bodyB.GetLocalPoint(anchor_b)
        
        # Set reference angle (CRITICAL for motor behavior)
        jointDef.referenceAngle = config['reference_angle']
        
        # Enable limits (ALL joints have limits)
        jointDef.enableLimit = True
        jointDef.lowerAngle = config['lower_angle']
        jointDef.upperAngle = config['upper_angle']
        
        # Set motor configuration
        jointDef.enableMotor = config['enable_motor']
        jointDef.maxMotorTorque = config['max_motor_torque']
        jointDef.motorSpeed = 0  # All motors start at zero speed
        
        # Create joint
        joint = self.world.CreateJoint(jointDef)
        
        # Store joint reference
        self.joints[name] = joint
        
        return joint
        
    def create_joints(self):
        """
        Create all 11 revolute joints in correct order.
        
        Joint hierarchy (parent ↔ child):
        1. neck: head ↔ torso (passive)
        2. rightShoulder: rightArm ↔ torso (motor: 1000 torque)
        3. leftShoulder: leftArm ↔ torso (motor: 1000 torque)
        4. rightElbow: rightForearm ↔ rightArm (passive)
        5. leftElbow: leftForearm ↔ leftArm (passive)
        6. rightHip: rightThigh ↔ torso (motor: 6000 torque, MAIN CONTROL)
        7. leftHip: leftThigh ↔ torso (motor: 6000 torque, MAIN CONTROL)
        8. rightKnee: rightCalf ↔ rightThigh (motor: 3000 torque, MAIN CONTROL)
        9. leftKnee: leftCalf ↔ leftThigh (motor: 3000 torque, MAIN CONTROL)
        10. rightAnkle: rightFoot ↔ rightCalf (passive)
        11. leftAnkle: leftFoot ↔ leftCalf (passive)
        
        Motor-enabled joints: hips, knees, shoulders
        Passive joints: neck, elbows, ankles
        """
        if len(self.bodies) != 12:
            raise RuntimeError("All bodies must be created before joints")
        
        # Create joints in order
        joint_order = [
            'neck',
            'rightShoulder', 'leftShoulder',
            'rightElbow', 'leftElbow',
            'rightHip', 'leftHip',
            'rightKnee', 'leftKnee',
            'rightAnkle', 'leftAnkle'
        ]
        
        for name in joint_order:
            config = JOINTS[name]
            joint = self.create_joint(name, config)
            
            # Verify motor configuration
            if config['enable_motor']:
                assert joint.motorSpeed == 0, f"{name} must start with motorSpeed=0"
        
        if self.verbose:
            print(f"✓ Created {len(self.joints)} joints")
    
    def create_hurdle(self):
        """
        Create hurdle obstacle with exact properties from QWOP.js.
        
        The hurdle consists of two dynamic bodies connected by a revolute joint:
        - Hurdle Base: Horizontal bar at the bottom (67x12 pixels)
        - Hurdle Top: Vertical bar that rotates (21.5x146 pixels)
        
        Both bodies start asleep and wake up when hit by the player.
        The joint allows the top bar to rotate around the connection point.
        
        Properties match QWOP.js lines 998-1032 exactly.
        """
        if self.world is None:
            raise RuntimeError("World must be created before hurdle")
        
        # === HURDLE BASE ===
        # Convert pixel position to world coordinates
        base_x = HURDLE_BASE_POS[0] / WORLD_SCALE  # 10000 / 20 = 500
        base_y = HURDLE_BASE_POS[1] / WORLD_SCALE  # 175.5 / 20 = 8.775
        
        # Convert pixel size to world dimensions (half-width, half-height)
        base_half_width = HURDLE_BASE_SIZE[0] / (2 * WORLD_SCALE)  # 67 / 40 = 1.675
        base_half_height = HURDLE_BASE_SIZE[1] / (2 * WORLD_SCALE)  # 12 / 40 = 0.3
        
        # Create base body definition
        base_def = b2BodyDef()
        base_def.type = b2_dynamicBody
        base_def.position = (base_x, base_y)
        base_def.angle = 0
        base_def.awake = False  # Start asleep until collision
        
        # Create base body
        self.hurdle_base = self.world.CreateBody(base_def)
        
        # Create base shape
        base_shape = b2PolygonShape()
        base_shape.SetAsBox(base_half_width, base_half_height)
        
        # Create base fixture
        base_fixture = b2FixtureDef()
        base_fixture.shape = base_shape
        base_fixture.density = 1.0
        base_fixture.friction = 0.2
        base_fixture.restitution = 0.0  # CRITICAL: No bounce
        base_fixture.filter.categoryBits = HURDLE_BASE_CATEGORY
        base_fixture.filter.maskBits = HURDLE_BASE_MASK
        
        self.hurdle_base.CreateFixture(base_fixture)
        self.hurdle_base.userData = "hurdleBase"
        
        # === HURDLE TOP ===
        # Convert pixel position to world coordinates
        top_x = HURDLE_TOP_POS[0] / WORLD_SCALE  # 10017.3 / 20 = 500.865
        top_y = HURDLE_TOP_POS[1] / WORLD_SCALE  # 101.15 / 20 = 5.0575
        
        # Convert pixel size to world dimensions (half-width, half-height)
        top_half_width = HURDLE_TOP_SIZE[0] / (2 * WORLD_SCALE)  # 21.5 / 40 = 0.5375
        top_half_height = HURDLE_TOP_SIZE[1] / (2 * WORLD_SCALE)  # 146 / 40 = 3.65
        
        # Create top body definition
        top_def = b2BodyDef()
        top_def.type = b2_dynamicBody
        top_def.position = (top_x, top_y)
        top_def.angle = 0
        top_def.awake = False  # Start asleep until collision
        
        # Create top body
        self.hurdle_top = self.world.CreateBody(top_def)
        
        # Create top shape
        top_shape = b2PolygonShape()
        top_shape.SetAsBox(top_half_width, top_half_height)
        
        # Create top fixture
        top_fixture = b2FixtureDef()
        top_fixture.shape = top_shape
        top_fixture.density = 1.0
        top_fixture.friction = 0.2
        top_fixture.restitution = 0.0  # CRITICAL: No bounce
        top_fixture.filter.categoryBits = HURDLE_TOP_CATEGORY
        top_fixture.filter.maskBits = HURDLE_TOP_MASK
        
        self.hurdle_top.CreateFixture(top_fixture)
        self.hurdle_top.userData = "hurdleTop"
        
        # === REVOLUTE JOINT ===
        # Connect top to base with a hinge joint
        joint_def = b2RevoluteJointDef()
        joint_def.bodyA = self.hurdle_top
        joint_def.bodyB = self.hurdle_base
        
        # Set local anchors (relative to each body's center)
        joint_def.localAnchorA = b2Vec2(HURDLE_JOINT_ANCHOR_A[0], HURDLE_JOINT_ANCHOR_A[1])
        joint_def.localAnchorB = b2Vec2(HURDLE_JOINT_ANCHOR_B[0], HURDLE_JOINT_ANCHOR_B[1])
        
        # Enable limits but no specific angle constraints (free rotation)
        joint_def.enableLimit = True
        joint_def.lowerAngle = -3.14159  # -180 degrees (full rotation)
        joint_def.upperAngle = 3.14159   # +180 degrees (full rotation)
        
        # No motor
        joint_def.enableMotor = False
        
        # Create joint
        self.hurdle_joint = self.world.CreateJoint(joint_def)
        
        if self.verbose:
            print(f"✓ Hurdle created at x={base_x}m")
            print(f"  Base: {HURDLE_BASE_SIZE[0]}x{HURDLE_BASE_SIZE[1]}px at ({base_x:.3f}, {base_y:.3f})m")
            print(f"  Top: {HURDLE_TOP_SIZE[0]}x{HURDLE_TOP_SIZE[1]}px at ({top_x:.3f}, {top_y:.3f})m")
        
    def get_body(self, name):
        """
        Get body by name.
        
        Args:
            name: Body part name
            
        Returns:
            b2Body or None
        """
        return self.bodies.get(name)
        
    def get_joint(self, name):
        """
        Get joint by name.
        
        Args:
            name: Joint name
            
        Returns:
            b2RevoluteJoint or None
        """
        return self.joints.get(name)
    
    def set_contact_listener(self, listener):
        """
        Attach a contact listener to the physics world.
        
        Args:
            listener: b2ContactListener subclass instance (e.g., QWOPContactListener)
            
        The listener's BeginContact and EndContact methods will be called
        automatically by Box2D when collisions occur.
        """
        if self.world is None:
            raise RuntimeError("World must be created before setting contact listener")
        
        self.world.contactListener = listener
        if self.verbose:
            print(f"✓ Contact listener attached: {listener.__class__.__name__}")
        
    def step(self, dt=None):
        """
        Advance physics simulation by one timestep.
        
        Args:
            dt: Timestep in seconds (defaults to PHYSICS_TIMESTEP = 0.04)
            
        Uses fixed timestep of 0.04s (25 FPS physics) for deterministic simulation.
        """
        if self.world is None:
            raise RuntimeError("World must be created before stepping")
        
        if dt is None:
            dt = PHYSICS_TIMESTEP
        
        self.world.Step(dt, VELOCITY_ITERATIONS, POSITION_ITERATIONS)
        
    def initialize(self):
        """
        Initialize complete physics world.
        
        Creates:
        1. Box2D world with gravity
        2. Ground/track static body
        3. Hurdle obstacle (if HURDLES_ENABLED)
        4. All 12 body parts
        5. All 11 joints
        
        Call this once at startup.
        """
        if self.verbose:
            print("Initializing QWOP physics world...")
        self.create_world()
        self.create_ground()
        if HURDLES_ENABLED:
            self.create_hurdle()
        self.create_bodies()
        self.create_joints()
        if self.verbose:
            print("✓ Physics world initialization complete")
            print(f"  Bodies: {len(self.bodies)}")
            print(f"  Joints: {len(self.joints)}")
            if HURDLES_ENABLED:
                print(f"  Hurdles: Enabled")
    
    def reset(self):
        """
        Reset the player (destroy and recreate all body parts and joints).
        
        This is called when the user presses 'R' to restart the game.
        Ground segments and hurdle are NOT destroyed - only player body parts and joints.
        Hurdle is destroyed and recreated to reset its position and state.
        
        Steps:
        1. Destroy all player joints
        2. Destroy all body part bodies (not ground or hurdle)
        3. Destroy and recreate hurdle
        4. Clear bodies and joints dicts
        5. Recreate bodies and joints
        """
        if self.world is None:
            raise RuntimeError("World must be initialized before reset")
        
        if self.verbose:
            print("Resetting player...")
        
        # 1. Destroy all player joints
        for joint in list(self.joints.values()):
            self.world.DestroyJoint(joint)
        
        # 2. Destroy all body part bodies (not ground segments or hurdle)
        for body in list(self.bodies.values()):
            self.world.DestroyBody(body)
        
        # 3. Destroy and recreate hurdle (if enabled)
        if HURDLES_ENABLED:
            if self.hurdle_joint is not None:
                self.world.DestroyJoint(self.hurdle_joint)
                self.hurdle_joint = None
            
            if self.hurdle_base is not None:
                self.world.DestroyBody(self.hurdle_base)
                self.hurdle_base = None
            
            if self.hurdle_top is not None:
                self.world.DestroyBody(self.hurdle_top)
                self.hurdle_top = None
            
            # Recreate hurdle
            self.create_hurdle()
        
        # 4. Clear dictionaries
        self.bodies.clear()
        self.joints.clear()
        
        # 5. Recreate player bodies and joints
        self.create_bodies()
        self.create_joints()
        
        if self.verbose:
            print("✓ Player reset complete")
            print(f"  Bodies: {len(self.bodies)}")
            print(f"  Joints: {len(self.joints)}")
