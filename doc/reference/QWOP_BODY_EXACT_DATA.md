# QWOP Body Parts - Exact Initial Data for 1:1 Recreation

## Body Part Initial Positions & Angles

All positions are in Box2D world units (meters). All angles are in radians.

### 1. TORSO
```
Initial Position: (2.5111726226000157, -1.8709517533957938)
Initial Angle: -1.2514497119301329 rad (-71.70°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "torso"

Sprite Properties:
- depth: 6
- centered: true
- shader: bevelShaderBody
- frames index: 0
```

### 2. HEAD
```
Initial Position: (3.888130278719558, -5.621802929095265)
Initial Angle: 0.06448415835225099 rad (3.69°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "head"

Sprite Properties:
- depth: 7
- centered: true
- shader: bevelShaderHead
- frames index: 1
```

### 3. LEFT FOREARM
```
Initial Position: (5.830008603424893, -2.8733539631159584)
Initial Angle: -1.2049772618421237 rad (-69.04°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "leftForearm"

Sprite Properties:
- depth: 5
- centered: true
- shader: bevelShaderLeftForearm
- frames index: 2
```

### 4. LEFT THIGH
```
Initial Position: (2.5648987628203876, 1.648090668682522)
Initial Angle: -2.0177234426823394 rad (-115.59°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "leftThigh"

Sprite Properties:
- depth: 3
- centered: true
- shader: bevelShaderLeftThigh
- frames index: 3
```

### 5. LEFT ARM
```
Initial Position: (4.417861014480877, -2.806563606410589)
Initial Angle: 0.9040095895272826 rad (51.80°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "leftArm"

Sprite Properties:
- depth: 4
- centered: true
- shader: bevelShaderLeftArm
- frames index: 4
```

### 6. LEFT CALF
```
Initial Position: (3.12585731974087, 5.525511655361298)
Initial Angle: -1.5903971528225265 rad (-91.11°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "leftCalf"

Sprite Properties:
- depth: 1
- centered: true
- shader: bevelShaderLeftCalf
- frames index: 5
```

### 7. LEFT FOOT
```
Initial Position: (3.926921842806667, 8.08884032049622)
Initial Angle: 0.12027524643408766 rad (6.89°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 1.5 ⚠️ HIGHER THAN OTHER PARTS
- restitution: 0
- density: 3.0 * densityFactor ⚠️ 3X HEAVIER
- isBullet: false
- userData: "leftFoot"

Sprite Properties:
- depth: 2
- centered: true
- shader: NONE (no shader)
- frames index: 6
```

### 8. RIGHT FOREARM
```
Initial Position: (0.4078206420797428, -1.0599953233084172)
Initial Angle: -1.7553358283857299 rad (-100.57°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "rightForearm"

Sprite Properties:
- depth: 12
- centered: true
- shader: bevelShaderRightForearm
- frames index: 7
```

### 9. RIGHT ARM
```
Initial Position: (1.1812303663272852, -3.5000256518601014)
Initial Angle: -0.5222217404634386 rad (-29.92°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "rightArm"

Sprite Properties:
- depth: 8
- centered: true
- shader: bevelShaderRightArm
- frames index: 8
```

### 10. RIGHT CALF
```
Initial Position: (-0.07253905736790486, 5.347881871063159)
Initial Angle: -0.7588859967104447 rad (-43.48°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "rightCalf"

Sprite Properties:
- depth: 9
- centered: true
- shader: bevelShaderRightCalf
- frames index: 9
```

### 11. RIGHT FOOT
```
Initial Position: (-1.1254742643908706, 7.567193169625567)
Initial Angle: 0.5897605418219602 rad (33.79°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 1.5 ⚠️ HIGHER THAN OTHER PARTS
- restitution: 0
- density: 3.0 * densityFactor ⚠️ 3X HEAVIER
- isBullet: false
- userData: "rightFoot"

Sprite Properties:
- depth: 11
- centered: true
- shader: NONE (no shader)
- frames index: 10
```

### 12. RIGHT THIGH
```
Initial Position: (1.6120186135678773, 2.0615320561881516)
Initial Angle: 1.4849422964528027 rad (85.08°)

Physics Properties:
- categoryBits: 2
- maskBits: 65533
- friction: 0.2
- restitution: 0
- density: 1.0 * densityFactor
- userData: "rightThigh"

Sprite Properties:
- depth: 10
- centered: true
- shader: bevelShaderRightThigh
- frames index: 11
```

## Collision Filter Explanation

### categoryBits = 2
This body belongs to collision category 2 (player body parts).

### maskBits = 65533
Binary: 1111111111101101
This means the body collides with categories: 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
Does NOT collide with category 1 (likely other player parts to prevent self-collision issues).

## Rendering Depth Order (back to front)

```
-2: Background batcher
-1: (none)
 0: World batcher (default)
 1: leftCalf
 2: leftFoot
 3: leftThigh
 4: leftArm
 5: leftForearm
 6: torso
 7: head
 8: rightArm
 9: rightCalf
10: rightThigh
11: rightFoot
12: rightForearm
 2: UI batcher
```

Left side parts render in front of torso, right side parts render behind.

## Special Properties

### Feet (both left and right)
- **3x heavier** (density = 3.0 * densityFactor)
- **Higher friction** (1.5 vs 0.2)
- **No shader** (rendered flat, not beveled)
- **isBullet = false** (explicitly set, though default is false)

These properties make the feet:
1. Grip the ground better (high friction)
2. Provide stability (heavy)
3. Look different visually (no bevel shader)

## Physics Body Shape

All bodies use **Box2D PolygonShape** (rectangular collision boxes).
The exact dimensions come from sprite sizes (see Box class, line 78):
```javascript
e.setAsBox(
    0.5 * this.sprite.size.x / l.worldScale,
    0.5 * this.sprite.size.y / l.worldScale
)
```

Width and height are derived from sprite.size divided by worldScale (20).
Sprite sizes come from the texture atlas (playercolor.json frames).

## Notes for 1:1 Recreation

1. **Position precision**: Use all decimal places for exact initial pose
2. **Angle precision**: Critical for joint reference angles to work correctly
3. **Feet are special**: Don't forget 3x density and 1.5 friction
4. **Depth ordering**: Important for visual correctness (left limbs in front)
5. **Centered sprites**: All sprites are centered on their physics body
6. **Collision filters**: categoryBits=2, maskBits=65533 for all player parts
