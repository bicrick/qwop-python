# QWOP Sprite Data - Complete Code Extraction

## Summary

This document contains ALL sprite-related data extractable from QWOP.js code.
The actual sprite dimensions and UV coordinates are in the atlas JSON files (playercolor.json, UISprites.json) which are embedded in the compressed assetbundle.parcel file.

## Complete Sprite Configuration Data

### Body Part Sprites (12 total)

#### 1. Torso (Frame 0)
```javascript
Line: 1037-1046
name: "torso"
frameIndex: 0
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 6
centered: true
shader: bevelShaderBody
texture: atlasImage (playercolor.png)
```

#### 2. Head (Frame 1)
```javascript
Line: 1052-1061
name: "head"
frameIndex: 1
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 7
centered: true
shader: bevelShaderHead
texture: atlasImage (playercolor.png)
```

#### 3. Left Forearm (Frame 2)
```javascript
Line: 1063-1072
name: "leftForearm"
frameIndex: 2
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 5
centered: true
shader: bevelShaderLeftForearm
texture: atlasImage (playercolor.png)
```

#### 4. Left Thigh (Frame 3)
```javascript
Line: 1074-1083
name: "leftThigh"
frameIndex: 3
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 3
centered: true
shader: bevelShaderLeftThigh
texture: atlasImage (playercolor.png)
```

#### 5. Left Arm (Frame 4)
```javascript
Line: 1085-1094
name: "leftArm"
frameIndex: 4
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 4
centered: true
shader: bevelShaderLeftArm
texture: atlasImage (playercolor.png)
```

#### 6. Left Calf (Frame 5)
```javascript
Line: 1096-1105
name: "leftCalf"
frameIndex: 5
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 1
centered: true
shader: bevelShaderLeftCalf
texture: atlasImage (playercolor.png)
```

#### 7. Left Foot (Frame 6)
```javascript
Line: 1107-1115
name: "leftFoot"
frameIndex: 6
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 2
centered: true
shader: NONE
texture: atlasImage (playercolor.png)
```

#### 8. Right Forearm (Frame 7)
```javascript
Line: 1118-1126
name: "rightForearm"
frameIndex: 7
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 12
centered: true
shader: bevelShaderRightForearm
texture: atlasImage (playercolor.png)
```

#### 9. Right Arm (Frame 8)
```javascript
Line: 1129-1137
name: "rightArm"
frameIndex: 8
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 8
centered: true
shader: bevelShaderRightArm
texture: atlasImage (playercolor.png)
```

#### 10. Right Calf (Frame 9)
```javascript
Line: 1140-1148
name: "rightCalf"
frameIndex: 9
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 9
centered: true
shader: bevelShaderRightCalf
texture: atlasImage (playercolor.png)
```

#### 11. Right Foot (Frame 10)
```javascript
Line: 1151-1158
name: "rightFoot"
frameIndex: 10
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 11
centered: true
shader: NONE
texture: atlasImage (playercolor.png)
```

#### 12. Right Thigh (Frame 11)
```javascript
Line: 1161-1169
name: "rightThigh"
frameIndex: 11
size: Vector(spriteSourceSize.w, spriteSourceSize.h)
uv: frame.uv
batcher: world_batcher
depth: 10
centered: true
shader: bevelShaderRightThigh
texture: atlasImage (playercolor.png)
```

## Shader Configuration (Line 522-526)

### Shader Assignments
```javascript
bevelShaderBody -> torso
bevelShaderHead -> head
bevelShaderLeftArm -> leftArm
bevelShaderRightArm -> rightArm
bevelShaderLeftForearm -> leftForearm
bevelShaderRightForearm -> rightForearm
bevelShaderLeftThigh -> leftThigh
bevelShaderRightThigh -> rightThigh
bevelShaderLeftCalf -> leftCalf
bevelShaderRightCalf -> rightCalf
```

### Shader Textures (Line 526)
```javascript
// Texture slot 1 - Bump map (all body parts)
playerbump.jpg -> tex1

// Texture slot 2 - Gradient
bodygradient.png -> tex2 (torso only)
skingradient.png -> tex2 (all limbs)

// Texture settings
clamp_s: 33071 (CLAMP_TO_EDGE)
clamp_t: 33071 (CLAMP_TO_EDGE)
```

### Dynamic Shader Parameters (Line 910)
Updated every frame:
```javascript
lightVec = Vector(±cos(angle - 1), sin(angle - 1))

// Sign pattern:
torso: -cos, +sin
head: +cos, +sin
rightArm: +cos, +sin
leftArm: +cos, +sin
rightForearm: +cos, +sin
leftForearm: +cos, +sin
rightThigh: +cos, +sin
leftThigh: +cos, +sin
rightCalf: +cos, +sin
leftCalf: +cos, +sin
```

## Rendering Pipeline

### Batcher Layers
```javascript
bg_batcher: layer -2 (background)
world_batcher: layer 0 (game objects)
ui_batcher: layer 2 (UI)
```

### Depth Sorting (within world_batcher)
```
-11: Sky
-10: Background, floor
-2: Sand pit
-1: Crowd
1: Left calf
2: Left foot
3: Left thigh
4: Left arm
5: Left forearm
6: Torso
7: Head
8: Right arm
9: Right calf
10: Right thigh
11: Right foot
12: Right forearm
```

## Atlas Loading (Line 526)

```javascript
player_atlas_json = cache.get("assets/playercolor.json").asset.json
ui_atlas_json = cache.get("assets/UISprites.json").asset.json
atlasImage = cache.get("assets/playercolor.png")
uiAtlasImage = cache.get("assets/UISprites.png")

// Parse atlas
playerData = TexturePackerJSON.parse(player_atlas_json)
uiData = TexturePackerJSON.parse(ui_atlas_json)

// Access frames
frame = playerData.frames[index]
```

## TexturePacker Format (Lines 7920-8010)

### Frame Structure
```javascript
{
  frame: {x, y, w, h},              // Position in atlas texture
  spriteSourceSize: {x, y, w, h},   // Trimmed sprite bounds
  sourceSize: {w, h},               // Original untrimmed size
  rotated: boolean,
  trimmed: boolean,
  uv: Rectangle                     // Calculated UV coordinates
}
```

### Meta Structure
```javascript
{
  app: string,
  version: string,
  image: string,
  format: string,
  size: {w, h},
  scale: number
}
```

## Sprite Creation Pattern

```javascript
// 1. Get frame data from atlas
e = playerData.frames[frameIndex]

// 2. Create sprite
sprite = new Sprite({
  name: "bodyPartName",
  size: new Vector(e.spriteSourceSize.w, e.spriteSourceSize.h),
  uv: e.uv,
  batcher: world_batcher,
  depth: depthValue,
  centered: true,
  shader: shaderInstance,
  texture: atlasImage
})

// 3. Add physics component
physicsBody = new Box({name: "physicsBody"})
physicsBody.world = m_world
physicsBody.categoryBits = 2
physicsBody.maskBits = 65533
physicsBody.friction = 0.2
physicsBody.restitution = 0
physicsBody.density = densityFactor
physicsBody.userData = "bodyPartName"
sprite.add(physicsBody)

// 4. Set initial transform
body = sprite._components.get("physicsBody", false)
body.setPosition(x, y)
body.setAngle(angle)
```

## For 1:1 Recreation

### Required Assets
1. **playercolor.png** - Body part sprites atlas
2. **playercolor.json** - Atlas metadata with frame positions/sizes
3. **UISprites.png** - UI elements atlas
4. **UISprites.json** - UI atlas metadata
5. **playerbump.jpg** - Bump/normal map for 3D effect
6. **skingradient.png** - Skin color gradient
7. **bodygradient.png** - Torso color gradient

### Asset Extraction Options
1. Extract from assetbundle.parcel (compressed, requires custom parser)
2. Intercept from browser when game loads
3. Recreate sprites based on visual reference
4. Use simpler flat-colored sprites without shaders

### Simplification for Python
- Can skip shader system and use pre-rendered sprites
- Can use single texture atlas without gradients
- Depth sorting can be done with simple z-order
- UV coordinates can be calculated from sprite positions in atlas

## Next Steps for Complete Data

To get exact pixel dimensions:
1. Extract atlas JSON files from parcel
2. Or measure sprites directly from PNG files
3. Or run game in browser and capture atlas data from memory
4. Or recreate based on physics body dimensions (approximate)
