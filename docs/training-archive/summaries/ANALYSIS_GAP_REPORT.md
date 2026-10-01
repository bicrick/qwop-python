# Browser vs Python QWOP gap analysis (2026-09-09 / 10)

## Scope / caveats
- Spectate VM `qwop-spectate-wr-hunt-20260909-1520` `direct.log` was **truncated at 00:51 UTC** on restart (model refresh). **No historical drop lines** in syslog/GCS — death distribution is from the **post-restart window only** (n≈49 as of analysis).
- Finish artifacts: **321 JSON** under `/workspace/analysis-gap/finishes` (GCS keep-if-HUD&lt;70); **84 under 50s**.
- Hunt config: `TRAIN_PHYSICS=0` (official JS Box2D dt=0.04), `fps=2`, stochastic.
- No new trainers / no hunt disruption. Split-logging patch drafted only.

## (a) Death distribution (browser, current direct.log)

| Bucket | Count | % of all eps | Median HUD (drops) | Median dist |
|--------|------:|-------------:|-------------------:|------------:|
| 0–5m   | 31 | 63.3% | 4.27s | 2.82m |
| 5–10m  | 2  | 4.1%  | 9.58s | 8.15m |
| 10–20m | 1  | 2.0%  | 16.7s | 17.1m |
| 20–50m | 0  | 0%    | — | — |
| 50–80m | 6  | 12.2% | 29.6s | 55.1m |
| 80–100m| 1  | 2.0%  | 50.8s | 88.7m |
| Finish (≥100m) | 8 | **16.3%** | min 47.5 / med 51.9 (this window) | — |

- **Early HUD&lt;10s rate: 65.3%**
- **0–5m faceplant dominates** (75.6% of drops). Secondary mode: **50–80m** (14.6% of drops).
- All-episode median distance ≈ **3.2m** (start is the typical outcome).

Plot: `/workspace/analysis-gap/browser_death_dist.png`

## (b) Conditional-on-finish pace (browser)

- Best browser finish: **46.133s** (692 steps). Steps match `steps ≈ HUD/(2/30)` exactly (fps=2).
- Under-50s finishes (n=84): median **48.83s**, mean 48.51s; best-10 all ~46.1–47.0.
- Avg speed best ≈ **2.18 m/s** vs Python best 100/43.672 ≈ **2.29 m/s**.
- Finish HUD hist: `/workspace/analysis-gap/browser_finish_hist.png`, CSV `/workspace/analysis-gap/finish_pace.csv`.
- **No measured browser 10/50/100 splits** (finish JSON lacks them; sparse mp4 only covers ~0.3–1.1m screenshots).

### Open-loop .rec replay in Python Box2D (top 10 under-47s)
- **10/10 fall early** in Python: dist **0.9–1.0m** (one at 3.6m), HUD ~1.67–1.73s.
- Same action prefixes start `3,3,3,8,8,8…` then diverge; closed-loop browser sequences are **not open-loop transferable**.
- Results: `/workspace/analysis-gap/replay_results.json`

## (c) Python splits (TB)

### gait1-fps2strideearly1 (best user/time **43.672** @ step ~97.1M)
| Metric | min | p10 | median | last50 med |
|--------|----:|----:|-------:|-----------:|
| split_10m | 6.823 | 6.862 | 6.983 | 6.947 |
| split_50m | 23.209 | 23.373 | 23.651 | 23.564 |
| split_100m| 43.403 | 43.675 | 43.987 | 43.940 |
| user/time | **43.672** | 43.981 | 44.284 | 44.231 |
| success_rate | — | 0.75 | 0.96 | 0.96 |

Best-episode segments (paired at best time step):
- 0–10: **6.833s**
- 10–50: **16.392s**
- 50–100: **20.179s**
- total: **43.672s**

### gait1-fps2stride14 (best user/time **43.758**)
- s10 min 6.808 / med 7.019; s50 min 23.214; s100 min 43.461; success med ~0.94

Detail JSON: `/workspace/analysis-gap/tb_splits_detail.json`

Local closed-loop smoke (early1 zip, **no** reward wrappers — dynamics only): stochastic finish_rate ~0.40 with many 0–5m falls; deterministic worse (locks into 5–10m falls). TB success ~0.9 is higher than this bare eval — treat TB as training-distribution reference; bare eval still shows **start fragility exists in Python too**, but browser finish_rate (16%) is clearly worse than TB.

## (d) Where the ~2.3–2.5s finish gap most likely lives

**Two different gaps:**

1. **Reliability / early death (dominant operational issue)**  
   Browser: **~63% die in 0–5m**, finish ~16%. This is **start-dominated**, consistent with open-loop .rec→Python faceplants at ~0.9m and with `rl_direct.js` comments about start parity. Mid-race (50–80m) is secondary (~12% of eps).

2. **Pace gap conditional on finish (~46.13 vs ~43.67 = +2.46s)**  
   **Cannot be localized from measured browser splits** (none logged).  
   If the gap were uniform (scale 46.133/43.672 ≈ 1.056), hyp segment contributions would be roughly:
   - 0–10: **+0.38s**
   - 10–50: **+0.92s**
   - 50–100: **+1.13s**  
   i.e. **mid+late would hold most of a uniform gap** — but this is **hypothesis only** (`segment_hypothesis.png`).  
   Evidence against “late-only”: open-loop divergence and death mass at start say **start dynamics already disagree**; finishers may also be paying a start tax (recovery / slower first 10m) that we cannot yet measure.

**Most likely overall picture:**  
- High early faceplant rate → **start** (browser vs trained Python start / stochastic recovery).  
- Best-finish +2.5s → **unknown mix**; prior is mid/late if uniform, but **instrument splits before concluding**. Do **not** attribute the pace gap to late race without data.

## (e) Recommended next experiment (after evidence; do not ship long outage yet)

**Next: add split logging + log rotation on spectate (short restart), then collect ≥200 episodes / ≥30 finishes with `split_10/50/100`.**  
Draft: `/workspace/analysis-gap/DRAFT_split_logging.txt`  
- Enables (b)/(d) properly.  
- Optional A/B after that: brief `trainphysics=1` compare on **same** model (note: only 4 old TP=1 finishes exist, all slow 58–60s under earlier model — not informative).  
- **Do not** launch new GCP trainers or swap fleet until splits localize the finish pace gap.

## Artifact paths
- `/workspace/analysis-gap/drop_summary.json`, `episodes.csv`
- `/workspace/analysis-gap/finish_pace.csv`, `finishes/`
- `/workspace/analysis-gap/replay_results.json`, `recs/`
- `/workspace/analysis-gap/tb_summary.json`, `tb_splits_detail.json`, `tb/`
- `/workspace/analysis-gap/browser_death_dist.png`, `browser_finish_hist.png`, `segment_hypothesis.png` (if generated)
- `/workspace/analysis-gap/DRAFT_split_logging.txt`
- `/workspace/analysis-gap/direct.log` (snapshot)
