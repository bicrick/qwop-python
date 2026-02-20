# QWOP Complete Data Reference - All Values for 1:1 Recreation

**Python/JS parity:** The qwop-python codebase keeps body positions, TRACK_Y, camera init/offset, and ground segment formula in sync with QWOP.min.js (create_player, create_world, reset, update). Run `python -m qwop_python.tools.verify_spawn_layout` to verify spawn and layout match 1:1.

## Table of Contents
1. [Physics World Setup](#physics-world-setup)
2. [Camera Configuration](#camera-configuration)
3. [Game State Variables](#game-state-variables)
4. [Timing & Frame Rate](#timing--frame-rate)
5. [Audio System](#audio-system)
6. [Collision Categories](#collision-categories)
7. [Hurdle Configuration](#hurdle-configuration)
8. [Floor/Track Configuration](#floortrack-configuration)
9. [Complete Variable Initialization](#complete-variable-initialization)

## Physics World Setup

### World Creation (line 461)
```javascript
gravity = new B2Vec2(0, 10)  // Downward gravity
m_world = new B2World(gravity, true)  // allowSleep = true
```

### Physics Constants
```javascript
worldScale = 20              // Pixels per meter
gravity = 10                 // m/s²
torqueFactor = 1             // Joint torque multiplier
densityFactor = 1            // Body density multiplier
```

## Camera Configuration

### World Camera (line 449)
```javascript
world_camera = new Camera({
    name: "world_camera"
})

// Viewport
viewport = Rectangle(0, 0, 640, 400)  // screenWidth, screenHeight

// Initial position
pos.x = -10 * worldScale  // -200 pixels
pos.y = -200

// Size mode
sizeMode = SizeMode.fit

// Bounds
bounds = Rectangle(
    -1200,                    // left
    -800,                     // top
    800 + levelSize + 93,     // width (21893)
    1600                      // height
)
```

### UI Camera (line 461)
```javascript
ui_camera = new Camera({
    name: "ui_camera"
})

// Viewport
viewport = Rectangle(0, 0, 640, 400)

// Initial position
pos.x = 0
pos.y = 0

// Size mode
sizeMode = SizeMode.fit
```

### Camera Follow Offset
```javascript
world_camera_offset = 0  // Can be adjusted for camera lead/lag
```

## Game State Variables

### Initial State (line 436)
```javascript
gameOver = false
gameEnded = false
jumped = false
jumpLanded = false
fallen = false
pause = false
helpUp = false
mute = false
started = false
firstClick = false  // Set to true when game starts
doneLoading = false  // Set to true after assets load
```

### Score Tracking
```javascript
score = 0              // Current distance in meters
scoreTime = 0          // Time elapsed in seconds
highScore = 0          // Best distance (loaded from localStorage)
```

### Input State
```javascript
QDown = false
WDown = false
ODown = false
PDown = false

QID = 0    // Touch ID for mobile
WID = 0
OID = 0
PID = 0

mouseClicked = ""  // "Q", "W", "O", or "P"
```

### Speed Tracking
```javascript
speedArray = []  // Array of velocity samples (max 30)
```

### Accelerometer (Mobile)
```javascript
accelerometer = Vector(0, 0, 0)
initialAcceleration = Vector(0, 0, 0)
```

## Timing & Frame Rate

### Core Timing (line 436)
```javascript
frame_time = 0.03333333333333333  // 30 FPS (1/30)
update_rate = 0                    // 0 = as fast as possible
render_rate = -1                   // -1 = vsync
```

### Physics Timestep (line 905)
```javascript
physicsTimeStep = 0.04             // 25 FPS physics (1/25)
velocityIterations = 5
positionIterations = 5
```

## Audio System

### Sound Files (line 495)
```javascript
sounds = [
    {id: "assets/Crunch.wav", name: "crunch", is_stream: false},
    {id: "assets/Ehh.wav", name: "ehh", is_stream: false},
    {id: "assets/cof2.wav", name: "music", is_stream: false}
]
```

### Music Volume Control
```javascript
// Formula: (averageSpeed - 2) / 15, clamped to [0, 1]
musicVolume = min(max((averageSpeed - 2) / 15, 0), 1)

// Music loops continuously
audio.loop("music")
audio.volume("music", 0)  // Start muted, increases with speed
```

## Collision Categories

### Category Bits
```javascript
// Player body parts
playerCategory = 2

// Track/ground
trackCategory = 1

// Hurdle
hurdleCategory = 4
```

### Mask Bits (What Collides With What)
```javascript
// Player parts (categoryBits = 2)
playerMaskBits = 65533  // Binary: 1111111111101101
// Collides with: 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
// Does NOT collide with: 1 (prevents some self-collision)

// Hurdle base (categoryBits = 4)
hurdleBaseMaskBits = 65529  // Binary: 1111111111101001
// Collides with: 0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
// Does NOT collide with: 1, 2

// Hurdle top (categoryBits = 4)
hurdleTopMaskBits = 65531  // Binary: 1111111111101011
// Collides with: 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
// Does NOT collide with: 2
```

## Hurdle Configuration

### Hurdle Position (line 1002)
```javascript
hurdleAt = 10000  // 10000 pixels from start
```

### Hurdle Base (line 1000)
```javascript
position = Vector(10000, 175.5)
size = Vector(67, 12)
depth = 6
centered = true

// Physics
categoryBits = 4
maskBits = 65529
isAwake = false
density = densityFactor
userData = "hurdleBase"
```

### Hurdle Top (line 1015)
```javascript
position = Vector(10000 + 17.3, 101.15)  // (10017.3, 101.15)
size = Vector(21.5, 146)
depth = 7
centered = true

// Physics
categoryBits = 4
maskBits = 65531
isAwake = false
density = densityFactor
userData = "hurdleTop"
```

### Hurdle Joint (line 1027)
```javascript
jointType = B2RevoluteJointDef
bodyA = hurdleTop
bodyB = hurdleBase

localAnchorA = (3.6 / worldScale, 74.6 / worldScale)
localAnchorB = (20.9 / worldScale, 0.25 / worldScale)

enableLimit = true
// No angle limits specified - free rotation
```

## Floor/Track Configuration

### Track Properties (line 575)
```javascript
// Multiple floor segments for infinite scrolling
floorSprites = []  // Array of floor segments

// Each segment:
categoryBits = 1
maskBits = 65535  // Collides with everything
friction = 0.2
type = 0  // Static body
restitution = 0
density = densityFactor
userData = "track"

// Position calculation (line 575):
x = i * screenWidth / worldScale  // i = segment index
y = 10.74275
angle = 0
```

### Sand Pit Location
```javascript
sandPitAt = 20000  // 20000 pixels from start
```

### Level Size
```javascript
levelSize = 21000  // Total track length in pixels
```

## Complete Variable Initialization

### From Line 436 (Game Constructor)
```javascript
// Game state
this.gameOver = false
this.gameEnded = false
this.jumped = false
this.jumpLanded = false
this.fallen = false
this.pause = false
this.helpUp = false
this.mute = false

// Timing
m.core.frame_time = 0.03333333333333333
m.core.update_rate = 0
m.core.render_rate = -1

// Input
this.QDown = false
this.WDown = false
this.ODown = false
this.PDown = false
this.QID = 0
this.WID = 0
this.OID = 0
this.PID = 0
this.mouseClicked = ""

// Physics
this.accelerometer = new Vector(0, 0, 0)
this.initialAcceleration = new Vector(0, 0, 0)

// Score
this.score = 0
this.scoreTime = 0
this.speedArray = []

// Flags
this.started = false
this.firstClick = false
this.doneLoading = false
```

## Asset Files Referenced

### Textures
```javascript
"assets/playercolor.png"      // Player sprite atlas
"assets/playercolor.json"     // Player sprite data
"assets/UISprites.png"        // UI sprite atlas
"assets/UISprites.json"       // UI sprite data
"assets/sprintbg.jpg"         // Background image
"assets/sky.png"              // Sky image
"assets/playerbump.jpg"       // Normal map for player
"assets/skingradient.png"     // Skin color gradient
"assets/bodygradient.png"     // Body color gradient
```

### Shaders
```javascript
"bevelShaderBody"
"bevelShaderHead"
"bevelShaderLeftArm"
"bevelShaderRightArm"
"bevelShaderLeftForearm"
"bevelShaderRightForearm"
"bevelShaderLeftThigh"
"bevelShaderRightThigh"
"bevelShaderLeftCalf"
"bevelShaderRightCalf"
"skyShader"
```

### Fonts
```javascript
"assets/font/mundo36.fnt"
"assets/font/mundo18.fnt"
```

## Screen Dimensions
```javascript
screenWidth = 640
screenHeight = 400
```

## Notes for 1:1 Recreation

1. **All pixel values** must be divided by worldScale (20) for Box2D
2. **Collision categories** are bit flags - use bitwise operations
3. **Floor segments** reposition dynamically for infinite scrolling
4. **Hurdle** is optional - can be disabled for practice
5. **Asset files** are not strictly necessary - can use colored rectangles
6. **Shaders** are for visual effects only - not gameplay critical
7. **Frame rate** (30 FPS) is separate from physics rate (25 FPS)
8. **Camera bounds** prevent scrolling past level edges
9. **Touch IDs** (QID, WID, etc.) are for mobile multi-touch support
10. **localStorage** is used to persist high score between sessions
