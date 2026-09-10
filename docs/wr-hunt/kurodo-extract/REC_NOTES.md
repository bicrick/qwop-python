# kurodo_wr.rec — mapping and clock

Source timeline: `/workspace/qwop-wr-extract/timeline.csv` (video time, 60 fps).
Recording: `/workspace/qwop-python/data/recordings/kurodo_wr.rec`
No expert weights loaded. Replay used the registered local env only.

## Action set (confirmed)

Current training (`config/train_bc.yml`, `config/record_model.yml`) uses
`reduced_action_set: true`. `qwop_python/actions.py` reduced 9 is **not**
`none, Q, W, O, P, QO, QP, WO, WP`. `itertools.combinations` order, after
dropping QO, WP, and all 3–4 key combos:

| index | name | keys |
|------:|------|------|
| 0 | none | |
| 1 | Q | q |
| 2 | W | w |
| 3 | O | o |
| 4 | P | p |
| 5 | QW | q+w |
| 6 | QP | q+p |
| 7 | WO | w+o |
| 8 | OP | o+p |

Exact held states map through `ActionMapper.action_from_keys`. States outside
that set are projected by dropping keys (never inventing a press) until a legal
subset remains. Largest subsets first; ties follow `q,w,o,p` order, so the
same-leg pairs the reduced set calls redundant become thighs: **QO → Q**,
**WP → W**. Triples similarly: QWP/QWO → QW, WOP → WO.

Of 341 env steps, 91 had no exact reduced action (mostly WP→W 47, QO→Q 38).
That drops the calf on the same-leg holds that dominate the video, so the .rec
cannot reproduce Kurodo's inputs even before physics mismatch.

## Clock

- Video samples: 60 fps (`t_sec` step ≈ 1/60).
- HTML HUD: one `game.update()` advances `score_time` by `SCORE_TIME_STEP = 1/30`
  (`qwop_python/data.py`). That is one HUD frame, not `frames_per_step`.
- Box2D still steps `PHYSICS_TIMESTEP = 0.04` inside that same update.
- Current training holds each discrete action for `frames_per_step = 4`
  updates = **4 HUD frames = 4/30 s = 8 video frames**. `frames_per_step=4`
  is not one HUD frame, so the .rec is **not** written at 30 Hz. A 30 Hz
  recording replayed in the fps=4 env would stretch the race 4×.
- Assumption: sample the race window at the training env's action rate
  (7.5 Hz). Each .rec line is the majority 60 fps key tuple in an 8-frame bin.
  Ties broken by the sample nearest the bin midpoint.

## Race window

- Pre-roll before the metre counter is frozen and omitted (`env.reset` already
  starts the episode; leading `none` would only burn HUD time).
- Start: video t = 2.0 s (frame 120). First press is O at 2.01667 s, one video
  frame into the first bin, so that bin's majority is WO not a lone O.
- End: last press at 47.4 s (frame 2844) is included. Window is
  `[2.0, 47.46667)` s video time → **341 actions**. Completed HUD time would be
  `341 * 4/30 = 45.46667` s.
- Header `seed=42` matches other demo .rec files. It only reseeds Python/numpy;
  it does not reproduce the browser world.

## Replay (real run)

Registered `local/QWOP-v1` the same way as `train_bc`: `config/env.yml` plus
`frames_per_step=4`, `reduced_action_set=true`. Stepped the single episode
until `terminated` (pattern as `collect_transitions`).

| field | value |
|-------|--------|
| steps taken | 22 of 341 (ended at action index 21) |
| `info["time"]` | 2.8666666666666663 s HUD |
| `info["distance"]` | 0.6 m |
| fallen | True |
| `is_success` | 0.0 |
| jump_landed | False |
| split 10/50/100 | not reached |
| finishes 100 m | no |

The recording is saved. The sim did **not** transfer: the runner fell almost
immediately (0.6 m, ~2.87 s HUD). Do not treat this as a Kurodo demo that
walks. Likely causes: reduced-9 projection of QO/WP, 4-HUD-frame action
quantization, and Box2D vs HTML physics.
