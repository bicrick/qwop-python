# QWOP Joints - Exact Data for 1:1 Recreation

## Joint Anchor Points (World Coordinates)

All coordinates are in Box2D world units (divide by worldScale=20 to get pixels).

### 1. NECK (head ↔ torso)
```
World Anchor Point: (3.5885141908253755, -4.526224223627244)

localAnchorA (head):  (3.5885141908253755, -4.526224223627244)
localAnchorB (torso): (3.588733341630704, -4.526434658500262)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.0 rad
- lowerAngle: -0.5 rad
- enableMotor: false
- maxMotorTorque: 0
- referenceAngle: -1.308996406363529 rad
```

### 2. RIGHT SHOULDER (rightArm ↔ torso)
```
World Anchor Point: (2.228476821818547, -4.086468732185028)

localAnchorA (rightArm): (2.228476821818547, -4.086468732185028)
localAnchorB (torso):    (2.228929993886102, -4.08707555939957)

Joint Configuration:
- enableLimit: true
- upperAngle: 1.5 rad (85.94°)
- lowerAngle: -0.5 rad (-28.65°)
- enableMotor: true
- maxMotorTorque: 1000 * torqueFactor
- referenceAngle: -0.7853907065463961 rad (-45.00°)
```

### 3. LEFT SHOULDER (leftArm ↔ torso)
```
World Anchor Point: (3.6241979856895377, -3.5334881618011442)

localAnchorA (leftArm): (3.6241979856895377, -3.5334881618011442)
localAnchorB (torso):   (3.6241778782207157, -3.533950434531982)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.0 rad
- lowerAngle: -2.0 rad (-114.59°)
- enableMotor: true
- maxMotorTorque: 1000 * torqueFactor
- referenceAngle: -2.09438311816829 rad (-120.00°)
```

### 4. LEFT HIP (leftThigh ↔ torso)
```
World Anchor Point: (2.0030339754142847, 0.23737160622781284)

localAnchorA (leftThigh): (2.0030339754142847, 0.23737160622781284)
localAnchorB (torso):     (2.003367181376716, 0.23802590387419476)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.5 rad (28.65°) [DYNAMIC - changes with O/P]
- lowerAngle: -1.5 rad (-85.94°) [DYNAMIC - changes with O/P]
- enableMotor: true
- maxMotorTorque: 6000 * torqueFactor
- referenceAngle: 0.7258477508944043 rad (41.59°)

Dynamic Limits:
- Default: upperAngle=0.5, lowerAngle=-1.5
- When O pressed: upperAngle=1.0, lowerAngle=-1.0
- When P pressed: upperAngle=0.5, lowerAngle=-1.5
```

### 5. RIGHT HIP (rightThigh ↔ torso)
```
World Anchor Point: (1.2475900729227194, -0.011046642863645761)

localAnchorA (rightThigh): (1.2475900729227194, -0.011046642863645761)
localAnchorB (torso):      (1.2470052823973599, -0.011635347168778898)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.7 rad (40.11°) [DYNAMIC - changes with O/P]
- lowerAngle: -1.3 rad (-74.48°) [DYNAMIC - changes with O/P]
- enableMotor: true
- maxMotorTorque: 6000 * torqueFactor
- referenceAngle: -2.719359381718199 rad (-155.81°)

Dynamic Limits:
- Default: upperAngle=0.7, lowerAngle=-1.3
- When O pressed: upperAngle=0.7, lowerAngle=-1.3
- When P pressed: upperAngle=1.2, lowerAngle=-0.8
```

### 6. LEFT ELBOW (leftForearm ↔ leftArm)
```
World Anchor Point: (5.525375332758792, -1.63856204930891)

localAnchorA (leftForearm): (5.525375332758792, -1.63856204930891)
localAnchorB (leftArm):     (5.52537532948459, -1.6385620366077662)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.5 rad (28.65°)
- lowerAngle: -0.1 rad (-5.73°)
- enableMotor: false
- maxMotorTorque: 0
- referenceAngle: 2.09438311816829 rad (120.00°)
```

### 7. RIGHT ELBOW (rightForearm ↔ rightArm)
```
World Anchor Point: (-0.006090859076100963, -2.8004758838752157)

localAnchorA (rightForearm): (-0.006090859076100963, -2.8004758838752157)
localAnchorB (rightArm):     (-0.0060908611708438976, -2.8004758929205846)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.5 rad (28.65°)
- lowerAngle: -0.1 rad (-5.73°)
- enableMotor: false
- maxMotorTorque: 0
- referenceAngle: 1.2968199012274688 rad (74.29°)
```

### 8. LEFT KNEE (leftCalf ↔ leftThigh)
```
World Anchor Point: (3.384323411985692, 3.5168931240916876)

localAnchorA (leftCalf):  (3.384323411985692, 3.5168931240916876)
localAnchorB (leftThigh): (3.3844684376952108, 3.5174122997898016)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.0 rad
- lowerAngle: -1.6 rad (-91.67°)
- enableMotor: true
- maxMotorTorque: 3000 * torqueFactor
- referenceAngle: -0.3953113764119829 rad (-22.65°)
```

### 9. RIGHT KNEE (rightCalf ↔ rightThigh)
```
World Anchor Point: (1.4982369235492752, 4.175600306005656)

localAnchorA (rightCalf):  (1.4982369235492752, 4.175600306005656)
localAnchorB (rightThigh): (1.4982043532615996, 4.17493520671361)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.3 rad (17.19°)
- lowerAngle: -1.3 rad (-74.48°)
- enableMotor: true
- maxMotorTorque: 3000 * torqueFactor
- referenceAngle: 2.2893406247158676 rad (131.18°)
```

### 10. LEFT ANKLE (leftFoot ↔ leftCalf)
```
World Anchor Point: (3.312322507818897, 7.947704853895541)

localAnchorA (leftFoot): (3.312322507818897, 7.947704853895541)
localAnchorB (leftCalf): (3.3123224825088817, 7.947704836256229)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.5 rad (28.65°)
- lowerAngle: -0.5 rad (-28.65°)
- enableMotor: false
- maxMotorTorque: 2000 * torqueFactor (unused, motor disabled)
- referenceAngle: -1.7244327585010226 rad (-98.79°)
```

### 11. RIGHT ANKLE (rightFoot ↔ rightCalf)
```
World Anchor Point: (-1.6562855402197227, 6.961551452557676)

localAnchorA (rightFoot): (-1.6562855402197227, 6.961551452557676)
localAnchorB (rightCalf): (-1.655726670462596, 6.961493826969391)

Joint Configuration:
- enableLimit: true
- upperAngle: 0.5 rad (28.65°)
- lowerAngle: -0.5 rad (-28.65°)
- enableMotor: false
- maxMotorTorque: 2000 * torqueFactor (unused, motor disabled)
- referenceAngle: -1.5708045825942758 rad (-90.00°)
```

## Initial Motor States (after creation)

All motors are initialized with these settings:

```javascript
// Hips
rightHip.setMotorSpeed(0)
rightHip.enableLimit(true)
rightHip.enableMotor(true)

leftHip.setMotorSpeed(0)
leftHip.enableLimit(true)
leftHip.enableMotor(true)

// Knees
rightKnee.setMotorSpeed(0)
rightKnee.enableLimit(true)
rightKnee.enableMotor(true)

leftKnee.setMotorSpeed(0)
leftKnee.enableLimit(true)
leftKnee.enableMotor(true)

// Shoulders
rightShoulder.setMotorSpeed(0)
rightShoulder.enableLimit(true)
rightShoulder.enableMotor(true)

leftShoulder.setMotorSpeed(0)
leftShoulder.enableLimit(true)
leftShoulder.enableMotor(true)
```

## Joint Type

All joints are **B2RevoluteJointDef** (revolute/hinge joints).

## Notes for 1:1 Recreation

1. **localAnchorA/B**: These are computed using `getLocalPoint()` which converts world coordinates to body-local coordinates. For exact recreation, you can either:
   - Use the world coordinates and let Box2D compute local anchors
   - Or use these exact local anchor values directly

2. **Reference Angle**: This is the angle difference between the two bodies when the joint is at "zero" rotation. Critical for motor behavior.

3. **Dynamic Limits**: The hip joint limits change based on O/P key state. This is handled in the update loop (line 876).

4. **Motor Speeds**: Set in the update loop based on Q/W/O/P key states (documented in QWOP_CONTROLS.md).

5. **Coordinate System**: Box2D uses meters, not pixels. All these coordinates are in meters. Multiply by worldScale (20) to get pixel coordinates.
