"""
QWOP Game Data - Complete Constants and Configurations
All values extracted from reverse-engineered QWOP.js documentation in /docs
"""

# =============================================================================
# WORLD CONSTANTS
# Source: doc/reference/QWOP_CONSTANTS.md, doc/reference/QWOP_COMPLETE_DATA_REFERENCE.md
# =============================================================================

WORLD_SCALE = 20  # Pixels per meter conversion
GRAVITY = 10  # m/s² downward
TORQUE_FACTOR = 1  # Joint torque multiplier
DENSITY_FACTOR = 1  # Body density multiplier

# Level layout
LEVEL_SIZE = 21000  # Total track length in pixels
SAND_PIT_AT = 20000  # Jump landing zone location (pixels)
HURDLE_AT = 10000  # Hurdle obstacle location (pixels)

# Screen dimensions
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 400
OBS_PANEL_WIDTH = 400

# Physics simulation parameters
PHYSICS_TIMESTEP = 0.04  # Fixed timestep - 25 FPS physics (1/25)
VELOCITY_ITERATIONS = 5  # Box2D velocity constraint solver iterations
POSITION_ITERATIONS = 5  # Box2D position constraint solver iterations

# =============================================================================
# COLLISION CATEGORIES
# Source: doc/reference/QWOP_COLLISION_SYSTEM.md
# =============================================================================

CATEGORY_GROUND = 0x0001  # 1 - Track/floor
CATEGORY_PLAYER = 0x0002  # 2 - All player body parts
CATEGORY_HURDLE = 0x0004  # 4 - Hurdle obstacle

MASK_ALL = 0xFFFF  # 65535 - Collides with everything
MASK_NO_SELF = 0xFFFD  # 65533 - Everything except category 2 (prevents self-collision)

# =============================================================================
# BODY PART CONFIGURATIONS
# Source: doc/reference/QWOP_BODY_EXACT_DATA.md, doc/reference/QWOP_SPRITE_DIMENSIONS_EXACT.md
# All positions and angles use 16-decimal precision from original game
# =============================================================================

BODY_PARTS = {
    'torso': {
        'position': (2.5111726226000157, -1.8709517533957938),
        'angle': -1.2514497119301329,  # -71.70°
        'half_width': 3.275,  # 131px / 40
        'half_height': 1.425,  # 57px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 6,
        'user_data': 'torso'
    },
    'head': {
        'position': (3.888130278719558, -5.621802929095265),
        'angle': 0.06448415835225099,  # 3.69°
        'half_width': 1.075,  # 43px / 40
        'half_height': 1.325,  # 53px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 7,
        'user_data': 'head'
    },
    'leftArm': {
        'position': (4.417861014480877, -2.806563606410589),
        'angle': 0.9040095895272826,  # 51.80°
        'half_width': 1.85,  # 74px / 40
        'half_height': 0.625,  # 25px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 4,
        'user_data': 'leftArm'
    },
    'leftForearm': {
        'position': (5.830008603424893, -2.8733539631159584),
        'angle': -1.2049772618421237,  # -69.04°
        'half_width': 1.75,  # 70px / 40
        'half_height': 0.55,  # 22px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 5,
        'user_data': 'leftForearm'
    },
    'leftThigh': {
        'position': (2.5648987628203876, 1.648090668682522),
        'angle': -2.0177234426823394,  # -115.59°
        'half_width': 2.525,  # 101px / 40
        'half_height': 1.0,  # 40px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 3,
        'user_data': 'leftThigh'
    },
    'leftCalf': {
        'position': (3.12585731974087, 5.525511655361298),
        'angle': -1.5903971528225265,  # -91.11°
        'half_width': 2.5,  # 100px / 40
        'half_height': 0.75,  # 30px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 1,
        'user_data': 'leftCalf'
    },
    'leftFoot': {
        'position': (3.926921842806667, 8.08884032049622),
        'angle': 0.12027524643408766,  # 6.89°
        'half_width': 1.35,  # 54px / 40
        'half_height': 0.675,  # 27px / 40
        'friction': 1.5,  # Higher friction for ground grip
        'density': 3.0,  # 3x heavier for stability
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 2,
        'user_data': 'leftFoot'
    },
    'rightArm': {
        'position': (1.1812303663272852, -3.5000256518601014),
        'angle': -0.5222217404634386,  # -29.92°
        'half_width': 1.95,  # 78px / 40
        'half_height': 0.75,  # 30px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 8,
        'user_data': 'rightArm'
    },
    'rightForearm': {
        'position': (0.4078206420797428, -1.0599953233084172),
        'angle': -1.7553358283857299,  # -100.57°
        'half_width': 2.225,  # 89px / 40
        'half_height': 0.675,  # 27px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 12,
        'user_data': 'rightForearm'
    },
    'rightThigh': {
        'position': (1.6120186135678773, 2.0615320561881516),
        'angle': 1.4849422964528027,  # 85.08°
        'half_width': 2.65,  # 106px / 40
        'half_height': 1.0,  # 40px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 10,
        'user_data': 'rightThigh'
    },
    'rightCalf': {
        'position': (-0.07253905736790486, 5.347881871063159),
        'angle': -0.7588859967104447,  # -43.48°
        'half_width': 2.5,  # 100px / 40
        'half_height': 0.75,  # 30px / 40
        'friction': 0.2,
        'density': 1.0,
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 9,
        'user_data': 'rightCalf'
    },
    'rightFoot': {
        'position': (-1.1254742643908706, 7.567193169625567),
        'angle': 0.5897605418219602,  # 33.79°
        'half_width': 1.35,  # 54px / 40
        'half_height': 0.725,  # 29px / 40
        'friction': 1.5,  # Higher friction for ground grip
        'density': 3.0,  # 3x heavier for stability
        'category_bits': CATEGORY_PLAYER,
        'mask_bits': MASK_NO_SELF,
        'depth': 11,
        'user_data': 'rightFoot'
    }
}

# =============================================================================
# JOINT CONFIGURATIONS
# Source: doc/reference/QWOP_JOINTS_EXACT_DATA.md
# All anchor points in world coordinates with 16-decimal precision
# =============================================================================

JOINTS = {
    'neck': {
        'body_a': 'head',
        'body_b': 'torso',
        'anchor_a': (3.5885141908253755, -4.526224223627244),
        'anchor_b': (3.588733341630704, -4.526434658500262),
        'lower_angle': -0.5,
        'upper_angle': 0.0,
        'reference_angle': -1.308996406363529,
        'enable_motor': False,
        'max_motor_torque': 0,
        'motor_speed': 0
    },
    'rightShoulder': {
        'body_a': 'rightArm',
        'body_b': 'torso',
        'anchor_a': (2.228476821818547, -4.086468732185028),
        'anchor_b': (2.228929993886102, -4.08707555939957),
        'lower_angle': -0.5,
        'upper_angle': 1.5,
        'reference_angle': -0.7853907065463961,
        'enable_motor': True,
        'max_motor_torque': 1000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'leftShoulder': {
        'body_a': 'leftArm',
        'body_b': 'torso',
        'anchor_a': (3.6241979856895377, -3.5334881618011442),
        'anchor_b': (3.6241778782207157, -3.533950434531982),
        'lower_angle': -2.0,
        'upper_angle': 0.0,
        'reference_angle': -2.09438311816829,
        'enable_motor': True,
        'max_motor_torque': 1000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'leftHip': {
        'body_a': 'leftThigh',
        'body_b': 'torso',
        'anchor_a': (2.0030339754142847, 0.23737160622781284),
        'anchor_b': (2.003367181376716, 0.23802590387419476),
        'lower_angle': -1.5,  # Dynamic - changes with O/P keys
        'upper_angle': 0.5,  # Dynamic - changes with O/P keys
        'reference_angle': 0.7258477508944043,
        'enable_motor': True,
        'max_motor_torque': 6000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'rightHip': {
        'body_a': 'rightThigh',
        'body_b': 'torso',
        'anchor_a': (1.2475900729227194, -0.011046642863645761),
        'anchor_b': (1.2470052823973599, -0.011635347168778898),
        'lower_angle': -1.3,  # Dynamic - changes with O/P keys
        'upper_angle': 0.7,  # Dynamic - changes with O/P keys
        'reference_angle': -2.719359381718199,
        'enable_motor': True,
        'max_motor_torque': 6000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'leftElbow': {
        'body_a': 'leftForearm',
        'body_b': 'leftArm',
        'anchor_a': (5.525375332758792, -1.63856204930891),
        'anchor_b': (5.52537532948459, -1.6385620366077662),
        'lower_angle': -0.1,
        'upper_angle': 0.5,
        'reference_angle': 2.09438311816829,
        'enable_motor': False,
        'max_motor_torque': 0,
        'motor_speed': 0
    },
    'rightElbow': {
        'body_a': 'rightForearm',
        'body_b': 'rightArm',
        'anchor_a': (-0.006090859076100963, -2.8004758838752157),
        'anchor_b': (-0.0060908611708438976, -2.8004758929205846),
        'lower_angle': -0.1,
        'upper_angle': 0.5,
        'reference_angle': 1.2968199012274688,
        'enable_motor': False,
        'max_motor_torque': 0,
        'motor_speed': 0
    },
    'leftKnee': {
        'body_a': 'leftCalf',
        'body_b': 'leftThigh',
        'anchor_a': (3.384323411985692, 3.5168931240916876),
        'anchor_b': (3.3844684376952108, 3.5174122997898016),
        'lower_angle': -1.6,
        'upper_angle': 0.0,
        'reference_angle': -0.3953113764119829,
        'enable_motor': True,
        'max_motor_torque': 3000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'rightKnee': {
        'body_a': 'rightCalf',
        'body_b': 'rightThigh',
        'anchor_a': (1.4982369235492752, 4.175600306005656),
        'anchor_b': (1.4982043532615996, 4.17493520671361),
        'lower_angle': -1.3,
        'upper_angle': 0.3,
        'reference_angle': 2.2893406247158676,
        'enable_motor': True,
        'max_motor_torque': 3000 * TORQUE_FACTOR,
        'motor_speed': 0
    },
    'leftAnkle': {
        'body_a': 'leftFoot',
        'body_b': 'leftCalf',
        'anchor_a': (3.312322507818897, 7.947704853895541),
        'anchor_b': (3.3123224825088817, 7.947704836256229),
        'lower_angle': -0.5,
        'upper_angle': 0.5,
        'reference_angle': -1.7244327585010226,
        'enable_motor': False,
        'max_motor_torque': 2000 * TORQUE_FACTOR,  # Unused, motor disabled
        'motor_speed': 0
    },
    'rightAnkle': {
        'body_a': 'rightFoot',
        'body_b': 'rightCalf',
        'anchor_a': (-1.6562855402197227, 6.961551452557676),
        'anchor_b': (-1.655726670462596, 6.961493826969391),
        'lower_angle': -0.5,
        'upper_angle': 0.5,
        'reference_angle': -1.5708045825942758,
        'enable_motor': False,
        'max_motor_torque': 2000 * TORQUE_FACTOR,  # Unused, motor disabled
        'motor_speed': 0
    }
}

# =============================================================================
# CONTROL MAPPINGS
# Source: doc/reference/QWOP_CONTROLS.md, doc/reference/QWOP_FUNCTIONS_EXACT.md
# Motor speeds and hip limit adjustments for each key
# =============================================================================

CONTROL_Q = {
    'motor_speeds': {
        'rightHip': 2.5,
        'leftHip': -2.5,
        'rightShoulder': -2.0,
        'leftShoulder': 2.0,
        'rightElbow': -10.0,  # Elbow motors disabled, these are no-ops
        'leftElbow': -10.0
    }
}

CONTROL_W = {
    'motor_speeds': {
        'rightHip': -2.5,
        'leftHip': 2.5,
        'rightShoulder': 2.0,
        'leftShoulder': -2.0,
        'rightElbow': 10.0,  # Elbow motors disabled, these are no-ops
        'leftElbow': 10.0
    }
}

CONTROL_O = {
    'motor_speeds': {
        'rightKnee': 2.5,
        'leftKnee': -2.5
    },
    'hip_limits': {
        'leftHip': (-1.0, 1.0),
        'rightHip': (-1.3, 0.7)
    }
}

CONTROL_P = {
    'motor_speeds': {
        'rightKnee': -2.5,
        'leftKnee': 2.5
    },
    'hip_limits': {
        'leftHip': (-1.5, 0.5),
        'rightHip': (-0.8, 1.2)
    }
}

# =============================================================================
# TRACK/GROUND CONFIGURATION
# Source: doc/reference/QWOP_COMPLETE_DATA_REFERENCE.md
# =============================================================================

TRACK_Y = 10.74275  # Y position in Box2D world units
# Half-height from underground.png (64px): 64 / (2 * WORLD_SCALE) = 1.6m (matches JS Box component)
TRACK_HALF_HEIGHT = 64 / (2 * WORLD_SCALE)
TRACK_FRICTION = 0.2
TRACK_DENSITY = 30  # Very heavy (static body)

# =============================================================================
# HURDLE CONFIGURATION
# Source: doc/reference/QWOP_COMPLETE_DATA_REFERENCE.md
# =============================================================================

HURDLES_ENABLED = False  # Set to True to enable hurdle obstacle

HURDLE_BASE_POS = (10000, 175.5)  # (x, y) in pixels
HURDLE_BASE_SIZE = (67, 12)  # (width, height) in pixels
HURDLE_TOP_POS = (10017.3, 101.15)  # (x, y) in pixels
HURDLE_TOP_SIZE = (21.5, 146)  # (width, height) in pixels

HURDLE_BASE_CATEGORY = CATEGORY_HURDLE
HURDLE_BASE_MASK = 0xFFF9  # 65529 - collides with ground only
HURDLE_TOP_CATEGORY = CATEGORY_HURDLE
HURDLE_TOP_MASK = 0xFFFB  # 65531 - collides with ground and player

# Hurdle joint anchors (from QWOP.js line 1028)
HURDLE_JOINT_ANCHOR_A = (3.6 / WORLD_SCALE, 74.6 / WORLD_SCALE)  # (0.18, 3.73) - top anchor
HURDLE_JOINT_ANCHOR_B = (20.9 / WORLD_SCALE, 0.25 / WORLD_SCALE)  # (1.045, 0.0125) - base anchor

# =============================================================================
# GAMEPLAY CONSTANTS
# Source: doc/reference/QWOP_FUNCTIONS_EXACT.md, doc/reference/QWOP_COMPLETE_DATA_REFERENCE.md
# =============================================================================

# Head stabilization (critical for balance)
HEAD_TORQUE_FACTOR = -4
HEAD_TORQUE_OFFSET = 0.2

# Jump detection
JUMP_TRIGGER_OFFSET = 220  # Pixels before sand pit (sandPitAt - 220)

# Collision detection
IMPACT_SOUND_THRESHOLD = 5  # Velocity threshold for "crunch" vs "ehh"

# Speed tracking for music volume
SPEED_ARRAY_MAX = 30  # Maximum samples in rolling average

# Camera
CAMERA_VERTICAL_THRESHOLD = -5  # Torso Y below this triggers vertical follow
CAMERA_VERTICAL_OFFSET = -210  # Pixel offset for vertical camera
CAMERA_HORIZONTAL_OFFSET = -14  # Matches original QWOP.js line 427 (was incorrectly 0 in docs)

# Game state
INITIAL_CAMERA_X = -10 * WORLD_SCALE  # -200 pixels
INITIAL_CAMERA_Y = -200  # Matches original QWOP.js camera initialization

# Camera bounds
CAMERA_BOUNDS_LEFT = -1200
CAMERA_BOUNDS_TOP = -800
CAMERA_BOUNDS_WIDTH = 800 + LEVEL_SIZE + 93  # 21893
CAMERA_BOUNDS_HEIGHT = 1600
