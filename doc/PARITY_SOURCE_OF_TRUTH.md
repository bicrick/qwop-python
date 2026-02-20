# Parity source of truth

The **single source of truth** for qwop-python physics, spawn, and game logic is:

1. **QWOP.min.js** (beautified), in the qwop-gym repo: `qwop_gym/envs/v1/game/QWOP.min.js`
   - `create_player`: ~line 1033 (body positions/angles, joints)
   - `update`: ~line 857 (scoreTime, floor, head torque, controls, physics step, camera, score, end)
   - `beginContact`: ~line 912 (foot/track, upper-body/track fall)
   - Physics step: line 905 `m_world.step(.04, 5, 5)`

2. **doc/reference/** in this repo: QWOP_CONSTANTS.md, QWOP_FUNCTIONS_EXACT.md, QWOP_JOINTS_EXACT_DATA.md, QWOP_BODY_EXACT_DATA.md, QWOP_SPRITE_DIMENSIONS_EXACT.md, QWOP_COLLISION_SYSTEM.md

All constants and logic in qwop-python (`data.py`, `physics.py`, `game.py`, `controls.py`, `collision.py`) are validated against the above. Any change to behavior or constants must trace to a min.js line or doc section.

---

## What is checked and how

| Area | What | How |
|------|------|-----|
| **Constants** | GRAVITY, PHYSICS_TIMESTEP, iterations, HEAD_TORQUE_*, category/mask, CONTROL_* | `tests/test_parity.py::test_constants_parity` |
| **Spawn** | All 12 body positions/angles, camera, ground segments; fixture half_width/half_height from QWOP_SPRITE_DIMENSIONS_EXACT | `python -m qwop_python.tools.verify_spawn_layout` |
| **Update order** | Sequence of operations in game loop | This doc (below); code in `game.py` matches |
| **Contact logic** | Fall detection, foot/track jump and landing | This doc; `collision.py` matches QWOP_FUNCTIONS_EXACT beginContact |
| **Cross-env** | Step-by-step vs browser qwop-gym | `tests/test_cross_env_parity.py`, `scripts/cross_env_parity.py`; see `doc/CROSS_ENV_TEST.md` |

---

## Update order (min.js 857–910)

The game update must run in this order. Implemented in `game.py` `update()`.

1. **Score time** (min.js 858): If not pause and not gameEnded, `scoreTime += t`.
2. **Accelerometer** (858): Skipped in Python (mobile only).
3. **Floor repositioning** (858–865): Reposition ground segments by camera for infinite scroll.
4. **Head torque** (866–868): If not fallen, `head.applyTorque(-4 * (head.getAngle() + 0.2))`.
5. **Speed tracking** (868–874): Rolling average of head velocity x (e.g. last 30 samples); used for music in JS, optional in Python.
6. **Control input** (875): Set motor speeds and hip limits from Q/W/O/P state.
7. **UI sprites** (876–904): Skipped in Python (rendering).
8. **Physics step** (905): If firstClick and not pause, `m_world.step(0.04, 5, 5)`.
9. **Camera** (906–907): Follow torso (horizontal when not fallen; vertical when torso y < -5).
10. **Score** (907): If not jumpLanded and not gameEnded, `score = round(torso.worldCenter.x) / 10`.
11. **Game end** (910–911): If jumpLanded or fallen, trigger end game.

---

## Contact logic (min.js 912–938)

- **beginContact**: Resolve which fixture is player part and which is track (Box2D can pass either order). Use body `userData` strings.
- **Foot + track**: Jump trigger at `maxX * worldScale > sandPitAt - 220`; landing at `maxX * worldScale > sandPitAt`. Only when not gameOver and not fallen.
- **Upper body + track (fall)**: If body part is one of `rightForearm`, `leftForearm`, `rightArm`, `leftArm`, `head` and other is `track`, and not already fallen, set `fallen = true`.

See `QWOP_FUNCTIONS_EXACT.md` beginContact section and `collision.py` for the exact implementation.
