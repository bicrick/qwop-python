# Kurodo1916 WR splits (45.530 HUD)

**Source:** [SRC run y9vk0k2m](https://www.speedrun.com/qwop/runs/y9vk0k2m) · video [youtu.be/4g9x7QJYx0M](https://youtu.be/4g9x7QJYx0M)  
**Extracted:** 2026-09-10 — LiveSplit overlay OCR from finish frame (`frames/ls_050.png`). SRC API `splits: null`.  
**Also:** Kurodo holds the **10 Meters** board at **7.067s** (separate category).

## Cumulative / segment (LiveSplit)

| Dist | Cum (s) | Seg (s) |
|-----:|--------:|--------:|
| 10 | **7.64** | 7.64 |
| 20 | 12.12 | 4.47 |
| 30 | 16.12 | 3.99 |
| 40 | 20.18 | 4.06 |
| 50 | **24.38** | 4.20 |
| 60 | 28.75 | 4.36 |
| 70 | 33.15 | 4.40 |
| 80 | **37.28** | 4.13 |
| 90 | 41.33 | 4.05 |
| 100 | **45.53** | 4.20 |

Gold / SoB on overlay: **42.51**. Overlay WR flipped to “by me” at finish; PB was 45.86 going in.

## Segment buckets (match our gap analysis)

| Segment | Kurodo WR | Browser PB 46.100 | Δ (us − WR) | Py best nosettle 43.592 |
|---------|----------:|------------------:|------------:|------------------------:|
| **t_0_10** | **7.64** | **8.80** | **+1.16** | 6.82 |
| **t_10_50** | 16.74 | 16.40 | −0.34 | 16.44 |
| t_50_80 | 12.90 | 12.53 | −0.37 | ~11.80 |
| t_80_100 | 8.25 | 8.13 | −0.12 | ~7.53 |
| **t_50_100** | 21.15 | 20.67 | −0.48 | 20.19 |
| **finish** | **45.53** | **46.100** | **+0.57** | 43.592 |

## Headline

**We lose the WR on the start only.** Mid and late we are already *faster* than Kurodo on the PB run.

- Browser start is **+1.16s** vs WR (8.80 vs 7.64). That more than eats the whole **+0.57s** finish gap.
- 10–50 and 50–100 we are **ahead** of WR (−0.34 / −0.48).
- Hybrid: WR start + our post-10m pace → `7.64 + (46.100 − 8.80) = **44.94**` — ~0.6s under WR without needing his mid/late.
- His own 10m board (**7.067**) shows another ~0.57s of start headroom vs this WR’s 7.64.

Py nosettle 6.82 start is **faster than WR** but is the dive-start artifact; settle-ON / browser reality is the 7.6–9s band. Target for start1: settle-ON `split_10m` ≤ **~7.5** (WR-class), then browser-gate — don’t promote on Python alone.

## Context (Kurodo blog 2021)

First 10m historically **+2.5–3.0s** slower than other 10m segs. He later shifted practice off start-spam after seeing humans/AI beat him mid despite him winning the start. Matches our finding: cruise is solved; plant→accelerate is the WR lever.

## Files

- `kurodo-wr.mp4` / `.webm` — local copy of the SRC video
- `frames/ls_050.png`, `livesplit-finish-2x.png` — finish LiveSplit crop
- Compare baseline: `../SEGMENT_GAP_POST_SETTLE.md`
