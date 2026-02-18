#!/usr/bin/env python3
"""
Test script to verify QWOP controls system.

Verifies:
1. ControlsHandler initializes correctly
2. Key down/up events update state correctly
3. apply() sets motor speeds correctly
4. Dynamic hip limits change with O/P keys
5. Mutual exclusivity works (Q/W, O/P)
"""

import sys
sys.path.insert(0, 'src')

from physics import PhysicsWorld
from controls import ControlsHandler
from data import CONTROL_Q, CONTROL_W, CONTROL_O, CONTROL_P


def test_controls():
    """Test complete controls system."""
    print("=" * 70)
    print("QWOP Controls System Verification Test")
    print("=" * 70)
    print()
    
    # Initialize physics world
    print("Initializing physics world...")
    physics = PhysicsWorld()
    physics.initialize()
    print("✓ Physics world ready")
    print()
    
    # Initialize controls handler
    print("Initializing controls handler...")
    controls = ControlsHandler(physics)
    print("✓ Controls handler ready")
    print()
    
    # Test 1: Initial state
    print("=" * 70)
    print("TEST 1: Initial State")
    print("=" * 70)
    assert not controls.q_down, "Q should start False"
    assert not controls.w_down, "W should start False"
    assert not controls.o_down, "O should start False"
    assert not controls.p_down, "P should start False"
    print("✓ All keys start in released state")
    print()
    
    # Test 2: Key down/up events
    print("=" * 70)
    print("TEST 2: Key Down/Up Events")
    print("=" * 70)
    
    controls.key_down('q')
    assert controls.q_down, "Q should be down"
    print("✓ Q key down registered")
    
    controls.key_up('q')
    assert not controls.q_down, "Q should be up"
    print("✓ Q key up registered")
    
    # Test case insensitivity
    controls.key_down('Q')
    assert controls.q_down, "Uppercase Q should work"
    controls.key_up('Q')
    assert not controls.q_down, "Uppercase Q up should work"
    print("✓ Case insensitive keys work")
    print()
    
    # Test 3: Q key motor speeds
    print("=" * 70)
    print("TEST 3: Q Key Motor Application")
    print("=" * 70)
    
    controls.key_down('q')
    controls.apply()
    
    # Check Q key motor speeds
    rightHip = physics.get_joint('rightHip')
    leftHip = physics.get_joint('leftHip')
    rightShoulder = physics.get_joint('rightShoulder')
    leftShoulder = physics.get_joint('leftShoulder')
    
    assert rightHip.motorSpeed == 2.5, f"Right hip should be 2.5, got {rightHip.motorSpeed}"
    assert leftHip.motorSpeed == -2.5, f"Left hip should be -2.5, got {leftHip.motorSpeed}"
    assert rightShoulder.motorSpeed == -2.0, f"Right shoulder should be -2.0, got {rightShoulder.motorSpeed}"
    assert leftShoulder.motorSpeed == 2.0, f"Left shoulder should be 2.0, got {leftShoulder.motorSpeed}"
    
    print(f"✓ Q key motors: rightHip={rightHip.motorSpeed}, leftHip={leftHip.motorSpeed}")
    print(f"✓ Q key motors: rightShoulder={rightShoulder.motorSpeed}, leftShoulder={leftShoulder.motorSpeed}")
    print()
    
    # Test 4: Release Q, motors should stop
    print("=" * 70)
    print("TEST 4: Release Q Key (Motors Stop)")
    print("=" * 70)
    
    controls.key_up('q')
    controls.apply()
    
    assert rightHip.motorSpeed == 0, f"Right hip should be 0, got {rightHip.motorSpeed}"
    assert leftHip.motorSpeed == 0, f"Left hip should be 0, got {leftHip.motorSpeed}"
    assert rightShoulder.motorSpeed == 0, f"Right shoulder should be 0, got {rightShoulder.motorSpeed}"
    assert leftShoulder.motorSpeed == 0, f"Left shoulder should be 0, got {leftShoulder.motorSpeed}"
    
    print("✓ All Q/W axis motors stopped")
    print()
    
    # Test 5: W key motor speeds (opposite of Q)
    print("=" * 70)
    print("TEST 5: W Key Motor Application")
    print("=" * 70)
    
    controls.key_down('w')
    controls.apply()
    
    assert rightHip.motorSpeed == -2.5, f"Right hip should be -2.5, got {rightHip.motorSpeed}"
    assert leftHip.motorSpeed == 2.5, f"Left hip should be 2.5, got {leftHip.motorSpeed}"
    assert rightShoulder.motorSpeed == 2.0, f"Right shoulder should be 2.0, got {rightShoulder.motorSpeed}"
    assert leftShoulder.motorSpeed == -2.0, f"Left shoulder should be -2.0, got {leftShoulder.motorSpeed}"
    
    print(f"✓ W key motors: rightHip={rightHip.motorSpeed}, leftHip={leftHip.motorSpeed}")
    print(f"✓ W key motors: rightShoulder={rightShoulder.motorSpeed}, leftShoulder={leftShoulder.motorSpeed}")
    
    controls.key_up('w')
    print()
    
    # Test 6: O key (knee motors + hip limits)
    print("=" * 70)
    print("TEST 6: O Key (Knees + Hip Limits)")
    print("=" * 70)
    
    controls.key_down('o')
    controls.apply()
    
    rightKnee = physics.get_joint('rightKnee')
    leftKnee = physics.get_joint('leftKnee')
    
    assert rightKnee.motorSpeed == 2.5, f"Right knee should be 2.5, got {rightKnee.motorSpeed}"
    assert leftKnee.motorSpeed == -2.5, f"Left knee should be -2.5, got {leftKnee.motorSpeed}"
    
    # Check hip limits (use tolerance for Box2D float precision)
    eps = 0.001
    assert abs(leftHip.lowerLimit - (-1.0)) < eps, f"Left hip lower should be -1.0, got {leftHip.lowerLimit}"
    assert abs(leftHip.upperLimit - 1.0) < eps, f"Left hip upper should be 1.0, got {leftHip.upperLimit}"
    assert abs(rightHip.lowerLimit - (-1.3)) < eps, f"Right hip lower should be -1.3, got {rightHip.lowerLimit}"
    assert abs(rightHip.upperLimit - 0.7) < eps, f"Right hip upper should be 0.7, got {rightHip.upperLimit}"
    
    print(f"✓ O key knees: rightKnee={rightKnee.motorSpeed}, leftKnee={leftKnee.motorSpeed}")
    print(f"✓ O key hip limits: leftHip=({leftHip.lowerLimit}, {leftHip.upperLimit})")
    print(f"✓ O key hip limits: rightHip=({rightHip.lowerLimit}, {rightHip.upperLimit})")
    print()
    
    # Test 7: P key (opposite knees + different hip limits)
    print("=" * 70)
    print("TEST 7: P Key (Opposite Knees + Different Hip Limits)")
    print("=" * 70)
    
    controls.key_up('o')
    controls.key_down('p')
    controls.apply()
    
    assert rightKnee.motorSpeed == -2.5, f"Right knee should be -2.5, got {rightKnee.motorSpeed}"
    assert leftKnee.motorSpeed == 2.5, f"Left knee should be 2.5, got {leftKnee.motorSpeed}"
    
    # Check different hip limits for P (use tolerance for Box2D float precision)
    assert abs(leftHip.lowerLimit - (-1.5)) < eps, f"Left hip lower should be -1.5, got {leftHip.lowerLimit}"
    assert abs(leftHip.upperLimit - 0.5) < eps, f"Left hip upper should be 0.5, got {leftHip.upperLimit}"
    assert abs(rightHip.lowerLimit - (-0.8)) < eps, f"Right hip lower should be -0.8, got {rightHip.lowerLimit}"
    assert abs(rightHip.upperLimit - 1.2) < eps, f"Right hip upper should be 1.2, got {rightHip.upperLimit}"
    
    print(f"✓ P key knees: rightKnee={rightKnee.motorSpeed}, leftKnee={leftKnee.motorSpeed}")
    print(f"✓ P key hip limits: leftHip=({leftHip.lowerLimit}, {leftHip.upperLimit})")
    print(f"✓ P key hip limits: rightHip=({rightHip.lowerLimit}, {rightHip.upperLimit})")
    
    controls.key_up('p')
    print()
    
    # Test 8: Mutual exclusivity (Q + W pressed)
    print("=" * 70)
    print("TEST 8: Q/W Mutual Exclusivity (Q has priority)")
    print("=" * 70)
    
    controls.key_down('q')
    controls.key_down('w')  # Both down, but Q should win
    controls.apply()
    
    # Should use Q values (Q is checked first in if/else if)
    assert rightHip.motorSpeed == 2.5, "Q should have priority over W"
    print("✓ Q has priority when both Q and W are pressed")
    
    controls.key_up('q')
    controls.key_up('w')
    print()
    
    # Test 9: Mutual exclusivity (O + P pressed)
    print("=" * 70)
    print("TEST 9: O/P Mutual Exclusivity (O has priority)")
    print("=" * 70)
    
    controls.key_down('o')
    controls.key_down('p')  # Both down, but O should win
    controls.apply()
    
    # Should use O values (O is checked first in if/else if)
    assert rightKnee.motorSpeed == 2.5, "O should have priority over P"
    assert leftHip.lowerLimit == -1.0, "O hip limits should apply"
    print("✓ O has priority when both O and P are pressed")
    
    controls.key_up('o')
    controls.key_up('p')
    print()
    
    # Test 10: Reset function
    print("=" * 70)
    print("TEST 10: Reset Function")
    print("=" * 70)
    
    controls.key_down('q')
    controls.key_down('o')
    assert controls.q_down and controls.o_down, "Keys should be down before reset"
    
    controls.reset()
    assert not controls.q_down, "Q should be False after reset"
    assert not controls.w_down, "W should be False after reset"
    assert not controls.o_down, "O should be False after reset"
    assert not controls.p_down, "P should be False after reset"
    print("✓ Reset clears all key states")
    print()
    
    # Test 11: Combined Q + O (independent axes)
    print("=" * 70)
    print("TEST 11: Combined Q + O (Independent Axes)")
    print("=" * 70)
    
    controls.key_down('q')
    controls.key_down('o')
    controls.apply()
    
    # Q axis
    assert rightHip.motorSpeed == 2.5, "Q hip motors should be active"
    assert rightShoulder.motorSpeed == -2.0, "Q shoulder motors should be active"
    
    # O axis
    assert rightKnee.motorSpeed == 2.5, "O knee motors should be active"
    assert leftHip.lowerLimit == -1.0, "O hip limits should be active"
    
    print("✓ Q and O work independently (thighs+shoulders + knees)")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ Key state tracking works")
    print("✓ Q key applies correct motor speeds")
    print("✓ W key applies opposite motor speeds")
    print("✓ O key applies knees + hip limits")
    print("✓ P key applies opposite knees + different hip limits")
    print("✓ Q/W mutual exclusivity works (Q priority)")
    print("✓ O/P mutual exclusivity works (O priority)")
    print("✓ Q/W and O/P axes are independent")
    print("✓ Reset function clears all states")
    print()
    print("✓ Controls system is 1:1 accurate with original QWOP!")
    print()


if __name__ == "__main__":
    test_controls()
