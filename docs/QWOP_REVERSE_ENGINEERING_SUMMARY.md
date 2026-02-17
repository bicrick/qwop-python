# QWOP Reverse Engineering Summary

## What We've Documented

This directory contains documentation extracted from the obfuscated QWOP.js file (12,750 lines).

### Documentation Files

1. **QWOP_ARCHITECTURE.md** - Overall code structure, frameworks, variable mappings
2. **QWOP_CONSTANTS.md** - Physics constants, simulation parameters
3. **QWOP_CONTROLS.md** - How Q/W/O/P keys control the runner
4. **QWOP_BODY_PARTS.md** - All 12 body parts, their positions, and 11 joints
5. **QWOP_GAME_LOGIC.md** - Game loop, win/lose conditions, state management

## Key Findings

### The Control System
QWOP is brilliantly simple:
- **Q/W** control the THIGHS (hip joints) with opposite motor speeds
- **O/P** control the CALVES (knee joints) with opposite motor speeds
- Arms swing automatically for balance
- Hip joint limits adjust dynamically with O/P for different stances

### The Physics
- Built on Box2D physics engine
- 12 body parts connected by 11 revolute joints
- Hips have strongest motors (6000 torque)
- Knees have medium motors (3000 torque)
- Shoulders have weak motors (1000 torque)
- Elbows and ankles are passive (no motors)

### The Challenge
The difficulty comes from:
1. Opposite motor directions (Q moves right thigh forward, left thigh back)
2. Slow motor speeds (2.5 rad/s for legs)
3. Realistic physics with gravity and momentum
4. Need to coordinate 4 keys to maintain balance

## For Python Recreation

### Recommended Stack
- **Physics**: PyMunk (Pythonic) or PyBox2D (direct port)
- **Graphics**: Pygame (simple) or Pyglet (more features)
- **Structure**: OOP with component pattern

### Core Classes Needed
1. `PhysicsWorld` - Box2D world wrapper
2. `BodyPart` - Individual limb with sprite + physics
3. `Joint` - Revolute joint wrapper with motor control
4. `Runner` - Player ragdoll with 12 parts + 11 joints
5. `Game` - Main loop, input, camera, scoring
6. `Camera` - Follow player, bounds checking

### Initial Steps
1. Set up physics world with gravity
2. Create static ground
3. Build runner ragdoll from constants
4. Implement Q/W/O/P motor control
5. Add camera following
6. Implement collision detection
7. Add win/lose logic

## Next Steps for Further Analysis

If you want to dig deeper:
1. Extract exact joint anchor points (line 1173+)
2. Analyze shader code for visual effects
3. Document collision categories and masks
4. Extract audio trigger conditions
5. Study camera smoothing algorithm
6. Analyze mobile touch controls
7. Document UI layout and sprites

## Code Locations

Key sections in QWOP.js:
- Lines 1-200: Framework setup
- Lines 436-529: Game initialization
- Lines 530-847: World/player creation
- Lines 848-856: Reset function
- Lines 857-905: Main update loop
- Lines 876-903: Control input handling
- Lines 1033-1173: Player body creation
- Lines 1173+: Joint creation
- Line 12749: Global constants
