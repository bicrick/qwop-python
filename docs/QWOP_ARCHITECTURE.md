# QWOP Code Architecture

## Framework Stack

### Luxe Engine (variable `o`)
- Game engine framework
- Component system (ID, Component base classes)
- Sprite rendering
- Scene management
- Camera system
- Input handling
- Audio system

### Box2D Physics (variable `p`)
- `p.dynamics` - Bodies, joints, world
- `p.collision` - Shapes, collision detection
- `p.common.math` - Vector math (B2Vec2)
- Revolute joints for all limb connections
- Contact listeners for collision callbacks

### Phoenix Graphics (variable `I`)
- `I.Vector` - 2D/3D vectors
- `I.Batcher` - Sprite batching
- `I.Shader` - Custom shaders (bevel shading for body parts)
- `I.Renderer` - Rendering pipeline
- `I.Transform` - Position/rotation/scale
- `I.Texture` - Texture management

### Snow Engine (variable `C`)
- `C.system` - Window, input, audio
- `C.core` - App lifecycle
- `C.api` - Promises, timers
- Web platform integration

## Main Game Class (variable `d`, line 436+)

Key properties:
- `m_world` - Box2D physics world
- Body part sprites: torso, head, leftArm, rightArm, etc.
- Joints: neck, leftHip, rightHip, leftKnee, rightKnee, etc.
- Cameras: world_camera, ui_camera
- Input state: QDown, WDown, ODown, PDown

Key methods:
- `create_world()` - Setup environment
- `create_player()` - Build ragdoll
- `create_hurdle()` - Place obstacle
- `update(dt)` - Main game loop
- `reset()` - Restart game
- `beginContact()` - Collision handler

## Component System

All game objects use entity-component pattern:
1. Create Sprite (entity)
2. Add physics Component (Box class)
3. Component has lifecycle: init → onadded → update → onremoved → ondestroy

Example:
```javascript
sprite = new o.Sprite({...})
physicsBody = new r({name: "physicsBody"})
physicsBody.world = this.m_world
sprite.add(physicsBody)
```

## Variable Name Mapping

Key obfuscated variables:
- `l` = Globals (constants)
- `m` = Luxe (main engine instance)
- `o` = Luxe classes
- `p` = Box2D
- `I` = Phoenix
- `C` = Snow
- `d` = Main game class
- `r` = Box physics component
- `t` = utility function (inheritance)
- `e` = iterator function
- `s` = bind function
- `i` = class registry object
- `h` = HxOverrides (utility functions)

## Asset Loading

Uses TexturePacker format:
- `player_atlas_json` - Body part sprites
- `ui_atlas_json` - UI elements
- Shaders for each body part (bevel lighting)
- Audio: music, crunch, ehh sounds

## Rendering Pipeline

1. world_batcher (layer 0) - Game objects
2. ui_batcher (layer 2) - UI elements
3. bg_batcher (layer -2) - Background
4. Custom shaders per body part for 3D-like appearance
5. Camera viewport transforms
