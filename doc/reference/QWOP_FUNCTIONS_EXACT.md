# QWOP Functions - Exact Logic for 1:1 Recreation

## update(dt) - Main Game Loop (line 857)

### Function Signature
```javascript
update: function(t)  // t = delta time in seconds
```

### Step-by-Step Logic

#### 1. Score Time Update
```javascript
if (pause == false && gameEnded == false) {
    scoreTime += t
}
```

#### 2. Accelerometer Handling (Mobile)
```javascript
// Initialize accelerometer baseline
if (initialAcceleration.length() == 0 && accelerometer.length() != 0) {
    initialAcceleration = accelerometer
}

// Flip gravity if phone tilted (score < -2.5 meters = going backwards)
if (score < -2.5) {
    if (initialAcceleration.dot(accelerometer) < -0.8) {
        m_world.setGravity(new B2Vec2(0, -gravity))  // Flip gravity upside down
    }
} else if (accelerometer.length() != 0) {
    initialAcceleration = accelerometer
}
```

#### 3. Floor Sprite Repositioning (Infinite Scrolling)
```javascript
if (floorSprites != null) {
    for (i = 0; i < floorSprites.length; i++) {
        floorSprite = floorSprites[i]
        physicsBody = floorSprite.getComponent("physicsBody")
        
        // Calculate new position based on camera
        newX = (floor(world_camera.pos.x / screenWidth) + i) * screenWidth / worldScale
        
        // Only update if position changed
        if (newX != physicsBody.getPosition().x) {
            physicsBody.setPosition(newX, physicsBody.getPosition().y)
        }
    }
}
```

#### 4. Head Stabilization Torque
```javascript
if (rightAnkle != null) {  // Check if player exists
    head = this.head.getComponent("physicsBody")
    
    // Apply counter-torque to keep head upright (only if not fallen)
    if (fallen == false) {
        head.applyTorque(-4 * (head.getAngle() + 0.2))
    }
}
```

#### 5. Speed Tracking & Music Volume
```javascript
// Track head velocity for music volume
headVelocity = head.getLinearVelocity()
speedArray.push(headVelocity.x)

// Keep only last 30 samples
if (speedArray.length > 30) {
    speedArray.shift()  // Remove oldest
}

// Calculate average speed
totalSpeed = 0
for (i = 0; i < speedArray.length; i++) {
    totalSpeed += speedArray[i]
}
averageSpeed = totalSpeed / speedArray.length

// Set music volume based on speed (0 to 1)
volume = min(max((averageSpeed - 2) / 15, 0), 1)
m.audio.volume("music", volume)

if (mute == true) {
    m.audio.volume("music", 0)
}
```

#### 6. Control Input Processing
```javascript
// Q Key - Right thigh forward, left thigh back
if (QDown == true) {
    rightHip.setMotorSpeed(2.5)
    leftHip.setMotorSpeed(-2.5)
    rightShoulder.setMotorSpeed(-2)
    rightElbow.setMotorSpeed(-10)
    leftShoulder.setMotorSpeed(2)
    leftElbow.setMotorSpeed(-10)
}
// W Key - Left thigh forward, right thigh back
else if (WDown == true) {
    rightHip.setMotorSpeed(-2.5)
    leftHip.setMotorSpeed(2.5)
    rightShoulder.setMotorSpeed(2)
    rightElbow.setMotorSpeed(10)
    leftShoulder.setMotorSpeed(-2)
    leftElbow.setMotorSpeed(10)
}
// No Q/W - Stop hip and shoulder motors
else {
    rightHip.setMotorSpeed(0)
    leftHip.setMotorSpeed(0)
    leftShoulder.setMotorSpeed(0)
    rightShoulder.setMotorSpeed(0)
}

// O Key - Right calf forward, left calf back
if (ODown == true) {
    rightKnee.setMotorSpeed(2.5)
    leftKnee.setMotorSpeed(-2.5)
    leftHip.setLimits(-1.0, 1.0)      // Adjust hip limits
    rightHip.setLimits(-1.3, 0.7)
}
// P Key - Left calf forward, right calf back
else if (PDown == true) {
    rightKnee.setMotorSpeed(-2.5)
    leftKnee.setMotorSpeed(2.5)
    leftHip.setLimits(-1.5, 0.5)      // Adjust hip limits
    rightHip.setLimits(-0.8, 1.2)
}
// No O/P - Stop knee motors
else {
    rightKnee.setMotorSpeed(0)
    leftKnee.setMotorSpeed(0)
}
```

#### 7. UI Key Sprite Updates (lines 877-903)
Updates visual appearance of Q/W/O/P key sprites when pressed.

#### 8. Physics Simulation Step
```javascript
if (firstClick == true && pause == false) {
    m_world.step(0.04, 5, 5)  // timeStep, velocityIterations, positionIterations
}
```

#### 9. Camera Follow Logic
```javascript
if (torso != null) {
    torsoBody = torso.getComponent("physicsBody")
    
    if (firstClick == true) {
        // Vertical camera follow (when jumping high)
        if (torsoBody.getWorldCenter().y < -5) {
            world_camera.pos.y = torsoBody.getWorldCenter().y * worldScale - 210
            ui_camera.pos.y = torsoBody.getWorldCenter().y * worldScale - 210
        }
        // Horizontal camera follow (normal running)
        else if (fallen == false) {
            world_camera.pos.x = (torsoBody.getWorldCenter().x + world_camera_offset) * worldScale
        }
    }
    
    // Update score display
    if (jumpLanded == false) {
        score = round(torsoBody.getWorldCenter().x) / 10  // Convert to meters
        scoreText.setText(score + " metres")
    }
}
```

#### 10. Shader Lighting Updates (line 910)
Updates bevel shader light direction for each body part based on its angle.

#### 11. Game End Check
```javascript
if (jumpLanded == true && gameEnded == false) {
    pause = true
    endGame()
}
else if (jumpLanded == false && gameEnded == false && fallen == true) {
    endGame()
}
```

## beginContact(contact) - Collision Detection (line 912)

### Function Signature
```javascript
beginContact: function(t)  // t = Box2D contact object
```

### Step-by-Step Logic

#### 1. Extract Contact Information
```javascript
fixtureB = contact.getFixtureB()
fixtureA = contact.getFixtureA()
bodyB = fixtureB.getBody()
bodyA = fixtureA.getBody()
userDataB = bodyB.getUserData()  // e.g., "leftFoot", "head", "track"
userDataA = bodyA.getUserData()

worldManifold = new B2WorldManifold()
contact.getWorldManifold(worldManifold)

// Find rightmost contact point
maxX = -100000
for (i = 0; i < worldManifold.m_points.length; i++) {
    point = worldManifold.m_points[i]
    if (point.x > maxX) {
        maxX = point.x
    }
}

contactY = worldManifold.m_points[0].y
```

#### 2. Foot Contact with Track (Landing/Running)
```javascript
if ((userDataB == "leftFoot" || userDataB == "rightFoot") && userDataA == "track") {
    if (gameOver == false && fallen == false) {
        
        // Detect jump start (approaching sand pit)
        if (jumped == false && maxX * worldScale > sandPitAt - 220) {
            jumped = true
        }
        
        // Detect successful landing in sand pit
        if (jumped == true && jumpLanded == false) {
            if (maxX * worldScale > sandPitAt) {
                jumpLanded = true
                
                // Spawn landing particle effect
                burst.color.a = 1
                burst.size = Vector(20, 20)
                burst.pos = Vector(maxX * worldScale, contactY * worldScale)
                
                // Animate burst (expand then fade)
                Actuate.tween(burst.size, 0.08, {x: 40, y: 40})
                    .onComplete(function() {
                        Actuate.tween(burst.size, 0.8, {x: 0, y: 0}).ease(Quad.easeIn)
                        Actuate.tween(burst.color, 0.8, {a: 0}).ease(Quad.easeIn)
                    })
                    .ease(Quad.easeOut)
                
                // Update score
                score = round(maxX) / 10
                if (score > highScore) {
                    highScore = score
                }
            }
        }
    }
}
```

#### 3. Upper Body Contact with Track (Falling)
```javascript
else if ((userDataB == "rightForearm" || userDataB == "leftForearm" ||
          userDataB == "rightArm" || userDataB == "leftArm" ||
          userDataB == "head") && userDataA == "track") {
    
    if (fallen == false) {
        fallen = true
        
        // Calculate impact velocity
        velocityB = bodyB.getLinearVelocity()
        velocityA = bodyA.getLinearVelocity()
        velocityB.subtract(velocityA)
        impactSpeed = velocityB.length()
        
        // Play sound based on impact speed
        if (impactSpeed > 5) {
            m.audio.play("crunch")  // Hard impact
        } else {
            m.audio.play("ehh")     // Soft impact
        }
        
        // Spawn impact particle effect
        burst.color.a = 1
        burst.size = Vector(20, 20)
        burst.pos = Vector(maxX * worldScale, contactY * worldScale)
        
        // Animate burst (larger than landing)
        Actuate.tween(burst.size, 0.15, {x: 80, y: 80})
            .onComplete(function() {
                Actuate.tween(burst.size, 0.8, {x: 0, y: 0}).ease(Quad.easeOut)
                Actuate.tween(burst.color, 0.8, {a: 0}).ease(Quad.easeOut)
            })
            .ease(Quad.easeIn)
        
        // If jumped but not landed, count as landing
        if (jumped == true && jumpLanded == false) {
            jumpLanded = true
        }
        
        // Update score
        score = round(maxX) / 10
        if (score > highScore) {
            highScore = score
        }
    }
}
```

## endContact(contact) - Collision End (line 955)
```javascript
endContact: function() {}  // Empty - no logic needed
```

## connect_input() - Input Binding (line 956)
```javascript
connect_input: function() {
    m.input.bind_key("Q", Keycodes.key_q)
    m.input.bind_key("W", Keycodes.key_w)
    m.input.bind_key("O", Keycodes.key_o)
    m.input.bind_key("P", Keycodes.key_p)
    m.input.bind_key("reset", Keycodes.key_r)
    m.input.bind_key("space", Keycodes.space)
    m.input.bind_key("test", Keycodes.key_t)
}
```

## Critical Constants

### Physics Simulation
- **timeStep**: 0.04 seconds (25 FPS physics)
- **velocityIterations**: 5
- **positionIterations**: 5

### Head Stabilization
- **torque**: -4 * (angle + 0.2)
- Applied every frame when not fallen

### Speed Tracking
- **window size**: 30 samples
- **music volume formula**: (averageSpeed - 2) / 15, clamped to [0, 1]

### Jump Detection
- **jump trigger**: x position > sandPitAt - 220 (19780)
- **landing trigger**: x position > sandPitAt (20000)

### Camera Follow
- **vertical threshold**: torso y < -5
- **vertical offset**: -210 pixels
- **horizontal offset**: world_camera_offset (configurable)

### Collision Detection
- **fall triggers**: head, arms, forearms touching track
- **landing triggers**: feet touching track
- **impact sound threshold**: velocity > 5 = "crunch", else "ehh"

## Notes for 1:1 Recreation

1. **Physics timestep is fixed at 0.04s** regardless of frame rate
2. **Head stabilization torque** is critical for balance
3. **Speed array** smooths music volume changes
4. **Camera follows torso**, not head
5. **Collision userData** strings must match exactly
6. **Particle effects** use tweening library (not critical for gameplay)
7. **Score is in meters** (world units / 10)
8. **Hip limits change dynamically** with O/P keys
