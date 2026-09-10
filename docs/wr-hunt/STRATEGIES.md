# WR hunt strategies (qwop-python → real browser)

Goal: beat human HTML5 QWOP 100m WR **45.530s HUD** (kurodo1916) on the **official browser** game.
Train in high-throughput `qwop-python` (Box2D), transfer via spectate / direct RL on the real page.

## Clocks (do not mix)

- Browser HUD `scoreTime` is the official clock.
- Python: `PHYSICS_TIMESTEP=0.04`, `SCORE_TIME_STEP=1/30`, typical `frames_per_step=2`.
- `user/time` on a **landed finish** (game ended, jump_landed, not fallen) is the finish clock.
- `user/split_100m_time` is only when torso first crosses 100m — **not** a finish / not a WR claim.
- Rough converts: W&B/protocol ×10 ≈ HUD; Python `info['time']` (0.04/tick) / 1.2 ≈ HUD. Never compare raw protocol times to 45.53.

## Pipeline

1. **Python PPO** (SB3) with gait / start adapters on settle-aware env.
2. **Spectate hunt** on GCP VM against real HTML QWOP (`TRAIN_PHYSICS=0`, settle spawn).
3. Keep only HUD finishes **&lt; 45.530**; ping on new browser PB / first WR keep.

## Strategy timeline (what we tried)

| Era | Idea | Outcome |
|-----|------|---------|
| Phase A QRDQN / expert | Scout fps1/fps2, from-expert, extended knee | Useful for tooling; not WR pace |
| BC / GAIL / AIRL | Demo bootstrap, BC warmup, browser `.rec` BC→PPO | Transfer helped some; not sufficient alone |
| Kurodo key timeline | Extract presses from WR video → `.rec` replay | Open-loop faceplants; timings not portable |
| Flex gait imitation | Soft QO→WP cycle (not timestamp lock) | First serious sub-50 Python finishes |
| Continue / speed / soft-hold / none-grace | Plateau ~51s then ~46–48 windows | Longer train + stride stretch beat reseeds |
| fps2stride family | Longer stride / grace / half075 / ent | Live Python best **43.592** (early1) *pre-settle dive* |
| Official 0.04 clock + browser spectate | Sim→real hunt | Browser PB **46.100** HUD |
| Spawn settle parity | Both envs plant at rest before clock | Closes plant/vel gap; exposes dive-start artifact |
| StartPaceWrapper | Dense reward &lt;10m + early-fall cost, settle ON | In flight — judge on **browser** t_0_10 / finish |

## Causal finding (post-settle)

Same early1 policy:

- **settle OFF** → ~6.8s to 10m / ~43–44s finishes (fake dive start).
- **settle ON** → ~9–10s to 10m / ~46–48s (browser-like) or low finish rate.

~2.5s Python→browser gap is **~79% first 10m**, not mid-race max velocity.

## Kurodo WR splits (target)

See `KURODO_WR_SPLITS.md`. Headline vs our browser PB 46.100:

- WR **t_0_10 = 7.64**; we are **8.80** (+1.16).
- Mid/late we are *faster* than WR.
- Hybrid WR start + our post-10m ≈ **44.94**.

Also: Kurodo **10m** board **7.067s**.

## Current policy (as of 2026-09-10)

- Cap ~3 trainers + spectate VM (`qwop-spectate-wr-hunt-*`, never delete).
- Spectate default: best finish-capable zip (early1 line) with settle + official physics.
- **startpace** / start adapters: do **not** auto-promote to spectate on Python times alone — browser-gate on `t_0_10` / finish.
- Stop workers that are not actually dropping times.
- Prefer checkpoint continuation of the best policy over same-recipe reseeds of a plateaued gait.

## Key configs

- `config/env.yml` — `settle_spawn: true` (parity with browser).
- `config/train_ppo_gait_fps2stride_*.yml` — stride / grace / earlysurv / ent / startpace family.
- `config/train_ppo_gait_fps2stride_startpace.yml` — settle-ON start adapter + `StartPaceWrapper`.
- `config/train_ppo_browser_bc_finetune.yml` / `train_bc_browser_fps2.yml` — browser demo path.
- `config/train_ppo_kurodo_gait*.yml` — flex gait era.

## Key code

- `qwop_python/wrappers/start_pace_wrapper.py`
- `qwop_python/wrappers/flex_gait_wrapper.py`
- `qwop_python/wrappers/early_survival_wrapper.py`
- Game settle: `QWOPGame.settle_spawn` / env `settle_spawn=True` (merged PR #10).

## Out of repo (ops)

GCP fleet, GCS `gs://qwop-wr-training`, spectate VM, 15m orchestrator — see `ORCHESTRATION.md`. Not required to train locally.
