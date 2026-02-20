# Parity constants: qwop-python vs qwop-gym (QWOP.min.js)

Single reference for constants that must match between qwop-python and the browser game for reward and physics parity.

## Physics and world

| Constant | qwop-python | QWOP.min.js / extensions.js | Notes |
|----------|-------------|-----------------------------|--------|
| Gravity | `data.GRAVITY` = 10 | `l.gravity` = 10, `B2World(0, l.gravity)` | m/s² downward |
| World scale | `data.WORLD_SCALE` = 20 | `l.worldScale` = 20 | Pixels per metre |
| Physics timestep | `data.PHYSICS_TIMESTEP` = 0.04 | `m_world.step(.04, 5, 5)` | 25 Hz |
| Velocity iterations | `data.VELOCITY_ITERATIONS` = 5 | Second arg to `step()` = 5 | Box2D |
| Position iterations | `data.POSITION_ITERATIONS` = 5 | Third arg to `step()` = 5 | Box2D |
| Density factor | `data.DENSITY_FACTOR` = 1 | `l.densityFactor` = 1 | Body density multiplier |
| Torque factor | `data.TORQUE_FACTOR` = 1 | `l.torqueFactor` = 1 | Joint torque multiplier |
| Track Y | `data.TRACK_Y` = 10.74275 | `d.setPosition(..., 10.74275)` in create_world | Box2D world units |
| Track friction | `data.TRACK_FRICTION` = 0.2 | `u.friction = .2` (track) | |
| Track density | `data.TRACK_DENSITY` = 30 | `u.density = 30`, `userData: "track"` | |

## Reward and time (RL interface)

| Constant | qwop-python | qwop-gym / extensions.js | Notes |
|----------|-------------|--------------------------|--------|
| Reward dt (protocol) | `frames_per_step * (1/30) / 10` when `reward_dt_mode="protocol_30hz"` | `reaction.time - last_reaction.time` with `time = scoreTime/10`, scoreTime += 1/30 per update | Same scale |
| Info time scale | `info["time"] = score_time/10` when protocol_30hz | `time = CORE.game.scoreTime / 10` | Match for logs |
| Avgspeed scale | 10 * (m/s) | `distance / reaction.time` = 10*m/s | info["avgspeed"] |
| Distance | torso x / 10 (metres) | `getPosition().x / 10` | info["distance"] |

## Joint motor torques (from QWOP_CONSTANTS.md)

| Joint | qwop-python (data/controls) | JS |
|-------|----------------------------|-----|
| Shoulders | 1000 * TORQUE_FACTOR | 1000 * torqueFactor |
| Elbows | 0 (passive) | 0 |
| Hips | 6000 * TORQUE_FACTOR | 6000 * torqueFactor |
| Knees | 3000 * TORQUE_FACTOR | 3000 * torqueFactor |
| Ankles | 2000 * TORQUE_FACTOR (passive) | 2000 * torqueFactor |

## Body and collision

- Body positions, half-widths, angles: see `data.BODY_PARTS` and doc/reference/QWOP_BODY_EXACT_DATA.md (from reverse-engineered JS).
- Category/mask: `CATEGORY_GROUND` 1, `CATEGORY_PLAYER` 2, `MASK_NO_SELF` 65533; track uses categoryBits 1, maskBits 65535 in JS.

## How to check for drift

- Run `python -m pytest tests/test_parity.py::test_constants_parity -v` (see tests/test_parity.py) to assert critical constants.
- When updating physics or reward, update this doc and the test if you add or change a constant.
