# QWOP Body Part Dimensions - PRECISE DATA

## How Dimensions Work

From line 78 of QWOP.js:
```javascript
e.setAsBox(.5 * this.sprite.size.x / l.worldScale, .5 * this.sprite.size.y / l.worldScale);
```

**Formula:**
- Box2D collision box = `sprite.size / worldScale`
- `setAsBox()` takes **half-widths** (Box2D convention)
- worldScale = 20 (pixels to meters)

## Sprite Size Sources

Sprite dimensions come from `e.spriteSourceSize.w` and `e.spriteSourceSize.h` where `e = t.frames[index]` from the texture atlas JSON file (`assets/playercolor.json`).

The texture atlas is loaded at runtime (line 526):
```javascript
this.player_atlas_json = m.resources.cache.get("assets/playercolor.json").asset.json
```

## Frame Indices (line 1036-1171)

Body parts are loaded from specific frame indices:

| Body Part | Frame Index | Variable |
|-----------|-------------|----------|
| Torso | 0 | t.frames[0] |
| Head | 1 | t.frames[1] |
| Left Forearm | 2 | t.frames[2] |
| Left Thigh | 3 | t.frames[3] |
| Left Arm | 4 | t.frames[4] |
| Left Calf | 5 | t.frames[5] |
| Left Foot | 6 | t.frames[6] |
| Right Forearm | 7 | t.frames[7] |
| Right Arm | 8 | t.frames[8] |
| Right Calf | 9 | t.frames[9] |
| Right Foot | 10 | t.frames[10] |
| Right Thigh | 11 | t.frames[11] |

## Deriving Dimensions from Joint Anchors

Since we don't have the texture atlas JSON, we can estimate dimensions from joint anchor points (line 1173+).

### Method: Calculate from Joint Distances

Each body part connects at two joints. The distance between joint anchors approximates the body part length.

### Neck Joint (Head-Torso connection)
```javascript
// Head anchor: (3.5885141908253755, -4.526224223627244)
// Torso anchor: (3.588733341630704, -4.526434658500262)
// These are nearly identical - head sits directly on torso
```

### Right Shoulder (RightArm-Torso)
```javascript
// RightArm anchor: (2.228476821818547, -4.086468732185028)
// Torso anchor: (2.228929993886102, -4.08707555939957)
```

### Left Shoulder (LeftArm-Torso)
```javascript
// LeftArm anchor: (3.6241979856895377, -3.5334881618011442)
// Torso anchor: (3.6241778782207157, -3.533950434531982)
```

### Left Hip (LeftThigh-Torso)
```javascript
// LeftThigh anchor: (2.0030339754142847, 0.23737160622781284)
// Torso anchor: (2.003367181376716, 0.23802590387419476)
```

### Right Hip (RightThigh-Torso)
```javascript
// RightThigh anchor: (1.2475900729227194, -0.011046642863645761)
// Torso anchor: (1.2470052823973599, -0.011635347168778898)
```

### Left Elbow (LeftForearm-LeftArm)
```javascript
// LeftForearm anchor: (5.525375332758792, -1.63856204930891)
// LeftArm anchor: (5.52537532948459, -1.6385620366077662)
```

### Right Elbow (RightForearm-RightArm)
```javascript
// RightForearm anchor: (-0.006090859076100963, -2.8004758838752157)
// RightArm anchor: (-0.0060908611708438976, -2.8004758929205846)
```

### Left Knee (LeftCalf-LeftThigh)
```javascript
// LeftCalf anchor: (3.384323411985692, 3.5168931240916876)
// LeftThigh anchor: (3.3844684376952108, 3.5174122997898016)
```

### Right Knee (RightCalf-RightThigh)
```javascript
// RightCalf anchor: (1.4982369235492752, 4.175600306005656)
// RightThigh anchor: (1.4982043532615996, 4.17493520671361)
```

### Left Ankle (LeftFoot-LeftCalf)
```javascript
// LeftFoot anchor: (3.312322507818897, 7.947704853895541)
// LeftCalf anchor: (3.3123224825088817, 7.947704836256229)
```

### Right Ankle (RightFoot-RightCalf)
```javascript
// RightFoot anchor: (-1.6562855402197227, 6.961551452557676)
// RightCalf anchor: (-1.655726670462596, 6.961493826969391)
```

## Estimated Dimensions from Body Positions

Using initial body positions (line 1052-1171) and typical human proportions:

### Torso
- Position: (2.511, -1.871)
- Connects: Head (top), Arms (shoulders), Thighs (hips)
- Estimated: ~40-50 pixels wide, ~60-80 pixels tall

### Head
- Position: (3.888, -5.622)
- Distance from torso: ~3.75 units
- Estimated: ~30-40 pixels diameter

### Arms (Upper)
- Left: (4.418, -2.807)
- Right: (1.181, -3.500)
- Estimated: ~15-20 pixels wide, ~40-50 pixels long

### Forearms
- Left: (5.830, -2.873)
- Right: (0.408, -1.060)
- Estimated: ~12-18 pixels wide, ~35-45 pixels long

### Thighs
- Left: (2.565, 1.648)
- Right: (1.612, 2.062)
- Distance from torso to knee: ~3.5 units
- Estimated: ~20-25 pixels wide, ~70-80 pixels long

### Calves
- Left: (3.126, 5.526)
- Right: (-0.073, 5.348)
- Distance from knee to ankle: ~2-2.5 units
- Estimated: ~18-22 pixels wide, ~50-60 pixels long

### Feet
- Left: (3.927, 8.089)
- Right: (-1.125, 7.567)
- Estimated: ~30-40 pixels long, ~15-20 pixels tall

## CRITICAL: Need Actual Texture Atlas

**To get exact 1:1 dimensions, we need:**
1. The `assets/playercolor.json` file (texture atlas metadata)
2. OR extract dimensions by running the game and logging `sprite.size.x` and `sprite.size.y`
3. OR decompile/extract the packed assets from the game

**Recommended approach:** Run QWOP in browser with console logging to capture exact sprite dimensions at runtime.

## Physics Box Creation (Line 73-80)

```javascript
onadded: function() {
    this.sprite = this.get_entity();
    var t = new p.dynamics.B2BodyDef;
    t.type = this.type;
    t.position.set(this.sprite.get_pos().x / l.worldScale, this.sprite.get_pos().y / l.worldScale);
    var e = new p.collision.shapes.B2PolygonShape;
    e.setAsBox(.5 * this.sprite.size.x / l.worldScale, .5 * this.sprite.size.y / l.worldScale);
    var s = new p.dynamics.B2FixtureDef;
    s.shape = e;
    s.density = this.density;
    s.friction = this.friction;
    s.restitution = this.restitution;
    s.filter.categoryBits = this.categoryBits;
    s.filter.maskBits = this.maskBits;
    this.body = this.world.createBody(t);
    this.body.createFixture(s);
}
```

**Key points:**
- Collision box is a rectangle (B2PolygonShape)
- Size = sprite dimensions / 20 (worldScale)
- Centered on body position
- All bodies use same physics properties (except feet have higher friction/density)
