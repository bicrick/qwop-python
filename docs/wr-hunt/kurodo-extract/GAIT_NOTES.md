# Open-loop gait from the kurodo timeline

Literal timestamp replay was stopped (see `TIMING_SWEEP.md`). Starts differ,
so this is a synthesized stride: phase order and duty from the press
timeline, then retuned in `local` physics. Full 16-action set
(`ActionMapper`, `reduced_action_set=false`). No expert weights.

All distances below are HUD `info["distance"]` (`round(torso_x) / 10`) from
a **fresh** `QWOPEnv` (`seed=42`, `frames_per_step=1`). Reusing one env
across episodes is not deterministic here (Box2D reset leftover); those
runs were discarded. The number in the saved recording section was replayed
from the `.rec` file on a new env and matched.

## What the timeline actually repeats

Source: `/workspace/qwop-wr-extract/timeline.csv`, race window after video
t=2.0. 60 fps. Q-rise aligned cycles split in two:

- Long cycles (the stride): n=21, median duration **1.767 s** (video).
- Short cycles (~0.37 s): QP blips. Treated as corrections, not the base cycle.

Long-cycle mode by phase (10 bins), full race:

| phase | mode state |
|------:|------------|
| 0.0–0.1 | Q |
| 0.1–0.3 | QO (same-leg) |
| 0.3–0.4 | Q |
| 0.4–0.7 | W |
| 0.7–0.9 | WP (same-leg) |
| 0.9–1.0 | W |

Duties on long cycles: Q ~0.42, W ~0.55, O ~0.23, P ~0.25.
O’s first rise is ~0.13 into the Q half; P’s main hold is late in the W half.
Q and W barely overlap in the mode (sim also treats Q/W and O/P as
if/else, so simultaneous pairs are illegal as two thighs or two calves).

Opening before the first Q (video t=2.02–2.42) is a short WO, then a pause.
That is a start pose, not the cycle. First clean Q-cycle is also cross-paired
(QP then WO), so both same-leg and cross pairs are in the tape.

## Generator

Not a copy of timestamps. One cycle of period `T` (HUD seconds; one
`game.update` is 1/30 s). Phase intervals, half-open:

**Family that walks (cross, from the first clean cycle and the opening WO):**

- Q `[0.00, 0.28)`, P `[0.05, 0.32)` → QP while both
- W `[0.45, 0.84)`, O `[0.48, 0.68)` → WO while both
- `phase_shift=0.5` so the episode starts on the W/O half
- `start_delay=0.2` s of `none` after reset, no extra pose

Mapped with `action_from_keys`. Conflicting Q+W or O+P never left in the spec.

**Same-leg family (mode bins: QO then WP)** was searched too (periods 1.05 /
1.5 / 1.77, shifts 0 and 0.5, with and without a WO start). On a fresh env
it did not walk past the literal replay. The sim accepts the cross pairing
that is also in the video, at a faster period than the 1.77 s median
(about 1.0 s HUD).

## Search

Fresh env each trial. Grid over period, start delay, phase shift, start pose
(none / WO / W), then calf/thigh phase widths once anything cleared ~10 m.

Same-leg peak stayed well under the 1.7 m literal replay. Cross with
`shift=0.5` was the one that stayed up. First reliable clear of 10 m was
period 1.0 s, delay 0, default cross spec, 14.0 m at 30 s HUD still upright
(split 10 m at 22.93 s). Tightening delay and the Q/P and W/O widths then
reached the finish.

## Best recording (disk replay)

`/workspace/qwop-python/data/recordings/kurodo_gait_best.rec`

| field | value |
|-------|--------|
| period | 1.0 s HUD |
| start delay | 0.2 s none |
| phase shift | 0.5 |
| spec | Q [0, 0.28), P [0.05, 0.32), W [0.45, 0.84), O [0.48, 0.68) |
| steps taken | 3996 (ended on `game_ended`) |
| `info["distance"]` | **100.0 m** |
| `info["time"]` | **133.2 s** HUD |
| fallen | **False** |
| jumped / jump_landed | True / True |
| `is_success` | 1.0 |
| split 10 / 50 / 100 | 17.067 s / 66.933 s / 133.2 s |

Actions actually emitted: none, Q, W, P, QP, WO (indices 0, 1, 2, 4, 7, 8).
Same-leg QO/WP are legal in this 16-set and were used in the same-leg
family; this winner does not need them. Q and W are not held together.

This is not a transferred Kurodo WR (45.5 s). It is an open-loop stride
inferred from that tape and retuned until the python env finishes 100 m.
Much slower than the video. The jump-landing success flag is the sim’s,
from this replay, not assumed.
