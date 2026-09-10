# What actually makes a 45–47s QWOP gait, and the next three knobs

Clock: HUD seconds only. Video time on the kurodo capture matches HUD
(race window video t=2.0–47.47s, LiveSplit 45.530s). Python `info["time"] / 1.2`
is HUD. Do not compare raw W&B protocol time to 45.53.

Trusted parent: `config/train_ppo_kurodo_gait.yml`. Best trusted finish
**51.062s HUD** (`gait1-controlr-20260908-0830`, still falling at the 8M cap).
Open-loop QP-then-WO at 1.0s finishes, but only at 133.2s HUD
(`data/recordings/kurodo_gait_best.rec`). Same-leg QO-then-WP does not walk
here. Do not retarget the pair.

Human WR 45.530s HUD is kurodo1916 (speedrun.com `y9vk0k2m`). Cited machine
WR is Liao's prioritized DDQN, 47.34s HUD (2021). No later verified machine
record below that turned up. Speedrun.com is human-only; gunmaneko is 45.630.

## 1. Mechanical differences, 51s vs 45–47s

Numbers below are from `/workspace/qwop-wr-extract/timeline.csv` (the 45.530
capture, race window after video t=2.0, 60 fps). Average WR speed is
`100 / 45.530 = 2.196 m/s`. A 51.062s finish is `1.958 m/s`. That 0.24 m/s
is almost all cruise, not the start (see below).

### Cadence is slower and the stride is much longer

Q-rise to Q-rise on the WR tape: 34 intervals, median 1.725s. The stride
cycles (≥1.0s) are n=21, median **1.767s**. Short 0.37s intervals are
correction blips, not the running cadence (already noted in `GAIT_NOTES.md`).

At 2.196 m/s a 1.767s cycle covers **~3.88 m** (~1.94 m per step). The flex
wrapper's sweet spot is `ideal_half_s: 0.50` (1.0s full cycle). A 51s policy
locked to that rhythm only needs ~1.96 m/cycle — half the WR stride. The
133.2s open-loop is the same 1.0s period at 0.75 m/cycle. Shortening the
half-cycle (0.45 → 54.3s, 0.42 → 54.8s) already went the wrong way: the WR
is not a faster tap rate.

Sources: this tape; kurodo, [スピードラン入門](https://kuro1san.hateblo.jp/entry/2025/05/06/175605)
(do not overstride the first step, but the speed form lands the foot moving,
slightly behind the hip, before the COM drops — that is a long airborne step,
not a chopped march).

### Calf is a short double-tap; the thigh stays down

Hold lengths on the WR tape:

| key | n | median | short | long |
|-----|--:|-------:|-------|------|
| Q | 35 | 0.70s | 34% <0.20s | 63% ≥0.40s |
| W | 28 | 0.83s | 4% <0.20s | 79% ≥0.40s |
| O | 46 | 0.167s | 59% <0.20s | 4% ≥0.40s |
| P | 58 | 0.100s | 52% <0.12s, 60% <0.20s | 7% ≥0.40s |

About **two P rises and two O rises per long Q-cycle** (P median 2, mean 2.14
on 21 long cycles). That matches kurodo's speed form, not a glued chord:
press the calf to drop/extend the foot, release, tap again at plant to kick.
"Knee long-press is almost unnecessary." Thigh control stays the basic hold.

`hold_full_s: 0.40` pays a full hold bonus for 0.40s of a QP/WO beat. That is
the open-loop chord (Q [0, 0.28), P [0.05, 0.32)), not this tape. Exact QP
is only 8.3% of race samples; lone Q is 18.3% and lone W is 21.9%.

Sources: this tape; kurodo 2025 blog (knee input time reduced; two calf taps
per step); earlier 50.834 writeup summarized by
[Denfaminicogamer](https://news.denfaminicogamer.jp/news/200831b) (W drop thigh
→ P bend to plant → O extend, to add foot speed at landing).

### Overlap is brief and staggered, and the video pair is not the sim pair

Measured co-hold: QP overlap median **0.10s**, P rises 0.067s after Q.
WO overlap median **0.133s**, but O lags W by **0.317s** (thigh leads, calf
is a late tick). Same-leg QO/WP occupy more of the tape than QP/WO
(QO 11.0%, WP 14.5% vs QP 8.3%, WO 7.7%). That is the HTML technique.

It does not transfer. Same-leg QO-then-WP stuck near 1.7 m in this Box2D env.
The pairing that finishes is cross QP-then-WO. Keep that pair. What is
missing is the *shape* of the beat: thigh leads, calf is a 0.10–0.17s tick,
not a simultaneous chord the bonus prefers (`soft_hold_scale: 0.55` pays
the lone thigh about half of the exact chord).

Sources: this tape; `GAIT_NOTES.md` / `FLEX_IMITATION.md`.

### Flight is a 0.20–0.31s release, not a held chord

`none` is 12% of the race. Release runs median **0.20s**, p75 0.26s, p90
0.31s (mid-race video t=8–42: median 0.20s, 37% ≥0.20s, max 0.30s). Kurodo:
release the instant the foot leaves the ground — further hold does not push
— and time the next press so the foot arrives before the COM falls.

`none_grace_s: 0.22` is the median release. Anything longer stops advancing
beat age, and `none_reset_s: 0.45` wipes the beat. The bonus therefore
prefers staying on the keys, which is how the 1.0s open-loop walks slowly.
Liao's missing human trick, before the speed pass, was the same thing:
"swinging the legs upwards and forwards" for extra momentum. His first
self-play, with torso-height and knee-bend penalties, never found it and
knee-walked.

Sources: this tape; kurodo 2025 blog (release on liftoff; land before COM
drop; keep COM up); Liao,
[Medium](https://medium.com/data-science/achieving-human-level-performance-in-qwop-using-reinforcement-learning-and-imitation-learning-81b0a9bbac96)
and the [47.34 video](https://www.youtube.com/watch?v=82sTpO_EpEc).

### The seconds are in the cruise. Start is a short WO. Hurdles are off here.

Start on this tape, video t=2.017–3.4: lone O 2.017, WO until 2.350, W,
then **none 2.417–2.817**, then Q / short QP. First WO hold is ~0.30s, then
a 0.40s release. Left-foot (WO) start, release when the foot floats, do not
lengthen step 1. Kurodo: fix a start clock, but start practice does not
buy the record; the running form does.

His 2021 note is the 51 vs 45 split. First 10 m is **2.5–3.0s slower** than
later 10 m splits. Comparing his 50.834, the then-human 48.340, and Liao
47.340: the AI was **slowest at 10 m** and faster on every segment after.
The 51→45 gap is mid-race velocity, not a new start.

Hurdle (50 m): charge it, or kick it clear; slowing down is the stable but
slower option, and kicking it off the map stops working as speed rises.
`HURDLES_ENABLED` is false in this env. The 51.062s finish has no hurdle to
clear. Do not turn hurdles on as a speed knob.

Sources: this tape start events; kurodo
[2021 annual](https://kuro1san.hateblo.jp/entry/2021/04/22/213754) (10 m
splits, AI slower at 10 m then faster); kurodo 2025 blog (left-foot start,
short first step, three hurdle options).

### Action tick is coarser than the calf tap

`frames_per_step: 4` holds each action `4/30 = 0.133s` HUD. P's median hold
is 0.100s and 52% of P holds are shorter than one action. Liao's speed agent
raised effective frame rate from 9 to 18 and 25 Hz specifically so those
taps and the liftoff release were representable. Our existing
`train_ppo_kurodo_fps2.yml` is not that test: it also set speed 0.6,
time_cost 14, n_envs 8, and a short half. That stack is the one that
jumped and fell.

## 2. What the parent / flex wrapper still does not encode

Already encoded, leave it:

- Cross QP-then-WO, not same-leg. Correct for this sim even though the tape
  is same-leg-heavy.
- Soft one-key credit exists (staggered lead-in is allowed).
- Upright gate at 1.15 m, so a crawl does not collect the gait bonus.
- Light both-thigh / same-direction / scrape breakers. Distance stays primary.
- No locked 0.2s start delay (good — the tape's pause is a start pose, not a
  cycle phase).

Not encoded, and this is the 51 vs 45 gap:

| WR mechanic | parent now | tried already |
|---|---|---|
| 1.77s cycle, ~3.9 m stride | `ideal_half_s: 0.50` pays a 1.0s cycle | shorter half 0.42 / 0.45 finished 54–55s. Do not shorten again. |
| calf double-tap ~0.10–0.17s, thigh stays | `hold_full_s: 0.40` pays a glued chord; exact pays more than lone thigh (`soft_hold_scale: 0.55`) | no calf-only term exists |
| 0.20–0.31s flight release is part of the beat | `none_grace_s: 0.22` clips the long half of releases | not tried |
| action tick finer than a 0.10s P tap | `frames_per_step: 4` (0.133s) | isolated fps=2 not tried; stacked fps2 was worse for other reasons |
| high COM as the speed form | only a scrape penalty once already low | no positive flight / COM term |
| cruise, not start; no hurdle in this sim | uniform distance + speed; hurdles off | speed_rew 0.35 finished 53.77s; 0.25 stuck ~132s; 0.30 was a mid-run, not a trusted finish. Do not crank speed_rew. |
| keep self-play after the stride exists | 8M cap, then reseed from scratch | reseeds of the parent finished 52.2s and 52.5s, worse than the seed that was still falling |

No yaml knob pays foot speed at plant, a second calf tap, or hip-swing
amplitude. Do not add that code in the same breath as a one-knob run.
The three configs below are the closest single yaml edits that point at
flight, calf shape, and action precision without changing the pair or the
0.50s attractor that already finishes.

## 3. Three one-knob configs

Each is a copy of `config/train_ppo_kurodo_gait.yml` with one field changed.
From scratch. No checkpoint. Do not stack them. Do not also raise
`speed_rew_mult` or cut `ideal_half_s`. Cap them like the parent (8M on the
worker). Score HUD `split_100m` only.

### A. `config/train_ppo_gait_fps2.yml`

- Knob: `env_kwargs.frames_per_step: 4 → 2` (action dt 0.133s → 0.067s HUD).
- Why it should lower HUD: 52% of WR P holds are shorter than one parent
  tick. The kick-at-plant and the liftoff release cannot be aimed until the
  tick is finer. Liao's 47.34 pass did this (9 Hz → 18/25) *after* the
  stride existed; we only have the from-scratch knob, so keep every other
  parent field so the QP-then-WO attractor stays.
- Why it should not collapse: the gait bonus, switch window, and speed
  weight are unchanged. This is not the stacked fps2 file.
- Watch: 8M steps at fps=2 is half the HUD-seconds of practice. If finish
  time is still falling at the cap, that is the continue-training signal,
  not a reason to add a second knob in this yaml.

### B. `config/train_ppo_gait_nonegrace032.yml`

- Knob: `env_wrappers.kwargs.none_grace_s: 0.22 → 0.32`.
- Why it should lower HUD: WR mid-race releases run 0.20–0.31s and are the
  airborne coast that turns a 1.0s cycle into a longer step. Today the
  median release still counts, but the fast half of them freeze beat age
  and start to look like a dropped gait. 0.32 covers the tape p90 without
  touching `none_reset_s: 0.45` (a real stall still clears) or the 0.28–0.85s
  switch window. The 0.50s half can then include a float and still collect
  the switch bonus. That is the encoded version of "release on liftoff."
- Why it should not collapse: keys-down still pay hold; only the gap between
  beats is treated more kindly. No change to pair, cadence target, or
  speed weight — the three things that made stacked sub45 runs jump.

### C. `config/train_ppo_gait_softhold090.yml`

- Knob: `env_wrappers.kwargs.soft_hold_scale: 0.55 → 0.90`.
- Why it should lower HUD: the tape's working state is a lone thigh (Q 18%,
  W 22%) with a 0.10s calf tick, not an exact chord (QP 8%, WO 8%). Exact
  still pays 1.0, so a short overlap remains better than never using the
  calf. Raising the lone-thigh scale stops the bonus from demanding a 0.27s
  glued P/O, which is the open-loop hold and the thing `hold_full_s: 0.40`
  is currently celebrating. Long thighs (0.70–0.83s) keep their pay; cutting
  `hold_full_s` would have clipped those and is the wrong single knob.
- Why it should not collapse: the beat identity (QP-family then WO-family)
  is unchanged, and same-leg still gets nothing. The agent can still learn
  the kick because exact is strictly better and distance is still the large
  term.

Do not run next: another `ideal_half_s` cut, `speed_rew_mult` above 0.2,
`n_envs` 6, hurdles on, or a same-leg bonus. Those are either already slower
or they change the thing that finishes.

## 4. Continue the 51.062s policy to 16–24M. Do not reseed it again.

Yes. Continue `gait1-controlr-20260908-0830` on the parent yaml
(`model_load_file` pointed at that run's checkpoint,
`reset_num_timesteps: false`, same rewards, cap 16M then 24M if HUD is
still falling). That is a higher-value use of a slot than a fourth from-scratch
reseed. The three yamls above are the next *new* objectives, not a
substitute for this.

Evidence it was truncated, not done:

- That seed was still dropping at the cap (ITERATE: ~54.1s at 5.4M, **51.062s
  at 8M**). The worker ended it. It did not plateau.
- Same recipe, other seeds, finished 52.20s and 52.50s at 8M. Seed noise is
  51–54s. More draws of the same start are not finding 45. The best draw
  was the one we stopped early.
- `speed_rew` 0.35 from scratch finished 53.77s. Stronger speed pressure
  without the already-learned 51s behavior does not buy cruise speed.

Evidence from public runs that longer self-play on a striding policy beats
a new objective:

- Liao's 47.34 was not a fresh agent with a harder reward. ACER self-play
  (25h, then Kurodo buffer, then 25h more) first got a human stride down to
  68s. The record agent was that policy continued as prioritized DDQN for
  ~40h, almost all self-play, after a couple of minutes of pretrain. Mixed
  demo injection was removed once the policy could not reconcile it. Taking
  the wheels off (drop torso-height, vertical, and knee-bend penalties;
  reward forward velocity only) was a *second stage on a policy that already
  strode*, and even then he kept the learned behavior as the init. From-scratch
  with no stride prior knee-walked. That matches our stacked sub45 runs
  (70–130s, jump/fall) and argues against reseeding plus a new objective.
- Kurodo 2021: after seeing Liao and the 48s human, he stopped resetting
  at a bad start and practiced the middle of the race. The AI's edge was
  10–100 m, not 0–10 m. More steps of the same forward reward, on a policy
  that already finishes, is the analogue. A new start term or a new cadence
  target is the thing he explicitly abandoned.
- Heess et al. 2017 (the locomotion paper Liao cites): once a gait exists,
  speed keeps climbing for a long time under a forward-progress reward if
  you do not reset the policy. Reseeding throws away the value function that
  has started to prefer the fast subset of 51s trajectories.

Do not, on the continue run, also drop scrape, raise speed_rew, or cut the
gait bonus. That is Liao's second agent, and we have not yet shown the 51s
weights can survive a reward change. Identical objective, more steps, HUD
finish as the only score. If it flatlines between 12M and 16M (best HUD
unchanged for ~4M), then stop and spend the slot on config A or B, still
not on a stack.
