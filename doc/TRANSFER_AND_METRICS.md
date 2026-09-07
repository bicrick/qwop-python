# Transfer target, clocks, and fair time claims

## Goal

Train RL agents in this fast Python Box2D env (`qwop-python`), then transfer
policies to the real browser game via [qwop-gym](https://github.com/smanolloff/qwop-gym)
and aim to beat the human 100 m WR of **45.530 s** (HUD / on-screen clock).

API compatibility with qwop-gym is intentional: **60-dim** observations and
**Discrete(9)** / **Discrete(16)** actions.

## Clocks (critical)

Real HTML/JS QWOP (and the browser drive behind qwop-gym) does two different
things each update:

| What | Value |
|------|--------|
| `scoreTime += …` (HUD) | **1/30** s per update |
| `world.Step(…)` (Box2D) | **0.04** s per update |

This repo aligns with that drive: `game.score_time` / `info['time']` advances
by `SCORE_TIME_STEP = 1/30` per update while Box2D still steps `0.04`.

| Clock | Source | Use |
|-------|--------|-----|
| **HUD time** | `info['time']` = `game.score_time` (`+1/30` per update) | Fair race times, WR claims, `speed_mps` — same scale as the in-game timer / human WR |
| **Protocol time** | `scoreTime / 10` (qwop-gym RL logs); reward uses `dt_protocol = frames_per_step/30/10` | Reward parity with qwop-wr / qwop-gym training only |
| **Box2D dt** | `PHYSICS_TIMESTEP = 0.04` | Simulation only — not the race clock |

Conversions (for reading older Python logs that advanced `score_time` by 0.04):

```text
t_hud ≈ t_protocol * 10
t_hud ≈ t_python_old * (1/30) / 0.04 = t_python_old / 1.2
```

Example: a logged “&lt;6 s” **protocol** finish is ~**60 s HUD**, not a sub-WR run.

Env steps advance `frames_per_step` updates. With `frames_per_step=4`,
each action advances HUD time by `4/30 ≈ 0.133 s`.

Episode mean speed for claims:

```text
speed_mps = distance_m / info['time']   # metres / HUD seconds
```

## `avgspeed` vs `speed_mps`

- `info['distance']` is already in **metres** (`torso_x / 10`).
- Legacy `info['avgspeed']` keeps the qwop-gym `FN_UPDATE_STATS` formula
  `10 * ds / dt_box2d`. That factor of 10 makes the value ~Box2D world-units/s
  (**~10× too high** vs metres/s). Kept for backward compatibility only.
- Prefer **`info['speed_mps']`** (rolling buffer on the HUD clock) or
  `distance / time`. Velocity reward shaping uses `speed_mps`, not `avgspeed`.

## Fall detection (matches original JS)

Authoritative list from `doc/reference/QWOP_FUNCTIONS_EXACT.md` / QWOP.min.js:
fall when **head, left/right arm, or left/right forearm** touches the track.

**Torso is not a fall trigger.** `QWOP_GAME_LOGIC.md` saying otherwise is wrong.
Belly-slide crawls can run until `max_episode_steps` without `fallen=True`.

Do **not** add torso to fall detection for browser transfer parity.
Use optional stuck detection instead (below).

## Stuck detection (optional)

`StuckDetectionWrapper` ends an episode as failure when speed stays below
`min_speed_mps` and distance is flat for `patience_steps`. Enable only via
`env_wrappers` in YAML (off by default so existing train configs are unchanged).

`config/eval_wr.yml` enables it for WR evals.

## Hurdles

`HURDLES_ENABLED` defaults to **False** in `qwop_python/data.py` (faster
training; mid-track hurdle omitted). Real browser QWOP has the hurdle.

For parity runs, set without changing the global default:

```yaml
env_kwargs:
  hurdles_enabled: true
```

## Success criteria

| Mode | Rule |
|------|------|
| **This env (default)** | Land-based: `jump_landed` and not `fallen` (sand-pit land / JS `endGame`) |
| **qwop-gym (common)** | Often `distance >= 100` “escape” without requiring a clean land |

Python keeps land-based success stable. Do not treat `distance >= 100` alone
as success unless you explicitly add a separate criterion for transfer
experiments. Eval’s `finish_distance_m` is only used when ranking finishes
that already have `is_success`.

## How to claim a time fairly

1. Run headless eval:
   `qwop-python -c config/eval_wr.yml evaluate`
2. Use **`info['time']`** (HUD seconds), not protocol dt or wall clock.
3. Require land-based `is_success` (and typically distance ≥ 100 m).
4. Report `speed_mps = distance / time`.
5. Compare against **45.530 s HUD**. Do not quote legacy `avgspeed` or
   protocol-scaled times as HUD/WR times.
6. Re-evaluate in qwop-gym / live QWOP before a browser transfer claim —
   PyBox2D and JS Box2D can diverge even when the API matches.

## Quick eval

```bash
# Edit model_file / model_cls in config/eval_wr.yml first
qwop-python -c config/eval_wr.yml evaluate
```
