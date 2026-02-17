# QWOP Game Logic

## Game State Flags (line 436)
```javascript
gameOver = false
gameEnded = false
jumped = false
jumpLanded = false
fallen = false
pause = false
helpUp = false
```

## Main Functions

### create_world() - line 530
- Creates background sprites
- Sets up floor/track (multiple segments)
- Creates world boundaries
- Initializes camera

### create_player() - line 1033
- Calls create_hurdle()
- Creates all 12 body parts with physics
- Sets up 11 joints connecting body parts
- Initializes starting pose

### create_hurdle() - line 998
- Creates hurdle at position 10000
- Two parts: base and top
- Connected with revolute joint
- Can tip over when hit

### reset() - line 848
- Destroys all joints
- Destroys all body parts
- Resets score and timer
- Calls create_player()
- Resets camera position

### update(dt) - line 857
Main game loop:
1. Update score time
2. Handle accelerometer (mobile)
3. Update floor sprite positions
4. Apply control inputs (Q/W/O/P)
5. Step physics simulation (0.04s, 5 vel iter, 5 pos iter)
6. Update camera to follow player
7. Check win/lose conditions
8. Update shader lighting

### connect_input() - line 956
Binds keyboard keys:
- Q, W, O, P for controls
- R for reset
- Space for restart after game over

## Win/Lose Conditions (line 926)

### Jump Detection
- `jumped = true` when x position > 19780 (sandPitAt - 220)
- `jumpLanded = true` when foot touches ground after sandPitAt

### Fall Detection
- Checks if head or torso touches ground
- Sets `fallen = true`
- Triggers game over

### Scoring
- Score = player x position / 10 (in meters)
- Best score saved in localStorage
- Time tracked in seconds

## Collision Detection (line 918+)
Uses Box2D contact callbacks:
- `beginContact()` - detects foot-ground contact
- Checks userData to identify body parts
- Different behavior for "leftFoot", "rightFoot", "head", "torso"

## Camera System (line 907)
- Follows torso x position
- Offset adjustable
- Y position follows when player jumps
- Bounds: (-1200, -800) to (levelSize+800, 1600)
