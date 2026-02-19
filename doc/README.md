# QWOP Reverse Engineering Documentation

Complete technical documentation for 1:1 recreation of QWOP in any language.

## Documentation Files

### Core Game Mechanics
1. **[QWOP_ARCHITECTURE.md](QWOP_ARCHITECTURE.md)** - Overall code structure, frameworks, variable mappings
2. **[QWOP_CONSTANTS.md](QWOP_CONSTANTS.md)** - Physics constants, simulation parameters
3. **[QWOP_CONTROLS.md](QWOP_CONTROLS.md)** - How Q/W/O/P keys control the runner

### Exact Data Files (1:1 Recreation)
4. **[QWOP_BODY_EXACT_DATA.md](QWOP_BODY_EXACT_DATA.md)** - All 12 body parts: positions, angles, physics properties, rendering depths
5. **[QWOP_JOINTS_EXACT_DATA.md](QWOP_JOINTS_EXACT_DATA.md)** - All 11 joints: anchor points, limits, motors, reference angles
6. **[QWOP_FUNCTIONS_EXACT.md](QWOP_FUNCTIONS_EXACT.md)** - Complete function logic: update loop, collision detection, camera
7. **[QWOP_COMPLETE_DATA_REFERENCE.md](QWOP_COMPLETE_DATA_REFERENCE.md)** - All remaining values: world setup, timing, audio, etc.

### Game Logic
8. **[QWOP_GAME_LOGIC.md](QWOP_GAME_LOGIC.md)** - Game loop, win/lose conditions, state management

## Quick Reference

### Body Parts (12 total)
1. Torso - Center mass
2. Head - Balance point
3. Left/Right Arm - Upper arms
4. Left/Right Forearm - Lower arms
5. Left/Right Thigh - Upper legs
6. Left/Right Calf - Lower legs
7. Left/Right Foot - Ground contact (3x heavier, high friction)

### Joints (11 total)
1. Neck (head ↔ torso) - Passive
2. Left/Right Shoulder (arm ↔ torso) - Motorized (1000 torque)
3. Left/Right Elbow (forearm ↔ arm) - Passive
4. Left/Right Hip (thigh ↔ torso) - Motorized (6000 torque) **MAIN CONTROL**
5. Left/Right Knee (calf ↔ thigh) - Motorized (3000 torque) **MAIN CONTROL**
6. Left/Right Ankle (foot ↔ calf) - Passive

### Controls
- **Q** = Right thigh forward (-2.5), Left thigh back (+2.5)
- **W** = Left thigh forward (+2.5), Right thigh back (-2.5)
- **O** = Right calf forward (+2.5), Left calf back (-2.5)
- **P** = Left calf forward (+2.5), Right calf back (-2.5)

### Critical Constants
```
worldScale = 20        (pixels per meter)
gravity = 10           (m/s²)
physicsTimeStep = 0.04 (25 FPS)
levelSize = 21000      (pixels)
sandPitAt = 20000      (jump landing zone)
hurdleAt = 10000       (obstacle location)
```

### Physics Simulation
```javascript
m_world.step(0.04, 5, 5)  // timeStep, velocityIter, positionIter
```

### Head Stabilization (Critical!)
```javascript
head.applyTorque(-4 * (head.angle + 0.2))  // Every frame
```

## Data Completeness

### ✅ Fully Documented
- [x] All 12 body part initial positions (to 16 decimal places)
- [x] All 12 body part initial angles (to 16 decimal places)
- [x] All 12 body part physics properties
- [x] All 11 joint anchor points (world coordinates)
- [x] All 11 joint configurations (limits, motors, reference angles)
- [x] Complete update() function logic
- [x] Complete beginContact() collision detection
- [x] Camera follow system
- [x] Control input mapping
- [x] Physics world setup
- [x] Game state machine
- [x] Timing and frame rates
- [x] Audio system
- [x] Collision categories and filters

### ⚠️ Not Critical for Gameplay
- [ ] Sprite UV coordinates (visual only)
- [ ] Shader code (visual effects only)
- [ ] Particle effects (visual only)
- [ ] UI layout (not gameplay)
- [ ] Font rendering (not gameplay)

## Implementation Checklist

### Phase 1: Basic Physics
- [ ] Set up Box2D/PyMunk world with gravity
- [ ] Create 12 body parts with exact positions/angles
- [ ] Create 11 joints with exact anchor points and limits
- [ ] Verify initial pose matches QWOP

### Phase 2: Controls
- [ ] Implement Q/W/O/P key input
- [ ] Set motor speeds based on key state
- [ ] Implement dynamic hip limits (O/P keys)
- [ ] Add head stabilization torque

### Phase 3: Game Logic
- [ ] Implement update loop (0.04s timestep)
- [ ] Add collision detection (feet vs track, head/arms vs track)
- [ ] Implement camera follow system
- [ ] Add score tracking

### Phase 4: Polish
- [ ] Add hurdle obstacle
- [ ] Implement jump detection
- [ ] Add audio (optional)
- [ ] Add visual effects (optional)

## Key Insights

### Why QWOP is Hard
1. **Opposite motor directions** - Q moves right thigh forward AND left thigh back
2. **Slow motor speeds** - 2.5 rad/s is very slow for human reaction time
3. **Realistic physics** - No cheating, pure ragdoll simulation
4. **Balance required** - Head stabilization torque is weak (-4), easy to tip over
5. **Coordination needed** - Must control 4 independent motors simultaneously

### Critical Implementation Details
1. **Feet are 3x heavier** - Provides stability, don't skip this
2. **Feet have 1.5 friction** - Ground grip, essential for walking
3. **Head stabilization** - Without this, runner falls immediately
4. **Hip limits change** - O/P keys adjust hip joint limits dynamically
5. **Reference angles matter** - Joint motors behave relative to reference angle
6. **Collision filters** - maskBits=65533 prevents some self-collisions

### Common Pitfalls
1. ❌ Forgetting to divide pixel coordinates by worldScale (20)
2. ❌ Using wrong physics timestep (must be 0.04s)
3. ❌ Skipping head stabilization torque
4. ❌ Not making feet 3x heavier
5. ❌ Wrong motor directions (Q should be +2.5 right, -2.5 left)
6. ❌ Forgetting dynamic hip limits with O/P keys

## Testing Your Recreation

### Visual Verification
1. Initial pose should look like QWOP start screen
2. Body parts should be same relative sizes
3. Depth ordering: left limbs in front, right limbs behind torso

### Physics Verification
1. Runner should stand upright initially
2. Pressing Q should move right thigh forward
3. Pressing O should move right calf forward
4. No keys = runner should balance briefly then fall
5. Head should wobble but try to stay upright

### Gameplay Verification
1. Score should increase as runner moves right
2. Falling (head/arms hit ground) should trigger game over
3. Camera should follow runner horizontally
4. Jump should trigger at x=19780, land at x=20000

## Source Code Locations

Key sections in original QWOP.js:
- Lines 1-200: Framework setup
- Lines 436-529: Game initialization
- Lines 530-847: World/player creation
- Lines 848-856: Reset function
- Lines 857-911: Main update loop
- Lines 912-954: Collision detection
- Lines 1033-1173: Player body/joint creation
- Line 12749: Global constants

## Questions?

If you find any missing data or discrepancies, check the original QWOP.js file at:
`/Users/b407404/qwop-python/legacy/QWOP.js`

All values in this documentation are extracted directly from the source code.
