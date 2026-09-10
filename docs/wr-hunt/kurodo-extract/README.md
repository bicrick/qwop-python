# Kurodo WR extract assets

Artifacts from reverse-engineering [kurodo1916’s 45.530s HTML5 WR](https://www.speedrun.com/qwop/runs/y9vk0k2m) ([YouTube](https://youtu.be/4g9x7QJYx0M)).

## What’s here

| File | What it is |
|------|------------|
| `timeline.csv` | Per-frame Q/W/O/P pressed (0/1) over the WR run (~60 Hz sampling) |
| `timeline.json` | Compact / derived timeline summary |
| `extract_timeline.py` | Script that built the timeline from video frames (UI button “pressed vs up” look) |
| `convert_kurodo_rec.py` / `convert_kurodo_full.py` | Convert timeline → qwop-python `.rec` for open-loop replay |
| `analyze_gait.py` | Infer stride / gait cycle structure from the press stream |
| `GAIT_NOTES.md`, `FLEX_IMITATION.md`, `REC_NOTES.md`, `TIMING_SWEEP.md`, `FASTER.md` | Working notes: why literal timing failed, soft gait imitation, speed ideas |
| `examples/` | Button-state templates + LiveSplit finish overlay crop |

## How we used it

1. **OCR / template match** the in-game Q W O P button chrome (pressed vs released), not the runner silhouette.
2. Build `timeline.csv` → try open-loop `.rec` replay in sim → **faceplants** (physics + timing not 1:1).
3. Shift to **flexible gait imitation**: soft QO→WP phase structure, not timestamp lock (`FlexibleGaitImitationWrapper` + `train_ppo_kurodo_gait*.yml`).
4. Later: read **LiveSplit** overlays from the same video for segment splits — see `../KURODO_WR_SPLITS.md`.

The source video is **not** checked into git (size / copyright). Re-download from the YouTube link above if you need frames.
