# Segment gap post-settle — where we lose time

**Date:** 2026-09-10 (UTC) / evening CT  
**Scope:** analysis only (no trainer swaps; spectate VM untouched aside from read/scp of logs+model).  
**Clocks:** browser HUD; Python `user/time` / `info["time"]` = `score_time` (HUD). fps=2 → steps×2/30 ≈ HUD.

## Headline answer

**~2.5s Py→browser is almost entirely the first 10m (+1.98s). Mid-race (10–50m) is matched. Late adds ~0.5s.**

Causal evidence: **`settle_spawn` (live on browser) removes the dive-start the policy was trained on.** Same zip, settle OFF in Python recovers the TB ~43–44s / ~6.8s-to-10m profile; settle ON shifts Python finishes into the browser regime (~9s start, ~46–48s finish) or kills finish rate.

**Browser→WR (~0.57s)** is not a mid-pace ceiling on the PB run — mid already equals Python. Residual is start still soft (8.80 vs Py 6.82) plus a smaller late/finish tax.

## Segment table (seconds)

| Segment | Py best (early1 TB / nosettle eval) | Browser best (46.100) | Browser finish median (n=85) | Py settle median (early1 105M, n_fin=12/40) |
|---------|--------------------------------------:|----------------------:|-----------------------------:|---------------------------------------------:|
| **t_0_10** | **6.82** | **8.80** | **9.40** | **9.63** |
| **t_10_50** | **16.44** | **16.40** | **17.80** | **17.37** |
| t_50_80 | ~11.80 (local best) | 12.53 | 14.00 | 12.17 |
| t_80_100 | ~7.53 (local best) | 8.13 | 8.60 | 8.33 |
| **t_50_100** | **20.19** | **20.67** | **23.07** | **20.47** |
| t_100_finish | 0.14 | 0.23 | 0.60 | 0.45 |
| **finish** | **43.592** | **46.100** | **51.367** | **47.650** |

Sources:
- Py best splits: early1 TB `user/split_*` at best `user/time` 43.592 (step ~102.97M); local nosettle eval of early1 105M / spectate_live reproduces ~6.8 / 23.x / 43–44.
- Browser: `gs://.../episodes.ndjson` (85 finishes with splits after split-logger deploy). Best JSON: `finish-hud-46.100-20260910-024911.json`.
- Older sub-46.5 JSONs (46.133 / 46.167 / …) predate split fields — only HUD/steps.

### Py best (TB early1) vs browser best — delta

| Segment | Δ (browser − py) | Share of +2.508s |
|---------|-----------------:|-----------------:|
| t_0_10 | **+1.978** | **~79%** |
| t_10_50 | −0.039 | ~0% (matched) |
| t_50_100 | +0.475 | ~19% |
| t_100_finish | +0.094 | ~4% |

## Same-policy transfer (settle ON vs OFF)

| Cohort | Finish rate | Best finish | Med t_0_10 | Med finish |
|--------|------------:|------------:|-----------:|-----------:|
| Spectate live zip, **settle OFF** | 15/15 | 43.233 | 6.867 | 43.833 |
| Spectate live zip, **settle ON** | **0/25** | — | — | — |
| early1 105M, **settle OFF** | 20/20 | 42.800 | 6.867 | 44.450 |
| early1 105M, **settle ON** | 12/40 | 46.433 | 9.633 | 47.650 |
| Browser (settle live) | 85/819 (~10% in this window) | 46.100 | 9.400 | 51.367 |

Browser reset path confirmed: `DIRECT_SETTLE_SPAWN()` in `/opt/qwop-spectate/rl_direct.js` (zero velocities, zero scoreTime/score after plant).

**Interpretation:** the famous 2.5s gap is mostly **distribution shift at t=0**, not a uniform Box2D slowdown. Once a settled episode locks gait, 10–50m times match Python’s best.

Py-settle medians vs browser medians (finished episodes only) are close on start (9.63 vs 9.40); browser median is slower mid/late (more degraded finishes in the long tail).

## Velocity / start vs mid bottleneck

| Metric (finished eps) | Py nosettle (early1 105M) | Py settle (early1 105M) |
|-----------------------|--------------------------:|------------------------:|
| max torso vx 0–10m (median) | **21.8** | **18.4** |
| mean torso vx 0–10m (median) | **11.9** | **8.4** |
| max torso vx 10–50m (median) | 25.7 | 24.9 |
| mean torso vx 10–50m (median) | 19.9 | 19.3 |

**Bottleneck = start acceleration / first-10m speed, not mid-race cruise.** Mid max/mean vx nearly identical once upright. Settle cuts early mean vx by ~30% and costs ~2s by 10m.

## Action histogram (optional, closed-loop)

Best browser `.rec` (46.100) vs one Python nosettle finish (spectate_live):

- **Mid 10–50m:** both dominated by actions **2** and **9**; switch rate ~0.67; mean hold ~1.5 steps — gait family matches.
- **First 10m:** browser more twitchy (switch 0.60, hold 1.65) vs Py dive-start (switch 0.49, hold 2.02). Same action family (2/8/7/13…), different cadence — consistent with fighting a planted start vs rolling into stride.

(Open-loop `.rec` replay still faceplants; do not use for physics claims.)

## Browser → human WR (45.530), ~0.57s

On the **46.100 PB**:
- Mid already Python-class (16.40).
- Start still +1.98 vs Py best; late 50–100 still +0.48.
- Across browser finishes, a **7.667** start exists (47.500 finish) but then bleeds mid/late — so start *capability* is partially there; combining fast start + clean mid/late is rare.

Likely WR slice: **~0.3–0.5s still available in a cleaner settled start**, remainder in late stability / lean to the line — **not** “need higher mid cruise.”

## Spectate log note

`direct.log` was rotated (few FINISH lines in the live file). Authoritative finish+split corpus is GCS `episodes.ndjson` (85 finishes). Live FINISH lines do print `splits={split_10m,...}` when present.

## What NOT to do

- More identical stride reseeds / continue zips into spectate without addressing settle-start.
- Blind open-loop `.rec` replay as a physics diagnostic.

## Next experiments (≤3)

1. **Settle-aware start fine-tune (primary):** continue from current zip with `settle_spawn=True` and heavy early-survival / 0–10m time shaping (or BC from browser finishes with t_0_10 ≤ 8.5). Goal: recover ≤7.5s-to-10m *under settle*, keep mid gait. Measure Py settle + browser medians on t_0_10.
2. **Spectate A/B settle ON vs OFF (confirm causal, no train):** same model, N≥50 attempts each; report finish rate + median/best t_0_10 / finish. Expect OFF ≈ Py 43–44, ON ≈ current 46+.
3. **Late-only polish only after start is fixed:** if (1) lands ~7.5–8.0 start on browser, then target t_50_100 (currently +0.5 vs Py) / finish lean — not before.

## Artifacts

- Browser splits: `/workspace/qwop-gap-analysis/browser-finishes/episodes.ndjson`, top JSONs under `browser-finishes/`
- Py evals: `python_eval_early1_105M_{settle,nosettle}.ndjson`, `python_eval_spectate_{settle,nosettle}.ndjson`
- early1 TB summary: `early1_tb_summary.json`, events in `tb-early1/`
- Models: `models/early1_105M.zip`, `models/spectate_live.zip`
- Eval script: `python_split_eval.py` (`SETTLE=0|1`)
