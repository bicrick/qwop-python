# Winning recipe — official browser WR 45.167 HUD

**Date:** 2026-09-10 ~04:37 UTC (23:37 CT Sep 9)  
**Artifact:** `gs://qwop-wr-training/artifacts/spectate/spectate-direct-hunt/wr-hud-45.167-20260910-043741.*` (+ `-FULL.mp4`)  
**Human WR beaten:** kurodo1916 **45.530** → our keep **45.167** (−0.363s)

## One-line difference

We stopped training against a **fake dive-start**, put the **finish-leader flex-gait PPO** on the **official browser** with **settle spawn**, and rolled **stochastically** until a **WR-class start (7.60s to 10m)** stuck the landing.

## Exact stack that scored it

| Layer | Setting |
|-------|---------|
| Train run | `gait1-fps2strideearly1-20260909-2342` |
| Train family | fps2stride + **FlexibleGaitImitationWrapper** + **EarlySurvivalWrapper** |
| Checkpoint on spectate | **`model_118000000_steps.zip`** (md5 `473901680b722b51887462b1280f33da`) |
| Env clock | `frames_per_step=2`, Box2D `0.04`, score `1/30` |
| Browser | Official `QWOP.min.js` + `rl_direct.js` |
| Physics | **`TRAIN_PHYSICS=0`** (stock HTML5) |
| Reset | **`settle_spawn` / `DIRECT_SETTLE_SPAWN`** — planted, velocities zeroed, clocks zeroed |
| Policy sampling | **`deterministic=false`** (stochastic) |
| Spectate VM | `qwop-spectate-wr-hunt-20260909-1520` (never deleted) |

Config cousins in-repo: `config/train_ppo_gait_fps2stride_earlysurv.yml`, `config/env.yml` (`settle_spawn: true`), flex gait + early survival wrappers.

## Episode splits (this keep)

| Segment | Seconds |
|---------|--------:|
| 0–10m | **7.600** |
| 10–50m | 17.000 |
| 50–80m | 12.000 |
| 80–100m | 8.333 |
| 100→finish | ~0.233 |
| **HUD finish** | **45.167** |

Distance **100.57m**, `success=true`, 678 policy steps.

## What changed vs the 46.100 PB era

| | Browser PB 46.100 | WR keep 45.167 |
|--|------------------:|---------------:|
| Start 0–10 | **8.80** | **7.60** (−1.20) |
| Mid 10–50 | 16.40 | 17.00 (+0.60) |
| Late 50–100 | ~20.67 | ~20.33 |
| Finish | 46.100 | **45.167** |

The PB already had Python-class mid pace. The WR was almost entirely a **better first 10m** under settle — matching Kurodo’s LiveSplit start (~7.64) instead of our soft 8.8–9.4 median.

## What did *not* produce this keep

- **StartPace** fine-tune (`start1`) was still above the ~7.5 browser gate (best settle `split_10m` ~8.3+) and was **not** on spectate.
- Settle-**OFF** Python “43.6s” finishes — dive-start artifact; same zip faceplants or slows when settled.
- Literal Kurodo key timelines / open-loop `.rec` imitation alone.

## Recipe to reproduce (ops)

1. Continue early1-class zip with flex gait (+ optional EarlySurvival); do not reseed a plateaued parent.
2. Keep spectate on **official physics + settle**, pointing at the finish-leader zip.
3. Hunt **stochastic**; keep only HUD < 45.530 with full sequential frame video.
4. Judge starts on **browser `t_0_10`**, not Python settle-OFF times.

## Related docs

- [METHODOLOGY.md](./METHODOLOGY.md) — full loop story  
- [STRATEGIES.md](./STRATEGIES.md) — era matrix  
- [KURODO_WR_SPLITS.md](./KURODO_WR_SPLITS.md) — human WR LiveSplit  
- [SEGMENT_GAP_POST_SETTLE.md](./SEGMENT_GAP_POST_SETTLE.md) — why start was the hole  
