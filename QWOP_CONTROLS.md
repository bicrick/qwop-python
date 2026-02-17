# QWOP Control System

## Key Bindings (line 876)

### Q Key - Right Thigh Forward / Left Thigh Back
```javascript
rightHip.setMotorSpeed(2.5)
leftHip.setMotorSpeed(-2.5)
rightShoulder.setMotorSpeed(-2)
rightElbow.setMotorSpeed(-10)
leftShoulder.setMotorSpeed(2)
leftElbow.setMotorSpeed(-10)
```

### W Key - Left Thigh Forward / Right Thigh Back
```javascript
rightHip.setMotorSpeed(-2.5)
leftHip.setMotorSpeed(2.5)
rightShoulder.setMotorSpeed(2)
rightElbow.setMotorSpeed(10)
leftShoulder.setMotorSpeed(-2)
leftElbow.setMotorSpeed(10)
```

### O Key - Right Calf Forward / Left Calf Back
```javascript
rightKnee.setMotorSpeed(2.5)
leftKnee.setMotorSpeed(-2.5)
leftHip.setLimits(-1, 1)
rightHip.setLimits(-1.3, 0.7)
```

### P Key - Left Calf Forward / Right Calf Back
```javascript
rightKnee.setMotorSpeed(-2.5)
leftKnee.setMotorSpeed(2.5)
leftHip.setLimits(-1.5, 0.5)
rightHip.setLimits(-0.8, 1.2)
```

### No Key Pressed
```javascript
rightHip.setMotorSpeed(0)
leftHip.setMotorSpeed(0)
leftShoulder.setMotorSpeed(0)
rightShoulder.setMotorSpeed(0)
rightKnee.setMotorSpeed(0)
leftKnee.setMotorSpeed(0)
```

## Key Observations
- Q/W control THIGHS (hips) + arms swing for balance
- O/P control CALVES (knees) + adjust hip limits
- Motor speeds are relatively slow (2.5 for legs, 2 for arms)
- Hip limits change dynamically with O/P to allow different leg positions
