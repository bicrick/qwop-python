# Timing sweep — stopped before a new grid

The literal timestamp-replay sweep was **not run**. After the prior fps=1 / fps=4
replays, the request changed: do not treat the kurodo recording as gospel
timings (starts differ). Infer an abstract gait and retune period / phase /
start delay instead.

No new env distances from a start-offset × time-scale × hold-length grid.
Numbers below are the earlier real replays only (see `REC_NOTES.md` and the
full-16 converter run), not a sweep.

| setting | distance | HUD time | fallen | notes |
|---------|----------|----------|--------|-------|
| reduced-9, frames_per_step=4, majority bins | 0.6 m | 2.8667 s | yes | 22/341 steps; QO/WP projected away |
| full-16, frames_per_step=1, majority 2-frame bins, start video t=2.0 | 1.7 m | 7.17 s | yes | prior best literal replay |
| full-16, frames_per_step=4 | 0.6 m | (early) | yes | fell at 0.6 m |

Literal clock matching is abandoned. See `GAIT_NOTES.md` for the open-loop stride.
