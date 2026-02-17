# QWOP Body Parts Structure

## Body Parts (lines 1037-1171)

### 1. Torso
- Position: (2.511, -1.871)
- Angle: -1.251 rad
- userData: "torso"

### 2. Head
- Position: (3.888, -5.622)
- Angle: 0.064 rad
- userData: "head"

### 3. Left Arm
- Position: (4.418, -2.807)
- Angle: 0.904 rad
- userData: "leftArm"

### 4. Left Forearm
- Position: (5.830, -2.873)
- Angle: -1.205 rad
- userData: "leftForearm"

### 5. Left Thigh
- Position: (2.565, 1.648)
- Angle: -2.018 rad
- userData: "leftThigh"

### 6. Left Calf
- Position: (3.126, 5.526)
- Angle: -1.590 rad
- userData: "leftCalf"

### 7. Left Foot
- Position: (3.927, 8.089)
- Angle: 0.120 rad
- userData: "leftFoot"
- Special: friction=1.5, density=3x

### 8. Right Arm
- Position: (1.181, -3.500)
- Angle: -0.522 rad
- userData: "rightArm"

### 9. Right Forearm
- Position: (0.408, -1.060)
- Angle: -1.755 rad
- userData: "rightForearm"

### 10. Right Thigh
- Position: (1.612, 2.062)
- Angle: 1.485 rad
- userData: "rightThigh"

### 11. Right Calf
- Position: (-0.073, 5.348)
- Angle: -0.759 rad
- userData: "rightCalf"

### 12. Right Foot
- Position: (-1.125, 7.567)
- Angle: 0.590 rad
- userData: "rightFoot"
- Special: friction=1.5, density=3x

## Joints (line 1173+)

### Neck (head-torso)
- Type: RevoluteJoint
- Limits: -0.5 to 0 rad
- Motor: disabled

### Right Shoulder (rightArm-torso)
- Type: RevoluteJoint
- Limits: -0.5 to 1.5 rad
- Motor: enabled, maxTorque=1000

### Left Shoulder (leftArm-torso)
- Type: RevoluteJoint
- Limits: -2 to 0 rad
- Motor: enabled, maxTorque=1000

### Left Hip (leftThigh-torso)
- Type: RevoluteJoint
- Limits: -1.5 to 0.5 rad (dynamic)
- Motor: enabled, maxTorque=6000

### Right Hip (rightThigh-torso)
- Type: RevoluteJoint
- Limits: -1.3 to 0.7 rad (dynamic)
- Motor: enabled, maxTorque=6000

### Left Elbow (leftForearm-leftArm)
- Type: RevoluteJoint
- Limits: -0.1 to 0.5 rad
- Motor: disabled

### Right Elbow (rightForearm-rightArm)
- Type: RevoluteJoint
- Limits: -0.1 to 0.5 rad
- Motor: disabled

### Left Knee (leftCalf-leftThigh)
- Type: RevoluteJoint
- Limits: -1.6 to 0 rad
- Motor: enabled, maxTorque=3000

### Right Knee (rightCalf-rightThigh)
- Type: RevoluteJoint
- Limits: -1.3 to 0.3 rad
- Motor: enabled, maxTorque=3000

### Left Ankle (leftFoot-leftCalf)
- Type: RevoluteJoint
- Limits: -0.5 to 0.5 rad
- Motor: disabled

### Right Ankle (rightFoot-rightCalf)
- Type: RevoluteJoint
- Limits: -0.5 to 0.5 rad
- Motor: disabled
