# Settle spawn (start-state parity)

## Why

Friction/density/torques already match between `qwop-python` (PyBox2D) and the
real HTML/JS QWOP used by spectate (`rl_direct.js`). Both still spawn with feet
slightly above the track. Free-fall then first foot plant diverge (Python plants
earlier; torso vertical speed at plant is much higher). That mismatch drives
early spectate faceplants even when mid-race physics look similar.

You cannot make PyBox2D identical to JS Box2D. Settling spawn in **both** envs
aligns the **start state**: planted contacts, near-zero velocities, `scoreTime`
and score at zero — so the policy’s first actions are not compensating for a
different free-fall.

## Python

`QWOPEnv(settle_spawn=True, settle_max_steps=20)` (defaults) calls
`QWOPGame.settle_spawn()` after `reset`/`start`:

1. Keys up
2. Run `update` (head torque + `controls.apply` + physics) up to `settle_max_steps`
3. Zero `score_time` after each settle step
4. Early-exit when torso/feet velocities stay small for a couple of frames
5. Zero all body linear/angular velocities; set `score_time=0`, `score=0`; snap camera

Toggle off with `settle_spawn=False` for ablation / legacy spawn free-fall.

Smoke: `python scripts/tests/test_settle_spawn.py`

## Browser (`rl_direct.js`) suggestion

Browser sources are not in this repo. Mirror the same reset settle in spectate’s
`reset()` (after a clean reset that does **not** let a `FN_RESET` update advance
the race clock). Suggested sketch:

```javascript
// Inside reset(), after recreating/placing the runner and releasing keys:
function settleSpawn(game, maxSteps = 20) {
  // Ensure no Q/W/O/P held
  game.qDown = game.wDown = game.oDown = game.pDown = false;

  for (let i = 0; i < maxSteps; i++) {
    // Prefer a physics-only tick that still applies head torque + controls.apply,
    // but do NOT advance race timing the way a normal FN_RESET/update would.
    // If your update always does scoreTime += 1/30, force scoreTime = 0 after.
    game.update(/* dt unused for HUD; Box2D still steps 0.04 */);
    game.scoreTime = 0;

    const torso = game.getBody("torso");
    const lf = game.getBody("leftFoot");
    const rf = game.getBody("rightFoot");
    const quiet = [torso, lf, rf].every((b) => {
      const v = b.getLinearVelocity();
      return Math.abs(v.x) < 0.45 && Math.abs(v.y) < 0.45
          && Math.abs(b.getAngularVelocity()) < 1.5;
    });
    // Optional: require quiet for 2 consecutive frames after i >= 8, then break.
    if (quiet && i >= 8) break;
  }

  for (const body of game.playerBodies) {
    body.setLinearVelocity(0, 0);
    body.setAngularVelocity(0);
  }
  game.scoreTime = 0;
  game.score = 0;
  // Reset / re-follow camera like a fresh start
}
```

Call `settleSpawn(game)` at the end of `reset()` before returning the first
observation. Observation distance should then be ~0 (or recomputed from torso
and immediately overridden to 0 for parity with Python `info['distance']`).
