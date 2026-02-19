# QWOP Sprite and Visual Data - Complete Extraction

## Texture Atlas System

QWOP uses TexturePacker format with two atlases:
- **playercolor.json** / **playercolor.png** - Body part sprites (12 frames)
- **UISprites.json** / **UISprites.png** - UI elements (25 frames)

## Player Body Part Sprites

All sprites use:
- `centered: true` - Sprite origin at center
- `batcher: world_batcher` - Rendered in world space
- `texture: atlasImage` - From playercolor.png

### Frame Index Mapping

| Frame Index | Body Part | Variable Name |
|------------|-----------|---------------|
| 0 | Torso | `this.torso` |
| 1 | Head | `this.head` |
| 2 | Left Forearm | `this.leftForearm` |
| 3 | Left Thigh | `this.leftThigh` |
| 4 | Left Arm | `this.leftArm` |
| 5 | Left Calf | `this.leftCalf` |
| 6 | Left Foot | `this.leftFoot` |
| 7 | Right Forearm | `this.rightForearm` |
| 8 | Right Arm | `this.rightArm` |
| 9 | Right Calf | `this.rightCalf` |
| 10 | Right Foot | `this.rightFoot` |
| 11 | Right Thigh | `this.rightThigh` |

## Sprite Properties Per Body Part

### Torso (Frame 0)
```javascript
name: "torso"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 6
centered: true
shader: bevelShaderBody
texture: atlasImage
```

### Head (Frame 1)
```javascript
name: "head"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 7
centered: true
shader: bevelShaderHead
texture: atlasImage
```

### Left Forearm (Frame 2)
```javascript
name: "leftForearm"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 5
centered: true
shader: bevelShaderLeftForearm
texture: atlasImage
```

### Left Thigh (Frame 3)
```javascript
name: "leftThigh"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 3
centered: true
shader: bevelShaderLeftThigh
texture: atlasImage
```

### Left Arm (Frame 4)
```javascript
name: "leftArm"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 4
centered: true
shader: bevelShaderLeftArm
texture: atlasImage
```

### Left Calf (Frame 5)
```javascript
name: "leftCalf"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 1
centered: true
shader: bevelShaderLeftCalf
texture: atlasImage
```

### Left Foot (Frame 6)
```javascript
name: "leftFoot"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 2
centered: true
shader: NONE (no shader)
texture: atlasImage
```

### Right Forearm (Frame 7)
```javascript
name: "rightForearm"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 12
centered: true
shader: bevelShaderRightForearm
texture: atlasImage
```

### Right Arm (Frame 8)
```javascript
name: "rightArm"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 8
centered: true
shader: bevelShaderRightArm
texture: atlasImage
```

### Right Calf (Frame 9)
```javascript
name: "rightCalf"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 9
centered: true
shader: bevelShaderRightCalf
texture: atlasImage
```

### Right Foot (Frame 10)
```javascript
name: "rightFoot"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 11
centered: true
shader: NONE (no shader)
texture: atlasImage
```

### Right Thigh (Frame 11)
```javascript
name: "rightThigh"
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
uv: e.uv
depth: 10
centered: true
shader: bevelShaderRightThigh
texture: atlasImage
```

## Depth/Layer Ordering

Rendering order (back to front):
- -11: Sky
- -10: Background, floor blocks
- -2: Sand pit
- -1: Crowd sprites
- 1: Left calf
- 2: Left foot
- 3: Left thigh
- 4: Left arm
- 5: Left forearm
- 6: Torso
- 7: Head
- 8: Right arm
- 9: Right calf
- 10: Right thigh
- 11: Right foot
- 12: Right forearm
- 2100: UI elements

## Shader System

### Bevel Shaders (3D-like appearance)
Each body part (except feet) has a unique shader instance:
- `bevelShaderBody` - Torso
- `bevelShaderHead` - Head
- `bevelShaderLeftArm` - Left arm
- `bevelShaderRightArm` - Right arm
- `bevelShaderLeftForearm` - Left forearm
- `bevelShaderRightForearm` - Right forearm
- `bevelShaderLeftThigh` - Left thigh
- `bevelShaderRightThigh` - Right thigh
- `bevelShaderLeftCalf` - Left calf
- `bevelShaderRightCalf` - Right calf

### Shader Textures
Each shader uses 2 textures:
- **tex1**: `playerbump.jpg` (slot 1) - Bump/normal map
- **tex2**: 
  - Body: `bodygradient.png` (slot 2)
  - All limbs: `skingradient.png` (slot 2)

### Shader Parameters
- **screenRes**: Vector2(texture.width, texture.height)
- **lightVec**: Dynamic, updated each frame based on body part rotation
  - Calculated as: `new I.Vector(±Math.cos(angle - 1), Math.sin(angle - 1))`
  - Sign varies per body part for lighting direction

### Texture Clamping
```javascript
skingradient.set_clamp_s(33071)  // CLAMP_TO_EDGE
skingradient.set_clamp_t(33071)
bodygradient.set_clamp_s(33071)
bodygradient.set_clamp_t(33071)
```

## UI Sprites (UISprites.json)

### Frame Index Reference
| Frame | UI Element |
|-------|-----------|
| 0 | Floor block |
| 1 | Best score text background |
| 2 | Score text background |
| 3 | "FALLEN" message |
| 4 | Help button |
| 5 | Help overlay |
| 6 | Intro message |
| 7 | Jump ending message |
| 8 | Mute button (unmuted) |
| 9 | Mute button (muted) |
| 10 | O key (unpressed) |
| 11 | O key (pressed) |
| 12 | P key (unpressed) |
| 13 | P key (pressed) |
| 14 | Q key (unpressed) |
| 15 | Q key (pressed) |
| 16 | Sand pit sprite |
| 17 | Sand pit sprite 2 |
| 18 | Current score text |
| 19 | W key (unpressed) |
| 20 | W key (pressed) |
| 21 | Burst particle effect |
| 22 | Hurdle base |
| 23 | Hurdle top |
| 24 | Sand pit sprite 3 |

## TexturePacker JSON Format

The atlas JSON is parsed using `o.importers.texturepacker.TexturePackerJSON.parse()` which extracts:

```javascript
{
  frames: [
    {
      frame: {x, y, w, h},           // Position in atlas
      spriteSourceSize: {x, y, w, h}, // Trimmed sprite bounds
      sourceSize: {w, h},             // Original sprite size
      uv: Rectangle                   // Calculated UV coords
    }
  ],
  meta: {
    size: {w, h},    // Atlas dimensions
    format: string,
    scale: number
  }
}
```

## Sprite Size Calculation

Sprites use `spriteSourceSize.w` and `spriteSourceSize.h` for dimensions:
```javascript
size: new I.Vector(e.spriteSourceSize.w, e.spriteSourceSize.h)
```

This is the trimmed size (transparent pixels removed), not the original size.

## World vs UI Batchers

- **world_batcher** (layer 0): Body parts, hurdles, floor
- **ui_batcher** (layer 2): UI elements, buttons, text
- **bg_batcher** (layer -2): Background, sky

## Special Sprite Properties

### Sand Pit Sprites
```javascript
// Multiple sand pit sprites at different positions
pos: new I.Vector(sandPitAt - 0.5 * width, 155)
size: new I.Vector(0.5 * width, 0.5 * height)  // Half size
```

### Floor Blocks
```javascript
// Tiled across track
size: new I.Vector(spriteSourceSize.w, 0.7 * spriteSourceSize.h)  // 70% height
depth: -10
```

### Background
```javascript
size: new I.Vector(640, 400)
depth: -10
uv: new I.Rectangle(0, 0, 640, 400)
centered: false
```

### Sky
```javascript
pos: new I.Vector(-31 * worldScale, -30 * worldScale)
depth: -11
shader: skyShader
```

## Notes for 1:1 Recreation

1. **Exact sprite dimensions** are stored in the atlas JSON files (playercolor.json, UISprites.json)
2. **UV coordinates** are calculated by TexturePacker and stored in the JSON
3. **Sprite origin** is always centered for body parts (`centered: true`)
4. **Depth sorting** is critical for proper rendering order
5. **Shaders** create the 3D bevel effect - can be replaced with pre-rendered sprites or simpler shading
6. **Dynamic lighting** updates each frame based on body part rotation
7. **Texture slots** allow multiple textures per shader (bump map + gradient)

## Missing Data (Requires Atlas JSON Files)

To get exact pixel dimensions and UV coordinates, need to:
1. Extract `assets/playercolor.json` from `assetbundle.parcel`
2. Extract `assets/UISprites.json` from `assetbundle.parcel`
3. Parse JSON to get exact frame data

Alternative: Measure from PNG files directly if available.
