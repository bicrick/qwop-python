# QWOP Sprite Dimensions - EXACT VALUES (Extracted from Browser)

## Body Part Sprite Dimensions (Pixels)

These are the EXACT sprite dimensions extracted from the running game.

| Frame | Body Part | Width (px) | Height (px) | Box2D Half-Width | Box2D Half-Height |
|-------|-----------|------------|-------------|------------------|-------------------|
| 0 | Torso | 131 | 57 | 3.275 | 1.425 |
| 1 | Head | 43 | 53 | 1.075 | 1.325 |
| 2 | Left Forearm | 70 | 22 | 1.75 | 0.55 |
| 3 | Left Thigh | 101 | 40 | 2.525 | 1.0 |
| 4 | Left Arm | 74 | 25 | 1.85 | 0.625 |
| 5 | Left Calf | 100 | 30 | 2.5 | 0.75 |
| 6 | Left Foot | 54 | 27 | 1.35 | 0.675 |
| 7 | Right Forearm | 89 | 27 | 2.225 | 0.675 |
| 8 | Right Arm | 78 | 30 | 1.95 | 0.75 |
| 9 | Right Calf | 100 | 30 | 2.5 | 0.75 |
| 10 | Right Foot | 54 | 29 | 1.35 | 0.725 |
| 11 | Right Thigh | 106 | 40 | 2.65 | 1.0 |

## Calculation Formula

From QWOP.js line 78:
```javascript
shape.setAsBox(
    0.5 * sprite.size.x / worldScale,
    0.5 * sprite.size.y / worldScale
)
```

Where:
- `sprite.size.x` = `spriteSourceSize.w` (from atlas)
- `sprite.size.y` = `spriteSourceSize.h` (from atlas)
- `worldScale` = 20

**Box2D Half-Width** = width / 2 / 20 = width / 40
**Box2D Half-Height** = height / 2 / 20 = height / 40

## Complete Body Part Data

### Frame 0: TORSO
```
Sprite Size: 131 x 57 pixels
Box2D Shape: setAsBox(3.275, 1.425)
Full Box Size: 6.55 x 2.85 meters
```

### Frame 1: HEAD
```
Sprite Size: 43 x 53 pixels
Box2D Shape: setAsBox(1.075, 1.325)
Full Box Size: 2.15 x 2.65 meters
```

### Frame 2: LEFT FOREARM
```
Sprite Size: 70 x 22 pixels
Box2D Shape: setAsBox(1.75, 0.55)
Full Box Size: 3.5 x 1.1 meters
```

### Frame 3: LEFT THIGH
```
Sprite Size: 101 x 40 pixels
Box2D Shape: setAsBox(2.525, 1.0)
Full Box Size: 5.05 x 2.0 meters
```

### Frame 4: LEFT ARM
```
Sprite Size: 74 x 25 pixels
Box2D Shape: setAsBox(1.85, 0.625)
Full Box Size: 3.7 x 1.25 meters
```

### Frame 5: LEFT CALF
```
Sprite Size: 100 x 30 pixels
Box2D Shape: setAsBox(2.5, 0.75)
Full Box Size: 5.0 x 1.5 meters
```

### Frame 6: LEFT FOOT
```
Sprite Size: 54 x 27 pixels
Box2D Shape: setAsBox(1.35, 0.675)
Full Box Size: 2.7 x 1.35 meters
```

### Frame 7: RIGHT FOREARM
```
Sprite Size: 89 x 27 pixels
Box2D Shape: setAsBox(2.225, 0.675)
Full Box Size: 4.45 x 1.35 meters
```

### Frame 8: RIGHT ARM
```
Sprite Size: 78 x 30 pixels
Box2D Shape: setAsBox(1.95, 0.75)
Full Box Size: 3.9 x 1.5 meters
```

### Frame 9: RIGHT CALF
```
Sprite Size: 100 x 30 pixels
Box2D Shape: setAsBox(2.5, 0.75)
Full Box Size: 5.0 x 1.5 meters
```

### Frame 10: RIGHT FOOT
```
Sprite Size: 54 x 29 pixels
Box2D Shape: setAsBox(1.35, 0.725)
Full Box Size: 2.7 x 1.45 meters
```

### Frame 11: RIGHT THIGH
```
Sprite Size: 106 x 40 pixels
Box2D Shape: setAsBox(2.65, 1.0)
Full Box Size: 5.3 x 2.0 meters
```

## Python Implementation

```python
# Body part dimensions for Box2D shapes
BODY_DIMENSIONS = {
    'torso': {'width': 131, 'height': 57, 'half_w': 3.275, 'half_h': 1.425},
    'head': {'width': 43, 'height': 53, 'half_w': 1.075, 'half_h': 1.325},
    'leftForearm': {'width': 70, 'height': 22, 'half_w': 1.75, 'half_h': 0.55},
    'leftThigh': {'width': 101, 'height': 40, 'half_w': 2.525, 'half_h': 1.0},
    'leftArm': {'width': 74, 'height': 25, 'half_w': 1.85, 'half_h': 0.625},
    'leftCalf': {'width': 100, 'height': 30, 'half_w': 2.5, 'half_h': 0.75},
    'leftFoot': {'width': 54, 'height': 27, 'half_w': 1.35, 'half_h': 0.675},
    'rightForearm': {'width': 89, 'height': 27, 'half_w': 2.225, 'half_h': 0.675},
    'rightArm': {'width': 78, 'height': 30, 'half_w': 1.95, 'half_h': 0.75},
    'rightCalf': {'width': 100, 'height': 30, 'half_w': 2.5, 'half_h': 0.75},
    'rightFoot': {'width': 54, 'height': 29, 'half_w': 1.35, 'half_h': 0.725},
    'rightThigh': {'width': 106, 'height': 40, 'half_w': 2.65, 'half_h': 1.0},
}

# Usage in PyBox2D
shape = b2PolygonShape()
shape.SetAsBox(BODY_DIMENSIONS['torso']['half_w'], BODY_DIMENSIONS['torso']['half_h'])
```

## Notes

1. **Asymmetry**: Left and right limbs have different dimensions
   - Right forearm (89px) is longer than left forearm (70px)
   - Right thigh (106px) is wider than left thigh (101px)
   - This asymmetry is intentional and part of QWOP's difficulty

2. **Feet are identical**: Both feet are 54px wide, but right foot is 2px taller (29 vs 27)

3. **Calves are identical**: Both 100x30 pixels

4. **All dimensions verified**: Extracted directly from running game on 2026-02-16

## Status

✅ **BLOCKER RESOLVED** - All sprite dimensions extracted and documented.

Ready for 1:1 Python implementation.
