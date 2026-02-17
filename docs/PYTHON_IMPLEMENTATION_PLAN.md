# QWOP Python Implementation Plan

## Goal

Create a 1:1 recreation of QWOP in Python using PyBox2D for exact physics matching, suitable for AI training.

## Technology Stack

- **Physics**: PyBox2D (Box2D wrapper - same engine as original)
- **Rendering**: Pygame (simple 2D graphics)
- **Platform**: macOS, Python 3.9, conda environment

## Why PyBox2D?

QWOP uses Box2D physics engine. PyBox2D is the official Python wrapper for Box2D, guaranteeing:
- Identical physics simulation
- Same joint behavior
- Same collision detection
- All extracted data (positions, angles, anchor points) maps directly

## High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│                   Main Loop                      │
│  - Handle input (Q/W/O/P keys)                  │
│  - Update physics (0.04s fixed timestep)        │
│  - Update game state (score, flags)             │
│  - Render frame                                 │
└─────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ Physics │   │ Controls │   │ Renderer │
   │  World  │   │ Handler  │   │          │
   └─────────┘   └──────────┘   └──────────┘
        │
        ├── 12 Body Parts (dynamic bodies)
        ├── 11 Joints (revolute/hinge)
        ├── Ground (static body)
        └── Contact Listener (collision detection)
```

## Implementation Phases

### Phase 1: Setup Environment
- Create conda environment
- Install PyBox2D via conda-forge
- Install Pygame via pip
- Verify imports work

### Phase 2: Data Module
Create single `data.py` file containing:
- All constants (gravity, worldScale, torqueFactor, etc.)
- 12 body part configurations (position, angle, size, physics properties)
- 11 joint configurations (anchors, limits, motors, reference angles)
- Collision categories and masks
- Control mappings (Q/W/O/P to motor speeds)

**Source**: All 17 documentation files in `/docs`

### Phase 3: Physics System
Create `physics.py` with:
- Box2D world initialization
- Ground/track creation (static body)
- 12 body part creation with exact shapes
- 11 joint creation with exact anchors and limits
- Helper methods to access bodies and joints

**Key Details**:
- Body type = `b2_dynamicBody` for all player parts
- Feet: friction=1.5, density=3.0 (special properties)
- Collision filters: categoryBits=2, maskBits=65533 (no self-collision)
- Joint anchors use world coordinates

### Phase 4: Collision Detection
Create `collision.py` with:
- `b2ContactListener` subclass
- `BeginContact()` method with exact logic:
  - Foot + track → jump/landing detection
  - Head/arm/forearm + track → fall detection
  - Impact velocity calculation
  - Score updates
- Handle both fixture orderings (A/B can be swapped)

**Key Details**:
- Check userData strings for identification
- Find rightmost contact point for distance tracking
- Jump triggers at x > 19780, landing at x > 20000
- Impact sound threshold at velocity > 5

### Phase 5: Controls
Create `controls.py` with:
- Input state tracking (QDown, WDown, ODown, PDown)
- Motor speed application based on key state
- Dynamic hip limit adjustment with O/P keys
- Q/W are mutually exclusive, O/P are mutually exclusive

**Key Details**:
- Q: rightHip=2.5, leftHip=-2.5, shoulders +-2
- W: opposite of Q
- O: knees +-2.5, hip limits change
- P: opposite of O, different hip limits
- Elbow motor calls are no-ops (motors disabled)

### Phase 6: Game Logic
Create `game.py` with:
- Game state tracking (fallen, jumped, jumpLanded, gameEnded, etc.)
- Update loop with exact sequence:
  1. Update score time
  2. Head stabilization torque: `-4 * (head.angle + 0.2)`
  3. Apply control inputs
  4. Physics step: `world.Step(0.04, 5, 5)`
  5. Camera follow (torso x position)
  6. Score calculation (torso x / 10)
  7. Game end detection
- Camera system (follows torso, vertical offset when jumping)
- Reset function

**Key Details**:
- Physics timestep FIXED at 0.04s (25 FPS)
- Head stabilization is critical for balance
- Camera follows torso, not head
- Score in meters = world x position / 10

### Phase 7: Renderer
Create `renderer.py` with:
- Pygame window (640x400)
- Camera transform (world coords to screen coords)
- Body part drawing (colored rectangles initially)
- Depth ordering (left limbs in front, right behind)
- Score display
- Simple UI

**Key Details**:
- Convert Box2D coords to screen: `x * worldScale`, flip y-axis
- Apply camera offset
- Depth order matters for visual correctness

### Phase 8: Main Entry Point
Create `play.py` with:
- Pygame initialization
- System integration
- Main game loop (60 FPS rendering, 25 FPS physics)
- Event handling
- Reset on 'R' key

## Data Completeness

### ✅ We Have (100%)
- All 12 body part positions (16 decimal precision)
- All 12 body part angles (16 decimal precision)
- All 12 body part dimensions (EXACT from browser)
- All 12 body part physics properties
- All 11 joint anchor points (world coordinates)
- All 11 joint limits and reference angles
- All 11 joint motor configurations
- Complete collision detection logic
- Complete control mapping
- Complete update loop logic
- Camera follow algorithm
- Game state machine

### ⚠️ Not Needed for Physics
- Sprite textures (can use colored rectangles)
- Shaders (visual effects only)
- Audio files (not gameplay critical)
- UI sprites (not gameplay critical)

## Critical Implementation Details

### Must-Have Features
1. **Feet properties**: friction=1.5, density=3.0 (not 0.2 and 1.0)
2. **Head stabilization**: Apply torque every frame: `-4 * (angle + 0.2)`
3. **Fixed timestep**: Always 0.04s, never variable
4. **Collision filters**: maskBits=65533 prevents self-collision
5. **Dynamic hip limits**: Change with O/P keys
6. **Reference angles**: Critical for joint motor behavior
7. **Both fixture orderings**: Check A→B and B→A in collision detection

### Common Pitfalls to Avoid
1. Forgetting to divide pixel coords by worldScale (20)
2. Using wrong body type (must be b2_dynamicBody)
3. Skipping head stabilization torque
4. Wrong motor directions or speeds
5. Not handling both collision fixture orderings
6. Variable timestep instead of fixed 0.04s

## Testing Strategy

### Unit Tests
- Body creation with correct properties
- Joint creation with correct anchors
- Collision filter verification
- Motor speed application

### Integration Tests
- Initial pose stability (should balance briefly)
- Q key moves right thigh forward
- Fall detection when head hits ground
- Score increases with forward movement
- Camera follows player

### Validation Against Original
- Run both versions side-by-side
- Apply same inputs at same times
- Compare torso position over time
- Physics should match within floating-point precision

## File Structure

```
qwop-python/
├── src/
│   ├── __init__.py
│   ├── data.py           # All constants and configurations
│   ├── physics.py        # Box2D world, bodies, joints
│   ├── collision.py      # Contact listener
│   ├── controls.py       # Input to motor mapping
│   ├── game.py           # Update loop, state, camera
│   ├── renderer.py       # Pygame rendering
│   └── play.py           # Interactive gameplay
├── docs/                 # 17 documentation files (complete)
├── legacy/               # Original QWOP files + extracted reference assets
├── requirements.txt
```

## Estimated Implementation Time

- **Phase 1**: 30 minutes (environment setup)
- **Phase 2**: 1 hour (data module from docs)
- **Phase 3**: 3 hours (physics system - most complex)
- **Phase 4**: 1 hour (collision detection)
- **Phase 5**: 1 hour (controls)
- **Phase 6**: 2 hours (game logic and update loop)
- **Phase 7**: 1 hour (renderer)
- **Phase 8**: 30 minutes (main integration)
- **Testing**: 2-3 hours (validation and tuning)

**Total**: 12-14 hours for complete 1:1 recreation

## Success Criteria

The Python version is 1:1 accurate when:
- [ ] Initial pose matches original QWOP
- [ ] Controls respond identically (Q/W/O/P)
- [ ] Physics behavior is indistinguishable
- [ ] Fall detection triggers at same moments
- [ ] Score progression matches frame-by-frame
- [ ] Runner can complete the same runs with same inputs

## Next Steps

1. Review this plan
2. Confirm approach
3. Begin Phase 1 (environment setup)
4. Implement phases sequentially
5. Test continuously against original
