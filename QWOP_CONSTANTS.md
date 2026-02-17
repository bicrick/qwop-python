# QWOP Physics Constants

## Global Constants (line 12749)
```javascript
l.levelSize = 21000        // Total track length
l.gravity = 10             // Gravity strength
l.torqueFactor = 1         // Joint torque multiplier
l.densityFactor = 1        // Body density multiplier
l.sandPitAt = 20000        // Sand pit location (jump landing)
l.hurdleAt = 10000         // Hurdle location
l.worldScale = 20          // Physics to pixel scale
l.screenWidth = 640        // Screen width
l.screenHeight = 400       // Screen height
```

## Body Part Physics Properties
All body parts use:
- `categoryBits = 2` (collision category)
- `maskBits = 65533` (what they collide with)
- `friction = 0.2` (except feet: 1.5)
- `restitution = 0` (no bounce)
- `density = l.densityFactor` (except feet: 3x)

## Joint Motor Torques
- **Shoulders**: 1000 * torqueFactor
- **Elbows**: 0 (passive joints)
- **Hips**: 6000 * torqueFactor
- **Knees**: 3000 * torqueFactor
- **Ankles**: 2000 * torqueFactor (passive)

## Physics Simulation
- Time step: 0.04 seconds
- Velocity iterations: 5
- Position iterations: 5
