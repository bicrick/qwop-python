# Flexible gait imitation

This is not a replay of a press timeline and not a clone of open-loop
timestamps. The learner starts from scratch and is paid mostly for going
forward. A small bonus prefers the cross two-beat that actually finishes
in this sim.

## What open-loop search found

Same-leg **QO then WP** never walks here (stuck around 1.7 m). The cross
pairing that finishes 100 m is **QP then WO**:

- period 1.0 s HUD
- phase shift 0.5
- start delay 0.2 s (when the recording starts, not a required alignment)
- holds inside the cycle: Q [0, 0.28), P [0.05, 0.32), W [0.45, 0.84), O [0.48, 0.68)

Reference recording (finishes, **133.2 s HUD**, slow, not a world record):
`data/recordings/kurodo_gait_best.rec`

## What the reward pays for

1. **Primary — go forward.** The usual env reward is unchanged: distance
   along the track and HUD progress, plus the existing time cost and fall
   penalty. That term stays the main one. A meter gained is worth far more
   than a pretty chord.

2. **Soft gait bonus — only after the runner is upright** (torso height at
   least about 1.15 m). Then a small bonus for the two-beat **cross**
   pattern: a **QP-like** beat, then a **WO-like** beat, then back.

   Exact chords (Q+P, or W+O) pay the full hold. A lone Q or P on the QP
   side, or a lone W or O on the WO side, still counts for less — the
   open-loop holds stagger, so one key leads and one trails. Same-leg
   QO / WP get **no** bonus.

   There is no required phase offset and no required 0.2 s start delay.
   A half-beat near 0.5 s HUD is the sweet spot (full cycle ~1.0 s).
   Switching a bit early or late still scores. Only a jitter flip
   (under ~0.28 s) gets no switch bonus. Holding one chord forever stops
   earning the hold bonus.

3. **Light penalties for hard breakers only.** Both thighs commanded or
   swinging the same direction for a sustained stretch, and knee-scrape
   (low torso and bent knees) if that signal is present. These are small.
   They should not outweigh forward distance.

Full **16-action** set (`reduced_action_set: false`). Learner starts from
scratch: `model_load_file` is null. Do not load `expert_dqnfd.zip`.

## One-command train (headless GCP worker)

From the repo root on the GCP worker (`/opt/qwop/qwop-python` after
`startup.sh` installs the tree), with the venv active:

```bash
qwop-python -c config/train_ppo_kurodo_gait.yml --run-id job-kurodo-flex-gait train_ppo
```

Config path: `config/train_ppo_kurodo_gait.yml`

That is the same invocation `infra/gcp/startup.sh` builds when instance
metadata is:

- `train-config=config/train_ppo_kurodo_gait.yml`
- `train-action=train_ppo`
- `job-id=job-kurodo-flex-gait`

Optional step cap (startup appends this when `max-timesteps` is set):

```bash
qwop-python -c config/train_ppo_kurodo_gait.yml --run-id job-kurodo-flex-gait --max-timesteps 1000000 train_ppo
```

Do not launch this as a long local-only run. Enqueue / fleet create stays
with the orchestrator; this file only names the command the worker should run.
