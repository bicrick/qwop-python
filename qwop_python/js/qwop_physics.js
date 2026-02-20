/**
 * QWOP physics-only bundle for PyMiniRacer.
 * Uses global "planck" (load planck.min.js first). No DOM.
 * Source of truth: doc/reference/ (QWOP_JOINTS_EXACT_DATA.md, QWOP_CONTROLS.md,
 * QWOP_FUNCTIONS_EXACT.md) and OG QWOP.min.js (qwop-gym envs/v1/game/).
 * Constants and control logic match qwop_python/data.py; joint creation order
 * matches OG (neck, rightShoulder, leftShoulder, leftHip, rightHip, elbows, knees, ankles).
 */
'use strict';

var Vec2 = planck.Vec2;
  var Box = planck.Box;
  var RevoluteJoint = planck.RevoluteJoint;

  // ---------------------------------------------------------------------------
  // Constants (from data.py / QWOP.min.js)
  // ---------------------------------------------------------------------------
  var GRAVITY = 10;
  var WORLD_SCALE = 20;
  var PHYSICS_TIMESTEP = 0.04;
  var VELOCITY_ITERATIONS = 5;
  var POSITION_ITERATIONS = 5;
  var TRACK_Y = 10.74275;
  var TRACK_HALF_HEIGHT = 64 / (2 * WORLD_SCALE);
  var TRACK_FRICTION = 0.2;
  var TRACK_DENSITY = 30;
  var SAND_PIT_AT = 20000;
  var JUMP_TRIGGER_OFFSET = 220;
  var HEAD_TORQUE_FACTOR = -4;
  var HEAD_TORQUE_OFFSET = 0.2;
  var SCREEN_WIDTH = 640;
  var SEGMENT_WIDTH = SCREEN_WIDTH / WORLD_SCALE;
  var CATEGORY_GROUND = 0x0001;
  var CATEGORY_PLAYER = 0x0002;
  var MASK_ALL = 0xFFFF;
  var MASK_NO_SELF = 0xFFFD;

  var BODY_PARTS = {
    torso:    { position: [2.5111726226000157, -1.8709517533957938], angle: -1.2514497119301329, halfWidth: 3.275, halfHeight: 1.425, friction: 0.2, density: 1.0, userData: 'torso' },
    head:     { position: [3.888130278719558, -5.621802929095265], angle: 0.06448415835225099, halfWidth: 1.075, halfHeight: 1.325, friction: 0.2, density: 1.0, userData: 'head' },
    leftArm:  { position: [4.417861014480877, -2.806563606410589], angle: 0.9040095895272826, halfWidth: 1.85, halfHeight: 0.625, friction: 0.2, density: 1.0, userData: 'leftArm' },
    leftForearm: { position: [5.830008603424893, -2.8733539631159584], angle: -1.2049772618421237, halfWidth: 1.75, halfHeight: 0.55, friction: 0.2, density: 1.0, userData: 'leftForearm' },
    leftThigh: { position: [2.5648987628203876, 1.648090668682522], angle: -2.0177234426823394, halfWidth: 2.525, halfHeight: 1.0, friction: 0.2, density: 1.0, userData: 'leftThigh' },
    leftCalf: { position: [3.12585731974087, 5.525511655361298], angle: -1.5903971528225265, halfWidth: 2.5, halfHeight: 0.75, friction: 0.2, density: 1.0, userData: 'leftCalf' },
    leftFoot: { position: [3.926921842806667, 8.08884032049622], angle: 0.12027524643408766, halfWidth: 1.35, halfHeight: 0.675, friction: 1.5, density: 3.0, userData: 'leftFoot' },
    rightArm: { position: [1.1812303663272852, -3.5000256518601014], angle: -0.5222217404634386, halfWidth: 1.95, halfHeight: 0.75, friction: 0.2, density: 1.0, userData: 'rightArm' },
    rightForearm: { position: [0.4078206420797428, -1.0599953233084172], angle: -1.7553358283857299, halfWidth: 2.225, halfHeight: 0.675, friction: 0.2, density: 1.0, userData: 'rightForearm' },
    rightThigh: { position: [1.6120186135678773, 2.0615320561881516], angle: 1.4849422964528027, halfWidth: 2.65, halfHeight: 1.0, friction: 0.2, density: 1.0, userData: 'rightThigh' },
    rightCalf: { position: [-0.07253905736790486, 5.347881871063159], angle: -0.7588859967104447, halfWidth: 2.5, halfHeight: 0.75, friction: 0.2, density: 1.0, userData: 'rightCalf' },
    rightFoot: { position: [-1.1254742643908706, 7.567193169625567], angle: 0.5897605418219602, halfWidth: 1.35, halfHeight: 0.725, friction: 1.5, density: 3.0, userData: 'rightFoot' }
  };

  var BODY_ORDER = ['torso', 'head', 'leftArm', 'leftCalf', 'leftFoot', 'leftForearm', 'leftThigh', 'rightArm', 'rightCalf', 'rightFoot', 'rightForearm', 'rightThigh'];

  // Joint creation order matches OG QWOP.min.js (line 1173): neck, shoulders, hips, elbows, knees, ankles.
  var JOINTS = [
    { name: 'neck', bodyA: 'head', bodyB: 'torso', anchorA: [3.5885141908253755, -4.526224223627244], anchorB: [3.588733341630704, -4.526434658500262], lowerAngle: -0.5, upperAngle: 0, referenceAngle: -1.308996406363529, enableMotor: false, maxMotorTorque: 0, motorSpeed: 0 },
    { name: 'rightShoulder', bodyA: 'rightArm', bodyB: 'torso', anchorA: [2.228476821818547, -4.086468732185028], anchorB: [2.228929993886102, -4.08707555939957], lowerAngle: -0.5, upperAngle: 1.5, referenceAngle: -0.7853907065463961, enableMotor: true, maxMotorTorque: 1000, motorSpeed: 0 },
    { name: 'leftShoulder', bodyA: 'leftArm', bodyB: 'torso', anchorA: [3.6241979856895377, -3.5334881618011442], anchorB: [3.6241778782207157, -3.533950434531982], lowerAngle: -2.0, upperAngle: 0.0, referenceAngle: -2.09438311816829, enableMotor: true, maxMotorTorque: 1000, motorSpeed: 0 },
    { name: 'leftHip', bodyA: 'leftThigh', bodyB: 'torso', anchorA: [2.0030339754142847, 0.23737160622781284], anchorB: [2.003367181376716, 0.23802590387419476], lowerAngle: -1.5, upperAngle: 0.5, referenceAngle: 0.7258477508944043, enableMotor: true, maxMotorTorque: 6000, motorSpeed: 0 },
    { name: 'rightHip', bodyA: 'rightThigh', bodyB: 'torso', anchorA: [1.2475900729227194, -0.011046642863645761], anchorB: [1.2470052823973599, -0.011635347168778898], lowerAngle: -1.3, upperAngle: 0.7, referenceAngle: -2.719359381718199, enableMotor: true, maxMotorTorque: 6000, motorSpeed: 0 },
    { name: 'leftElbow', bodyA: 'leftForearm', bodyB: 'leftArm', anchorA: [5.525375332758792, -1.63856204930891], anchorB: [5.52537532948459, -1.6385620366077662], lowerAngle: -0.1, upperAngle: 0.5, referenceAngle: 2.09438311816829, enableMotor: false, maxMotorTorque: 0, motorSpeed: 0 },
    { name: 'rightElbow', bodyA: 'rightForearm', bodyB: 'rightArm', anchorA: [-0.006090859076100963, -2.8004758838752157], anchorB: [-0.0060908611708438976, -2.8004758929205846], lowerAngle: -0.1, upperAngle: 0.5, referenceAngle: 1.2968199012274688, enableMotor: false, maxMotorTorque: 0, motorSpeed: 0 },
    { name: 'leftKnee', bodyA: 'leftCalf', bodyB: 'leftThigh', anchorA: [3.384323411985692, 3.5168931240916876], anchorB: [3.3844684376952108, 3.5174122997898016], lowerAngle: -1.6, upperAngle: 0.0, referenceAngle: -0.3953113764119829, enableMotor: true, maxMotorTorque: 3000, motorSpeed: 0 },
    { name: 'rightKnee', bodyA: 'rightCalf', bodyB: 'rightThigh', anchorA: [1.4982369235492752, 4.175600306005656], anchorB: [1.4982043532615996, 4.17493520671361], lowerAngle: -1.3, upperAngle: 0.3, referenceAngle: 2.2893406247158676, enableMotor: true, maxMotorTorque: 3000, motorSpeed: 0 },
    { name: 'leftAnkle', bodyA: 'leftFoot', bodyB: 'leftCalf', anchorA: [3.312322507818897, 7.947704853895541], anchorB: [3.3123224825088817, 7.947704836256229], lowerAngle: -0.5, upperAngle: 0.5, referenceAngle: -1.7244327585010226, enableMotor: false, maxMotorTorque: 2000, motorSpeed: 0 },
    { name: 'rightAnkle', bodyA: 'rightFoot', bodyB: 'rightCalf', anchorA: [-1.6562855402197227, 6.961551452557676], anchorB: [-1.655726670462596, 6.961493826969391], lowerAngle: -0.5, upperAngle: 0.5, referenceAngle: -1.5708045825942758, enableMotor: false, maxMotorTorque: 2000, motorSpeed: 0 }
  ];

  // Control constants: match qwop_python/data.py and doc/reference/QWOP_CONTROLS.md, QWOP_FUNCTIONS_EXACT.md (OG line 876).
  var CONTROL_Q = { motorSpeeds: { rightHip: 2.5, leftHip: -2.5, rightShoulder: -2.0, leftShoulder: 2.0 }, hipLimits: {} };
  var CONTROL_W = { motorSpeeds: { rightHip: -2.5, leftHip: 2.5, rightShoulder: 2.0, leftShoulder: -2.0 }, hipLimits: {} };
  var CONTROL_O = { motorSpeeds: { rightKnee: 2.5, leftKnee: -2.5 }, hipLimits: { leftHip: [-1.0, 1.0], rightHip: [-1.3, 0.7] } };
  var CONTROL_P = { motorSpeeds: { rightKnee: -2.5, leftKnee: 2.5 }, hipLimits: { leftHip: [-1.5, 0.5], rightHip: [-0.8, 1.2] } };

  // Restored when neither O nor P is pressed (doc: Q/W running has full hip range; matches JOINTS default limits).
  var DEFAULT_HIP_LIMITS = { leftHip: [-1.5, 0.5], rightHip: [-1.3, 0.7] };

  // ---------------------------------------------------------------------------
  // Seeded RNG (deterministic reset)
  // ---------------------------------------------------------------------------
  function mulberry32(seed) {
    return function () {
      var t = seed += 0x6D2B79F5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var random = mulberry32(12345);

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var world = null;
  var bodies = {};
  var joints = {};
  var groundSegments = [];
  var gameState = { scoreTime: 0, score: 0, highScore: 0, gameEnded: false, fallen: false, jumped: false, jumpLanded: false };
  var keyState = { q: false, w: false, o: false, p: false };
  var firstClick = true;

  function createWorld() {
    world = planck.World({ gravity: Vec2(0, GRAVITY), allowSleep: true });
    world.on('begin-contact', function (contact) {
      var fa = contact.getFixtureA();
      var fb = contact.getFixtureB();
      var ba = fa.getBody();
      var bb = fb.getBody();
      var ua = ba.getUserData();
      var ub = bb.getUserData();
      if (!ua || !ub) return;
      var bodyPart = ua === 'track' ? ub : (ub === 'track' ? ua : null);
      if (bodyPart === null || (ua !== 'track' && ub !== 'track')) return;
      var bodyPartBody = ua === 'track' ? bb : ba;
      var maxX = -1e5;
      try {
        var manifold = contact.getManifold();
        if (manifold && manifold.points && manifold.pointCount > 0) {
          for (var i = 0; i < manifold.pointCount; i++) {
            var lp = manifold.points[i].localPoint;
            var wp = bodyPartBody.getWorldPoint(lp);
            if (wp.x > maxX) maxX = wp.x;
          }
        } else {
          maxX = bodyPartBody.getWorldCenter().x;
        }
      } catch (e) {
        maxX = bodyPartBody.getWorldCenter().x;
      }
      if (bodyPart === 'leftFoot' || bodyPart === 'rightFoot') {
        if (!gameState.gameEnded && !gameState.fallen) {
          if (!gameState.jumped && maxX * WORLD_SCALE > (SAND_PIT_AT - JUMP_TRIGGER_OFFSET)) gameState.jumped = true;
          if (gameState.jumped && !gameState.jumpLanded && maxX * WORLD_SCALE > SAND_PIT_AT) {
            gameState.jumpLanded = true;
            gameState.score = Math.round(maxX) / 10;
            if (gameState.score > gameState.highScore) gameState.highScore = gameState.score;
          }
        }
      } else if (bodyPart === 'head' || bodyPart === 'leftArm' || bodyPart === 'rightArm' || bodyPart === 'leftForearm' || bodyPart === 'rightForearm') {
        if (!gameState.fallen) {
          gameState.fallen = true;
          if (gameState.jumped && !gameState.jumpLanded) gameState.jumpLanded = true;
          gameState.score = Math.round(maxX) / 10;
          if (gameState.score > gameState.highScore) gameState.highScore = gameState.score;
        }
      }
    });
  }

  function createGround() {
    var numSegments = 3;
    for (var i = 0; i < numSegments; i++) {
      var bd = { type: 'static', position: Vec2(i * SEGMENT_WIDTH, TRACK_Y) };
      var body = world.createBody(bd);
      body.createFixture(Box(SEGMENT_WIDTH / 2, TRACK_HALF_HEIGHT), { friction: TRACK_FRICTION, density: TRACK_DENSITY });
      body.setUserData('track');
      groundSegments.push(body);
    }
  }

  function createBodies() {
    var name;
    for (var i = 0; i < BODY_ORDER.length; i++) {
      name = BODY_ORDER[i];
      var c = BODY_PARTS[name];
      var bd = { type: 'dynamic', position: Vec2(c.position[0], c.position[1]), angle: c.angle };
      var body = world.createBody(bd);
      body.createFixture(Box(c.halfWidth, c.halfHeight), { density: c.density, friction: c.friction });
      body.setUserData(c.userData);
      bodies[name] = body;
    }
  }

  function createJoints() {
    var j, bodyA, bodyB, la, lb, def;
    for (var i = 0; i < JOINTS.length; i++) {
      j = JOINTS[i];
      bodyA = bodies[j.bodyA];
      bodyB = bodies[j.bodyB];
      la = bodyA.getLocalPoint(Vec2(j.anchorA[0], j.anchorA[1]));
      lb = bodyB.getLocalPoint(Vec2(j.anchorB[0], j.anchorB[1]));
      def = {
        bodyA: bodyA,
        bodyB: bodyB,
        localAnchorA: la,
        localAnchorB: lb,
        referenceAngle: j.referenceAngle,
        enableLimit: true,
        lowerAngle: j.lowerAngle,
        upperAngle: j.upperAngle,
        enableMotor: j.enableMotor,
        maxMotorTorque: j.maxMotorTorque,
        motorSpeed: j.motorSpeed
      };
      var joint = world.createJoint(RevoluteJoint(def));
      joints[j.name] = joint;
    }
  }

  // Control logic matches OG QWOP.min.js line 876 and doc QWOP_FUNCTIONS_EXACT.md / QWOP_CONTROLS.md.
  // Q/W: hip and shoulder motors; O/P: knee motors + dynamic hip limits (setLimits). When no O/P we restore default hip limits.
  function applyControls() {
    var jn, j;
    if (keyState.q) {
      for (jn in CONTROL_Q.motorSpeeds) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(CONTROL_Q.motorSpeeds[jn]); }
      for (jn in CONTROL_Q.hipLimits) { j = joints[jn]; if (j && j.setLimits) j.setLimits(CONTROL_Q.hipLimits[jn][0], CONTROL_Q.hipLimits[jn][1]); }
    } else if (keyState.w) {
      for (jn in CONTROL_W.motorSpeeds) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(CONTROL_W.motorSpeeds[jn]); }
      for (jn in CONTROL_W.hipLimits) { j = joints[jn]; if (j && j.setLimits) j.setLimits(CONTROL_W.hipLimits[jn][0], CONTROL_W.hipLimits[jn][1]); }
    } else {
      ['rightHip', 'leftHip', 'rightShoulder', 'leftShoulder'].forEach(function (jn) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(0); });
    }
    if (keyState.o) {
      for (jn in CONTROL_O.motorSpeeds) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(CONTROL_O.motorSpeeds[jn]); }
      for (jn in CONTROL_O.hipLimits) { j = joints[jn]; if (j && j.setLimits) j.setLimits(CONTROL_O.hipLimits[jn][0], CONTROL_O.hipLimits[jn][1]); }
    } else if (keyState.p) {
      for (jn in CONTROL_P.motorSpeeds) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(CONTROL_P.motorSpeeds[jn]); }
      for (jn in CONTROL_P.hipLimits) { j = joints[jn]; if (j && j.setLimits) j.setLimits(CONTROL_P.hipLimits[jn][0], CONTROL_P.hipLimits[jn][1]); }
    } else {
      ['rightKnee', 'leftKnee'].forEach(function (jn) { j = joints[jn]; if (j && j.setMotorSpeed) j.setMotorSpeed(0); });
      for (jn in DEFAULT_HIP_LIMITS) { j = joints[jn]; if (j && j.setLimits) j.setLimits(DEFAULT_HIP_LIMITS[jn][0], DEFAULT_HIP_LIMITS[jn][1]); }
    }
  }

  function update(dt, timeDt) {
    if (!firstClick) return;
    if (!gameState.gameEnded) gameState.scoreTime += (timeDt != null ? timeDt : dt);
    if (!gameState.fallen && bodies.head) {
      var head = bodies.head;
      head.applyTorque(HEAD_TORQUE_FACTOR * (head.getAngle() + HEAD_TORQUE_OFFSET));
    }
    applyControls();
    world.step(PHYSICS_TIMESTEP, VELOCITY_ITERATIONS, POSITION_ITERATIONS);
    if (!gameState.jumpLanded && !gameState.gameEnded && bodies.torso) {
      var torso = bodies.torso;
      gameState.score = Math.round(torso.getWorldCenter().x) / 10;
    }
    if (gameState.jumpLanded && !gameState.gameEnded) gameState.gameEnded = true;
    else if (!gameState.jumpLanded && !gameState.gameEnded && gameState.fallen) gameState.gameEnded = true;
  }

  // Gym observation protocol: browser sends body getPosition() in Box2D world units (metres); normalizer ranges are pos_x [-10,1050] m, pos_y [-10,10] m, vel in m/s
  function getObservation() {
    var obs = [];
    var i, b, pos, vel, name;
    for (i = 0; i < BODY_ORDER.length; i++) {
      name = BODY_ORDER[i];
      b = bodies[name];
      if (!b) { obs.push(0, 0, 0, 0, 0); continue; }
      pos = b.getWorldCenter();
      vel = b.getLinearVelocity();
      obs.push(pos.x, pos.y, b.getAngle(), vel.x, vel.y);
    }
    var torso = bodies.torso;
    var distance = torso ? torso.getWorldCenter().x / 10 : 0;
    var time = gameState.scoreTime / 10;
    var gameEnded = gameState.gameEnded || distance < -10 || distance > 105;
    var success = distance > 100;
    return { time: time, distance: distance, obs: obs, gameEnded: gameEnded, success: success, fallen: gameState.fallen, jumped: gameState.jumped, jumpLanded: gameState.jumpLanded };
  }

  function destroyPlayer() {
    var jn, j;
    for (jn in joints) { j = joints[jn]; if (j) world.destroyJoint(j); }
    joints = {};
    var bn, body;
    for (bn in bodies) { body = bodies[bn]; if (body) world.destroyBody(body); }
    bodies = {};
  }

  function reset(seed) {
    if (world) {
      destroyPlayer();
    } else {
      createWorld();
      createGround();
    }
    if (seed != null) random = mulberry32(seed | 0);
    createBodies();
    createJoints();
    gameState = { scoreTime: 0, score: 0, highScore: gameState && gameState.highScore ? gameState.highScore : 0, gameEnded: false, fallen: false, jumped: false, jumpLanded: false };
    keyState = { q: false, w: false, o: false, p: false };
    firstClick = true;
    return true;  // PyMiniRacer .call() rejects undefined
  }

  function setAction(q, w, o, p) {
    keyState.q = !!q;
    keyState.w = !!w;
    keyState.o = !!o;
    keyState.p = !!p;
    return true;  // PyMiniRacer .call() rejects undefined
  }

  function step(dt, timeDt) {
    if (dt == null) dt = PHYSICS_TIMESTEP;
    firstClick = true;
    update(dt, timeDt);
    return true;  // PyMiniRacer .call() rejects undefined
  }

// Expose for PyMiniRacer (global scope: qwop is on the eval context)
var qwop = { reset: reset, setAction: setAction, step: step, getObservation: getObservation };
