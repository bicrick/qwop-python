# Transfer target, clocks, and fair time claims

## Goal

Train RL agents in this fast Python Box2D env (`qwop-python`), then transfer
policies to the real browser game via [qwop-gym](https://github.com/smanolloff/qwop-gym)
and aim to beat the human 100 m WR of **45.530 s**.

API compatibility with qwop-gym is intentional: **60-dim** observations and
**Discrete(9)** / **Discrete(16)** actions.

## Two clocks

| Clock | Source | Use |
|-------|--------|-----|
| **Physics time** | `info['time']` = `game.score_time`, advances by `0.04 s` per Box2D tick | Fair race times, WR claims, `speed_mps` |
| **Protocol / reward dt** | `frames_per_step * (1/30) / 10` inside `_calc_reward` | Reward parity with qwop-wr / browser training only — **not** a wall-clock or physics race timer |

Env steps advance `frames_per_step` physics ticks. With `frames_per_step=4`,
each action lasts `0.16 s` of physics time.

Episode mean speed for claims:

```text
speed_mps = distance_m / info['time']
```

## `avgspeed` vs `speed_mps`

- `info['distance']` is already in **metres** (`torso_x / 10`).
- Legacy `info['avgspeed']` keeps the qwop-gym `FN_UPDATE_STATS` formula
  `10 * ds / dt`. That factor of 10 makes the value ~Box2D world-units/s
  (**~10× too high** vs metres/s). Kept for backward compatibility only.
- Prefer **`info['speed_mps']`** (rolling buffer) or `distance / time` for
  honest metrics. Velocity reward shaping uses `speed_mps`, not `avgspeed`.

## Fall detection (matches original JS)

Authoritative list from `doc/reference/QWOP_FUNCTIONS_EXACT.md`: fall when
**head, left/right arm, or left/right forearm** touches the track.

**Torso is not a fall trigger** in the original game. Belly-slide crawls can
therefore run until `max_episode_steps` without `fallen=True`.

Do **not** add torso to fall detection if the goal is browser transfer parity.
Use optional stuck detection instead (below).

Note: older notes in `QWOP_GAME_LOGIC.md` mention torso; the exact extracted
contact handler does not. Trust `QWOP_FUNCTIONS_EXACT.md`.

## Stuck detection (optional)

`StuckDetectionWrapper` ends an episode as failure when speed stays below
`min_speed_mps` and distance is flat for `patience_steps`. Enable only via
`env_wrappers` in YAML (off by default so existing train configs are unchanged).

`config/eval_wr.yml` enables it for WR evals.

## How to claim a time fairly

1. Run headless eval with physics reporting:
   `qwop-python -c config/eval_wr.yml evaluate`
2. Use **`info['time']`** (physics seconds), not protocol dt or wall clock.
3. Require a true finish: `is_success` (jump landed, not fallen) and
   distance ≥ 100 m (or the sand-pit finish the env already uses).
4. Report `speed_mps = distance / time` (or the eval summary fields).
5. Compare against **45.530 s**. Do not quote legacy `avgspeed`.
6. For a transfer claim on browser QWOP, re-evaluate in qwop-gym / the live
   game with the same physics-time definition — Python Box2D and JS Box2D
   can diverge even when the API matches.

## Quick eval

```bash
# Edit model_file / model_cls in config/eval_wr.yml first
qwop-python -c config/eval_wr.yml evaluate
```
