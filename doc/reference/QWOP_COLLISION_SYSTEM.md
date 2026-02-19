# QWOP Collision System - Complete Specification

## Collision Shape System

### Box2D Polygon Shapes
All body parts use rectangular collision boxes:
```javascript
// Line 77-78
shape = new B2PolygonShape()
shape.setAsBox(
  0.5 * sprite.size.x / worldScale,  // Half-width
  0.5 * sprite.size.y / worldScale   // Half-height
)
```

**Key Point**: Box2D uses half-widths/heights, and dimensions are divided by worldScale (20)

### Shape Dimensions
Collision box size = Sprite visual size (from atlas)
- Width: `spriteSourceSize.w / worldScale`
- Height: `spriteSourceSize.h / worldScale`
- Center: Sprite center (centered: true)

## Collision Filtering System

### Category Bits (What am I?)
```javascript
1 (0b00001) = Track/Ground
2 (0b00010) = Player body parts
4 (0b00100) = Hurdle
```

### Mask Bits (What do I collide with?)
```javascript
65535 (0b1111111111111111) = Everything
65533 (0b1111111111101101) = Everything except category 2 (no self-collision between body parts)
65531 (0b1111111111101011) = Everything except categories 2 and 4
65529 (0b1111111111101001) = Everything except categories 2, 4, and others
```

### Complete Collision Matrix

| Object | Category | Mask | Collides With |
|--------|----------|------|---------------|
| Track/Floor | 1 | 65535 | Everything |
| All Body Parts | 2 | 65533 | Track (1), Hurdle (4) |
| Hurdle Base | 4 | 65529 | Track (1) |
| Hurdle Top | 4 | 65531 | Track (1), Player (2) |

### Body Part Collision Properties (Lines 1050-1171)

**Standard Body Parts** (torso, head, arms, legs, calves):
```javascript
categoryBits: 2
maskBits: 65533
friction: 0.2
restitution: 0
density: densityFactor (1.0)
```

**Feet** (special properties):
```javascript
categoryBits: 2
maskBits: 65533
friction: 1.5          // Higher friction for grip
restitution: 0
density: 3 * densityFactor  // 3x heavier
isBullet: false        // Continuous collision detection OFF
```

**Track/Floor** (Line 573):
```javascript
categoryBits: 1
maskBits: 65535
friction: 0.2
restitution: 0
density: 30
userData: "track"
type: 0  // Static body
```

**Hurdle Base** (Line 1013):
```javascript
categoryBits: 4
maskBits: 65529
friction: (default)
restitution: 0
density: densityFactor
userData: "hurdleBase"
isAwake: false
```

**Hurdle Top** (Line 1026):
```javascript
categoryBits: 4
maskBits: 65531
friction: (default)
restitution: 0
density: densityFactor
userData: "hurdleTop"
isAwake: false
```

## Collision Detection Callbacks

### Contact Listener Setup (Lines 1185-1195)
```javascript
ContactListener extends B2ContactListener {
  beginContact(contact) {
    this.main.beginContact(contact)
  }
  endContact(contact) {
    this.main.endContact(contact)
  }
}
```

### beginContact() Function (Lines 912-954)

**Signature**:
```javascript
beginContact(contact)
```

**Process**:
1. Get fixtures from contact
2. Get bodies from fixtures
3. Get userData (body part names) from bodies
4. Get world manifold (collision points)
5. Find rightmost collision point
6. Check body part combinations
7. Trigger game events

**Complete Logic**:

```javascript
// Line 912-954
beginContact: function(contact) {
  // Get collision data
  fixtureA = contact.getFixtureA()
  fixtureB = contact.getFixtureB()
  bodyA = fixtureA.getBody()
  bodyB = fixtureB.getBody()
  userDataA = bodyA.getUserData()
  userDataB = bodyB.getUserData()
  
  // Get collision points
  worldManifold = new B2WorldManifold()
  contact.getWorldManifold(worldManifold)
  points = worldManifold.m_points
  
  // Find rightmost point (for distance tracking)
  maxX = -100000
  for each point in points:
    if point.x > maxX:
      maxX = point.x
  
  contactY = points[0].y
  
  // Check collision combinations
  
  // FEET + TRACK collision
  if (userDataA == "leftFoot" OR userDataA == "rightFoot") AND
     (userDataB == "track"):
    
    if gameOver == false AND fallen == false:
      
      // Jump detection (approaching sand pit)
      if jumped == false AND maxX * worldScale > (sandPitAt - 220):
        jumped = true
      
      // Jump landing detection
      if jumped == true AND jumpLanded == false:
        if maxX * worldScale > sandPitAt:
          jumpLanded = true
          // Show burst effect
          burst.alpha = 1
          burst.size = (20, 20)
          burst.pos = (maxX * worldScale, contactY * worldScale)
          // Animate burst
          tween burst.size to (40, 40) over 0.08s
          then tween to (0, 0) over 0.8s
          
          // Update score
          score = round(maxX) / 10
          if score > highScore:
            highScore = score
  
  // UPPER BODY + TRACK collision (FALL)
  else if (userDataA == "rightForearm" OR
           userDataA == "leftForearm" OR
           userDataA == "rightArm" OR
           userDataA == "leftArm" OR
           userDataA == "head") AND
          (userDataB == "track") AND
          fallen == false:
    
    fallen = true
    
    // Calculate impact velocity
    velocityA = bodyA.getLinearVelocity()
    velocityB = bodyB.getLinearVelocity()
    relativeVelocity = velocityA - velocityB
    impactSpeed = relativeVelocity.length()
    
    // Play sound based on impact
    if impactSpeed > 5:
      play("crunch")  // Hard impact
    else:
      play("ehh")     // Soft impact
    
    // Show burst effect
    burst.alpha = 1
    burst.size = (20, 20)
    burst.pos = (maxX * worldScale, contactY * worldScale)
    tween burst.size to (80, 80) over 0.15s
    then tween to (0, 0) over 0.8s
    
    // Mark jump as landed if in air
    if jumped == true AND jumpLanded == false:
      jumpLanded = true
    
    // Update score
    score = round(maxX) / 10
    if score > highScore:
      highScore = score
}
```

### endContact() Function (Line 955)
```javascript
endContact: function() {}
```
**Note**: Empty - no logic on contact end

## Collision Detection Flow

```
1. Box2D Physics Step
   ↓
2. Collision Detection Phase
   ↓
3. For each new contact:
   → Call beginContact(contact)
   ↓
4. Extract collision data:
   - Body A userData
   - Body B userData
   - Contact points
   - Contact position
   ↓
5. Check userData combinations:
   - Feet + Track → Jump/Landing logic
   - Upper body + Track → Fall logic
   ↓
6. Update game state:
   - Set flags (jumped, fallen, jumpLanded)
   - Update score
   - Play sounds
   - Show visual effects
```

## Critical Collision Rules

### 1. Foot-Ground Contact
- **Purpose**: Normal running, jump detection, landing detection
- **Bodies**: leftFoot/rightFoot + track
- **Effects**:
  - Triggers jump flag at sandPitAt - 220
  - Triggers landing flag at sandPitAt
  - Updates score continuously

### 2. Upper Body-Ground Contact
- **Purpose**: Fall detection (game over)
- **Bodies**: head/arms/forearms + track
- **Effects**:
  - Sets fallen = true (game over)
  - Plays impact sound (crunch or ehh)
  - Shows burst effect
  - Finalizes score

### 3. Body Part Self-Collision
- **Prevented**: maskBits excludes categoryBits 2
- **Reason**: Body parts don't collide with each other
- **Implementation**: Joints connect them instead

### 4. Hurdle Collision
- **Hurdle Base**: Only collides with ground (static)
- **Hurdle Top**: Collides with ground and player
- **Effect**: Can tip over when hit

## UserData Tags

All bodies have userData strings for identification:

**Player Body Parts**:
- "torso"
- "head"
- "leftArm", "rightArm"
- "leftForearm", "rightForearm"
- "leftThigh", "rightThigh"
- "leftCalf", "rightCalf"
- "leftFoot", "rightFoot"

**Environment**:
- "track" - Ground/floor
- "hurdleBase" - Hurdle bottom
- "hurdleTop" - Hurdle top bar

## Collision Shape Details

### Box Creation (Lines 77-80)
```javascript
// Create polygon shape
shape = new B2PolygonShape()
shape.setAsBox(halfWidth, halfHeight)

// Create fixture definition
fixtureDef = new B2FixtureDef()
fixtureDef.shape = shape
fixtureDef.density = density
fixtureDef.friction = friction
fixtureDef.restitution = restitution
fixtureDef.filter.categoryBits = categoryBits
fixtureDef.filter.maskBits = maskBits

// Create body and attach fixture
body = world.createBody(bodyDef)
body.createFixture(fixtureDef)
body.setUserData(userData)
```

## Physics Material Properties

### Friction Values
- **Body parts**: 0.2 (low friction, slides easily)
- **Feet**: 1.5 (high friction, grips ground)
- **Track**: 0.2 (smooth surface)

### Restitution (Bounciness)
- **All objects**: 0 (no bounce)

### Density
- **Body parts**: 1.0 * densityFactor
- **Feet**: 3.0 * densityFactor (heavier for stability)
- **Track**: 30 (very heavy, static)

## For 1:1 Recreation

### Required Components

1. **Box2D World Setup**:
   ```python
   world = b2World(gravity=(0, 10))
   contactListener = CustomContactListener()
   world.contactListener = contactListener
   ```

2. **Body Creation**:
   ```python
   # For each body part:
   bodyDef = b2BodyDef()
   bodyDef.type = b2_dynamicBody
   bodyDef.position = (x / worldScale, y / worldScale)
   bodyDef.angle = angle
   
   body = world.CreateBody(bodyDef)
   
   shape = b2PolygonShape()
   shape.SetAsBox(width / 2 / worldScale, height / 2 / worldScale)
   
   fixtureDef = b2FixtureDef()
   fixtureDef.shape = shape
   fixtureDef.density = density
   fixtureDef.friction = friction
   fixtureDef.restitution = 0
   fixtureDef.filter.categoryBits = categoryBits
   fixtureDef.filter.maskBits = maskBits
   
   body.CreateFixture(fixtureDef)
   body.userData = "bodyPartName"
   ```

3. **Contact Listener**:
   ```python
   class QWOPContactListener(b2ContactListener):
       def BeginContact(self, contact):
           fixtureA = contact.fixtureA
           fixtureB = contact.fixtureB
           bodyA = fixtureA.body
           bodyB = fixtureB.body
           userDataA = bodyA.userData
           userDataB = bodyB.userData
           
           # Implement collision logic here
           if userDataA in ["leftFoot", "rightFoot"] and userDataB == "track":
               # Handle foot-ground contact
               pass
           elif userDataA in ["head", "leftArm", "rightArm", "leftForearm", "rightForearm"] and userDataB == "track":
               # Handle fall
               pass
   ```

4. **Collision Filtering**:
   ```python
   CATEGORY_GROUND = 0x0001
   CATEGORY_PLAYER = 0x0002
   CATEGORY_HURDLE = 0x0004
   
   MASK_ALL = 0xFFFF
   MASK_NO_PLAYER = 0xFFFD  # Everything except player
   ```

## Summary

The collision system is:
- **Simple**: Only 3 collision categories
- **Efficient**: Body parts don't self-collide
- **Precise**: Uses userData for identification
- **Event-driven**: Callbacks trigger game logic
- **Complete**: All data extracted for 1:1 recreation

The skeleton is fully documented with exact collision shapes, filters, and callback logic.
