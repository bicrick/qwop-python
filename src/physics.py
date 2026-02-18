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

from data import (
    GRAVITY, WORLD_SCALE, PHYSICS_TIMESTEP,
    VELOCITY_ITERATIONS, POSITION_ITERATIONS,
    TRACK_Y, TRACK_FRICTION, TRACK_DENSITY,
    CATEGORY_GROUND, MASK_ALL,
    LEVEL_SIZE, SCREEN_WIDTH,
    BODY_PARTS, JOINTS,
    HURDLE_ENABLED,
    HURDLE_BASE_POS, HURDLE_BASE_SIZE,
    HURDLE_TOP_POS, HURDLE_TOP_SIZE,
    HURDLE_BASE_CATEGORY, HURDLE_BASE_MASK,
    HURDLE_TOP_CATEGORY, HURDLE_TOP_MASK,
    DENSITY_FACTOR
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
    
    def __init__(self):
        """Initialize physics world container."""
        self.world = None
        self.bodies = {}  # Dict of body name -> b2Body
        self.joints = {}  # Dict of joint name -> b2RevoluteJoint
        self.ground_body = None
        self.ground_segments = []  # List of all ground segment bodies
        # Hurdle (optional, controlled by HURDLE_ENABLED)
        self.hurdle_base = None
        self.hurdle_top = None
        self.hurdle_joint = None
        
    def create_world(self):
        """
        Create Box2D world with exact gravity settings.
        
        Settings:
        - Gravity: (0, 10) m/s² downward
        - doSleep: True (allows bodies to sleep when at rest)
        """
        self.world = b2World(gravity=(0, GRAVITY), doSleep=True)
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
        
        # Create 4 segments to cover initial view plus extra
        num_segments = 4
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
            
            # Create box shape (very wide and thin)
            shape = b2PolygonShape()
            shape.SetAsBox(segment_width / 2, 0.1)  # Half-width, half-height
            
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
        
        print(f"✓ Ground created: {num_segments} segments at y={TRACK_Y}")
        
    def create_hurdle(self):
        """
        Create hurdle obstacle at x=10000 pixels (500 meters).
        
        Two-part hurdle: base (static) on ground + top (dynamic) connected by
        revolute joint. Top rotates when player hits it. Only created when
        HURDLE_ENABLED is True.
        """
        if not HURDLE_ENABLED or self.world is None:
            return
        
        # Convert pixel positions/sizes to Box2D world units (meters)
        base_x = HURDLE_BASE_POS[0] / WORLD_SCALE
        base_y = HURDLE_BASE_POS[1] / WORLD_SCALE
        base_hw = HURDLE_BASE_SIZE[0] / (2 * WORLD_SCALE)
        base_hh = HURDLE_BASE_SIZE[1] / (2 * WORLD_SCALE)
        
        top_x = HURDLE_TOP_POS[0] / WORLD_SCALE
        top_y = HURDLE_TOP_POS[1] / WORLD_SCALE
        top_hw = HURDLE_TOP_SIZE[0] / (2 * WORLD_SCALE)
        top_hh = HURDLE_TOP_SIZE[1] / (2 * WORLD_SCALE)
        
        # Hurdle base - static body (fixed support)
        base_def = b2BodyDef()
        base_def.type = b2_staticBody
        base_def.position = (base_x, base_y)
        base_def.angle = 0
        self.hurdle_base = self.world.CreateBody(base_def)
        
        base_shape = b2PolygonShape()
        base_shape.SetAsBox(base_hw, base_hh)
        base_fixture = b2FixtureDef()
        base_fixture.shape = base_shape
        base_fixture.friction = TRACK_FRICTION
        base_fixture.restitution = 0
        base_fixture.density = DENSITY_FACTOR
        base_fixture.filter.categoryBits = HURDLE_BASE_CATEGORY
        base_fixture.filter.maskBits = HURDLE_BASE_MASK
        self.hurdle_base.CreateFixture(base_fixture)
        self.hurdle_base.userData = "hurdleBase"
        
        # Hurdle top - dynamic body (rotates when hit)
        top_def = b2BodyDef()
        top_def.type = b2_dynamicBody
        top_def.position = (top_x, top_y)
        top_def.angle = 0
        top_def.awake = False
        self.hurdle_top = self.world.CreateBody(top_def)
        
        top_shape = b2PolygonShape()
        top_shape.SetAsBox(top_hw, top_hh)
        top_fixture = b2FixtureDef()
        top_fixture.shape = top_shape
        top_fixture.friction = TRACK_FRICTION
        top_fixture.restitution = 0
        top_fixture.density = DENSITY_FACTOR
        top_fixture.filter.categoryBits = HURDLE_TOP_CATEGORY
        top_fixture.filter.maskBits = HURDLE_TOP_MASK
        self.hurdle_top.CreateFixture(top_fixture)
        self.hurdle_top.userData = "hurdleTop"
        
        # Revolute joint: top pivots on base (local anchors from docs)
        joint_def = b2RevoluteJointDef()
        local_a = b2Vec2(3.6 / WORLD_SCALE, 74.6 / WORLD_SCALE)
        world_anchor = self.hurdle_top.GetWorldPoint(local_a)
        joint_def.Initialize(self.hurdle_top, self.hurdle_base, world_anchor)
        joint_def.enableLimit = True
        joint_def.lowerAngle = -3.14159 * 2  # Free rotation
        joint_def.upperAngle = 3.14159 * 2
        self.hurdle_joint = self.world.CreateJoint(joint_def)
        
        print(f"✓ Hurdle created at x={base_x * WORLD_SCALE:.0f}px")
        
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
        jointDef = b2RevoluteJointDef()
        
        # Initialize with bodies and world anchor point
        # Use anchor_a as the world anchor (both anchors are nearly identical)
        world_anchor = b2Vec2(config['anchor_a'][0], config['anchor_a'][1])
        jointDef.Initialize(bodyA, bodyB, world_anchor)
        
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
        
        print(f"✓ Created {len(self.joints)} joints")
        
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
        3. All 12 body parts
        4. All 11 joints
        
        Call this once at startup.
        """
        print("Initializing QWOP physics world...")
        self.create_world()
        self.create_ground()
        self.create_hurdle()
        self.create_bodies()
        self.create_joints()
        print("✓ Physics world initialization complete")
        print(f"  Bodies: {len(self.bodies)}")
        print(f"  Joints: {len(self.joints)}")
    
    def reset(self):
        """
        Reset the player (destroy and recreate all body parts and joints).
        
        This is called when the user presses 'R' to restart the game.
        Ground segments are NOT destroyed - only player body parts and joints.
        
        Steps:
        1. Destroy all joints
        2. Destroy all body part bodies (not ground)
        3. Clear bodies and joints dicts
        4. Recreate bodies and joints
        """
        if self.world is None:
            raise RuntimeError("World must be initialized before reset")
        
        print("Resetting player...")
        
        # 0. Destroy hurdle if present (recreated below when HURDLE_ENABLED)
        if self.hurdle_joint is not None:
            self.world.DestroyJoint(self.hurdle_joint)
            self.hurdle_joint = None
        if self.hurdle_top is not None:
            self.world.DestroyBody(self.hurdle_top)
            self.hurdle_top = None
        if self.hurdle_base is not None:
            self.world.DestroyBody(self.hurdle_base)
            self.hurdle_base = None
        
        # 1. Destroy all joints
        for joint in list(self.joints.values()):
            self.world.DestroyJoint(joint)
        
        # 2. Destroy all body part bodies (not ground segments)
        for body in list(self.bodies.values()):
            self.world.DestroyBody(body)
        
        # 3. Clear dictionaries
        self.bodies.clear()
        self.joints.clear()
        
        # 4. Recreate player bodies and joints
        self.create_bodies()
        self.create_joints()
        
        # 5. Recreate hurdle if enabled
        self.create_hurdle()
        
        print("✓ Player reset complete")
        print(f"  Bodies: {len(self.bodies)}")
        print(f"  Joints: {len(self.joints)}")
