"""
QWOP Controls System

Handles keyboard input translation to Box2D joint motor commands.
Implements the exact control logic from the original QWOP game:
- Q/W axis: Thigh (hip) and shoulder control (mutually exclusive)
- O/P axis: Calf (knee) control + dynamic hip limits (mutually exclusive)

All motor speeds and hip limits match doc/reference/QWOP_FUNCTIONS_EXACT.md lines 94-139.
"""

from .data import CONTROL_Q, CONTROL_W, CONTROL_O, CONTROL_P, DEFAULT_HIP_LIMITS


class ControlsHandler:
    """
    Manages QWOP control input and applies motor commands to physics joints.
    
    Tracks Q/W/O/P key states and translates them into motor speeds and
    hip limit adjustments. Called once per frame from the game update loop.
    
    Key behavior:
    - Q/W are mutually exclusive (if/else if/else)
    - O/P are mutually exclusive (if/else if/else)
    - When no key in an axis is pressed, motors are set to 0
    """
    
    def __init__(self, physics_world):
        """
        Initialize controls handler.
        
        Args:
            physics_world: PhysicsWorld instance with initialized joints
        """
        self.physics = physics_world
        
        # Key state tracking
        self.q_down = False
        self.w_down = False
        self.o_down = False
        self.p_down = False
    
    def key_down(self, key):
        """
        Handle key press event.
        
        Args:
            key: Key identifier (string like 'q', 'Q', or pygame key constant)
        """
        # Normalize to lowercase string for comparison
        key_str = self._normalize_key(key)
        
        if key_str == 'q':
            self.q_down = True
        elif key_str == 'w':
            self.w_down = True
        elif key_str == 'o':
            self.o_down = True
        elif key_str == 'p':
            self.p_down = True
    
    def key_up(self, key):
        """
        Handle key release event.
        
        Args:
            key: Key identifier (string like 'q', 'Q', or pygame key constant)
        """
        # Normalize to lowercase string for comparison
        key_str = self._normalize_key(key)
        
        if key_str == 'q':
            self.q_down = False
        elif key_str == 'w':
            self.w_down = False
        elif key_str == 'o':
            self.o_down = False
        elif key_str == 'p':
            self.p_down = False
    
    def _normalize_key(self, key):
        """
        Normalize key identifier to lowercase string.
        
        Args:
            key: Key identifier (string or pygame constant)
            
        Returns:
            Lowercase string ('q', 'w', 'o', 'p', or empty string)
        """
        # If it's already a string, convert to lowercase
        if isinstance(key, str):
            return key.lower()
        
        # If it's a pygame key constant, we'll handle it in Stage 8
        # For now, try to get the name attribute if it exists
        if hasattr(key, 'name'):
            return key.name.lower()
        
        # Otherwise convert to string and lowercase
        return str(key).lower()
    
    def apply(self):
        """
        Apply current control state to physics joints.
        
        Called once per frame from game update loop, after head stabilization
        and before physics step. Implements exact logic from original QWOP:
        
        Q/W axis (if/else if/else):
        - Q: rightHip=2.5, leftHip=-2.5, shoulders ±2
        - W: opposite signs
        - Neither: all motors = 0
        
        O/P axis (if/else if/else):
        - O: knees ±2.5, hip limits adjust
        - P: knees opposite, different hip limits
        - Neither: knee motors = 0
        """
        # Q/W AXIS: Thigh and shoulder control (mutually exclusive)
        if self.q_down:
            # Q Key: Right thigh forward, left thigh back
            self._apply_motor_speeds(CONTROL_Q['motor_speeds'])
        elif self.w_down:
            # W Key: Left thigh forward, right thigh back
            self._apply_motor_speeds(CONTROL_W['motor_speeds'])
        else:
            # No Q/W: Stop hip and shoulder motors
            self._stop_motors(['rightHip', 'leftHip', 'rightShoulder', 'leftShoulder'])
        
        # O/P AXIS: Knee control + dynamic hip limits (mutually exclusive)
        if self.o_down:
            # O Key: Right calf forward, left calf back
            self._apply_motor_speeds(CONTROL_O['motor_speeds'])
            self._apply_hip_limits(CONTROL_O['hip_limits'])
        elif self.p_down:
            # P Key: Left calf forward, right calf back
            self._apply_motor_speeds(CONTROL_P['motor_speeds'])
            self._apply_hip_limits(CONTROL_P['hip_limits'])
        else:
            # No O/P: Stop knee motors and restore default hip limits for Q/W running
            self._stop_motors(['rightKnee', 'leftKnee'])
            self._apply_hip_limits(DEFAULT_HIP_LIMITS)
    
    def _apply_motor_speeds(self, motor_speeds):
        """
        Apply motor speeds to joints.
        
        Args:
            motor_speeds: Dict of joint_name -> speed
        """
        for joint_name, speed in motor_speeds.items():
            joint = self.physics.get_joint(joint_name)
            if joint is not None:
                joint.motorSpeed = speed
    
    def _stop_motors(self, joint_names):
        """
        Set motor speeds to 0 for specified joints.
        
        Args:
            joint_names: List of joint names to stop
        """
        for joint_name in joint_names:
            joint = self.physics.get_joint(joint_name)
            if joint is not None:
                joint.motorSpeed = 0
    
    def _apply_hip_limits(self, hip_limits):
        """
        Apply angle limits to hip joints.
        
        Args:
            hip_limits: Dict of joint_name -> (lower, upper) tuple
        """
        for joint_name, (lower, upper) in hip_limits.items():
            joint = self.physics.get_joint(joint_name)
            if joint is not None:
                # PyBox2D revolute joints support direct limit setting
                joint.lowerLimit = lower
                joint.upperLimit = upper
    
    def reset(self):
        """
        Reset all control states to False.
        
        Called on game reset (R key).
        """
        self.q_down = False
        self.w_down = False
        self.o_down = False
        self.p_down = False
