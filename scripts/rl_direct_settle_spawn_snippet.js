/**
 * Suggested settle-spawn helper for browser spectate (rl_direct.js).
 *
 * Not imported by this repo — paste/adapt into the HTML/JS QWOP reset() used
 * by spectate. Goal: match qwop_python.game.QWOPGame.settle_spawn so both envs
 * start planted, near rest, with scoreTime=0 and score=0.
 *
 * See doc/SETTLE_SPAWN.md.
 */

function settleSpawn(game, opts) {
  const maxSteps = (opts && opts.maxSteps) || 20;
  const linEps = (opts && opts.linEps) || 0.45;
  const angEps = (opts && opts.angEps) || 1.5;
  const minSteps = (opts && opts.minSteps) || 8;
  const stableNeeded = (opts && opts.stableNeeded) || 2;

  // Keys up (names depend on your bindings — mirror controls.reset()).
  if (typeof game.releaseAllKeys === "function") {
    game.releaseAllKeys();
  } else {
    game.qDown = false;
    game.wDown = false;
    game.oDown = false;
    game.pDown = false;
  }

  let stable = 0;
  for (let i = 0; i < maxSteps; i++) {
    // IMPORTANT: after FN_RESET / clean reset, do not let a pending reset update
    // advance the race. Prefer a normal update that applies head torque +
    // controls, then force the HUD clock back to 0.
    game.update(1 / 30);
    game.scoreTime = 0;

    const parts = ["torso", "leftFoot", "rightFoot"].map((n) => game.getBody(n));
    const quiet = parts.every((b) => {
      if (!b) return false;
      const v = b.getLinearVelocity();
      return (
        Math.abs(v.x) < linEps &&
        Math.abs(v.y) < linEps &&
        Math.abs(b.getAngularVelocity()) < angEps
      );
    });

    if (quiet && i + 1 >= minSteps) {
      stable += 1;
      if (stable >= stableNeeded) break;
    } else {
      stable = 0;
    }
  }

  const bodies =
    game.playerBodies ||
    ["torso", "head", "leftArm", "rightArm", "leftForearm", "rightForearm",
     "leftThigh", "rightThigh", "leftCalf", "rightCalf", "leftFoot", "rightFoot"]
      .map((n) => game.getBody(n))
      .filter(Boolean);

  for (const body of bodies) {
    body.setLinearVelocity(0, 0);
    body.setAngularVelocity(0);
  }

  game.scoreTime = 0;
  game.score = 0;
  // Optional: reset camera to initial, then follow torso once.
}

/**
 * Example reset() wiring:
 *
 * function reset() {
 *   // 1) Clean recreate / place runner (existing logic)
 *   // 2) Suppress any FN_RESET path that would call update and bump scoreTime
 *   // 3) settleSpawn(game)
 *   // 4) return first observation with time≈0, distance≈0
 * }
 */
