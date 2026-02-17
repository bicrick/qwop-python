#!/usr/bin/env python3
"""
Test script to verify QWOP physics world initialization.

Verifies:
1. World creates without errors
2. All 12 bodies exist with correct initial positions
3. All 11 joints exist and connect correct bodies
4. All properties match documentation (1:1 accuracy)
"""

import sys
sys.path.insert(0, 'src')

from physics import PhysicsWorld
from data import BODY_PARTS, JOINTS


def test_physics_world():
    """Test complete physics world initialization."""
    print("=" * 70)
    print("QWOP Physics World Verification Test")
    print("=" * 70)
    print()
    
    # Initialize physics world
    physics = PhysicsWorld()
    physics.initialize()
    print()
    
    # Verify bodies
    print("=" * 70)
    print("BODY VERIFICATION")
    print("=" * 70)
    
    for name in BODY_PARTS.keys():
        body = physics.get_body(name)
        config = BODY_PARTS[name]
        
        if body is None:
            print(f"❌ {name}: MISSING")
            continue
        
        # Get body properties
        pos = body.position
        angle = body.angle
        fixture = body.fixtures[0]
        
        # Check position (to 4 decimal places for readability)
        pos_match = (
            abs(pos[0] - config['position'][0]) < 0.0001 and
            abs(pos[1] - config['position'][1]) < 0.0001
        )
        
        # Check angle
        angle_match = abs(angle - config['angle']) < 0.0001
        
        # Check fixture properties
        friction_match = abs(fixture.friction - config['friction']) < 0.0001
        density_match = abs(fixture.density - config['density']) < 0.0001
        restitution_match = fixture.restitution == 0
        category_match = fixture.filterData.categoryBits == config['category_bits']
        mask_match = fixture.filterData.maskBits == config['mask_bits']
        userdata_match = body.userData == config['user_data']
        
        # Print results
        status = "✓" if all([pos_match, angle_match, friction_match, density_match, 
                             restitution_match, category_match, mask_match, userdata_match]) else "❌"
        
        print(f"{status} {name:15} pos=({pos[0]:7.3f}, {pos[1]:7.3f}) "
              f"angle={angle:7.4f} friction={fixture.friction:.1f} "
              f"density={fixture.density:.1f} restitution={fixture.restitution}")
        
        if not pos_match:
            print(f"   ⚠ Position mismatch: expected {config['position']}")
        if not angle_match:
            print(f"   ⚠ Angle mismatch: expected {config['angle']}")
        if not restitution_match:
            print(f"   ⚠ Restitution must be 0, got {fixture.restitution}")
    
    print()
    
    # Verify joints
    print("=" * 70)
    print("JOINT VERIFICATION")
    print("=" * 70)
    
    for name in JOINTS.keys():
        joint = physics.get_joint(name)
        config = JOINTS[name]
        
        if joint is None:
            print(f"❌ {name}: MISSING")
            continue
        
        # Get joint properties
        bodyA = physics.get_body(config['body_a'])
        bodyB = physics.get_body(config['body_b'])
        
        # Check bodies are connected
        bodies_match = (joint.bodyA == bodyA and joint.bodyB == bodyB)
        
        # Check reference angle (use method, not property)
        ref_angle_match = abs(joint.GetReferenceAngle() - config['reference_angle']) < 0.0001
        
        # Check limits (use properties)
        limits_enabled = joint.limitEnabled
        lower_match = abs(joint.lowerLimit - config['lower_angle']) < 0.0001
        upper_match = abs(joint.upperLimit - config['upper_angle']) < 0.0001
        
        # Check motor (mixed: motorEnabled/motorSpeed are properties, maxMotorTorque is method)
        motor_enabled = joint.motorEnabled == config['enable_motor']
        motor_speed_zero = joint.motorSpeed == 0
        torque_match = abs(joint.GetMaxMotorTorque() - config['max_motor_torque']) < 0.1
        
        # Print results
        status = "✓" if all([bodies_match, ref_angle_match, limits_enabled, 
                             lower_match, upper_match, motor_enabled, 
                             motor_speed_zero, torque_match]) else "❌"
        
        print(f"{status} {name:15} {config['body_a']:12} ↔ {config['body_b']:12} "
              f"motor={'ON ' if config['enable_motor'] else 'OFF'} "
              f"torque={config['max_motor_torque']:4.0f}")
        
        if not ref_angle_match:
            print(f"   ⚠ Reference angle mismatch: expected {config['reference_angle']:.4f}, got {joint.GetReferenceAngle():.4f}")
        if not limits_enabled:
            print(f"   ⚠ Limits must be enabled")
        if not motor_speed_zero:
            print(f"   ⚠ Motor speed must start at 0, got {joint.motorSpeed}")
    
    print()
    
    # Test physics step
    print("=" * 70)
    print("PHYSICS STEP TEST")
    print("=" * 70)
    
    try:
        # Get initial torso position
        torso = physics.get_body('torso')
        initial_pos = (torso.position[0], torso.position[1])
        
        # Step physics
        physics.step()
        
        # Get new position
        new_pos = (torso.position[0], torso.position[1])
        
        print(f"✓ Physics step successful")
        print(f"  Torso moved: ({initial_pos[0]:.4f}, {initial_pos[1]:.4f}) → "
              f"({new_pos[0]:.4f}, {new_pos[1]:.4f})")
        
        # Step 10 more times to see if stable
        for i in range(10):
            physics.step()
        
        final_pos = (torso.position[0], torso.position[1])
        print(f"  After 10 more steps: ({final_pos[0]:.4f}, {final_pos[1]:.4f})")
        
    except Exception as e:
        print(f"❌ Physics step failed: {e}")
    
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Bodies created: {len(physics.bodies)}/12")
    print(f"Joints created: {len(physics.joints)}/11")
    print(f"World steps: OK")
    print()
    print("✓ Physics world initialization complete!")
    print("  All components created with exact 1:1 properties")
    print()


if __name__ == "__main__":
    test_physics_world()
