# QWOP World-Record Experiments

Target: beat **45.530s** (train in Python, transfer to browser later).

These experiments encode techniques from WR / high-level QWOP play into
training configs and wrappers so we can iterate systematically. Mid-race
pace matters more than the start (Kurodo): use `split_10m_time`,
`split_50m_time`, and `split_100m_time` in env `info` / TensorBoard
(`user/split_*`) to judge progress between marks.

**Fall detection stays original JS:** head, arms, and forearms only — do
**not** add torso to fall contacts.

**Headless note:** `camera_x` must update even when `headless=True` so
ground segments keep scrolling. Skipping camera stalls runners near ~18m.

---

## Experiment A — Anti-scrape / high-CoG curriculum (implemented)

**Idea:** Early training rewards upright posture and forward velocity while
penalizing thigh-drag / knee-scrape (low torso + high knee flexion). Later,
anneal posture penalties toward zero so the policy can chase pure speed.

| Phase | Config | Focus |
|-------|--------|--------|
| A | `config/train_qrdqn_wr_phase_a.yml` | Shaping on; `reduced_action_set: true`; `frames_per_step: 4`; aim upright stride ≥20m |
| B | `config/train_qrdqn_wr_phase_b.yml` | Load Phase A; penalties near 0; velocity-dominant fine-tune |

Wrapper: `AntiScrapeCurriculumWrapper`
(`qwop_python/wrappers/anti_scrape_wrapper.py`).

- Rewards: forward velocity, torso / CoM height above a floor.
- Penalties: scrape (low torso ∧ flexed knees), optional small knee-flexion.
- Anneal via `anneal_penalties` + `set_progress()` (same scheduler hook as
  progressive velocity), or use the two YAML configs above.

`frames_per_step: 4` is the default (matches prior WR-oriented QRDQN runs;
0.16s per action). Prefer `2` only when testing finer control (see Exp D).

---

## Experiment B — Extended-knee shaping (scaffold)

**Idea:** WR gaits often keep the free leg more extended. Add a bonus for
knee extension (near joint upper limit).

Scaffold already in `AntiScrapeCurriculumWrapper`: set
`knee_extension_bonus_weight > 0` (Phase A/B leave it at `0.0`). Combine with
near-zero scrape penalties so extension does not fight Phase A anti-scrape.

---

## Experiment C — Expert demo bootstrap (record → BC → WR from scratch)

**Idea:** Use an expert checkpoint **only** to write demonstration `.rec`
files, behavioral-clone a policy, then keep WR QRDQN from-scratch (no expert
as `model_load_file`). Optional PPO finetune from `ppo_warmup.zip`.

**Implemented:** see [`doc/DEMO_BOOTSTRAP.md`](DEMO_BOOTSTRAP.md).

| Step | Command / config |
|------|------------------|
| Record | `qwop-python record_model` (`config/record_model.yml`) |
| BC | `qwop-python train_bc` (`config/train_bc.yml`) |
| WR scout | `config/sweeps/scout_qrdqn_wr_from_scratch.yml` (`model_load_file: ~`) |
| Phase A long | `config/train_qrdqn_wr_phase_a_long.yml` (16M, `n_envs: 4`) |

DQfD / demo-augmented replay for QRDQN remains future work; this pass is the
Liao-style demo bootstrap without contaminating WR checkpoints.

---

## Experiment D — Action-rate ablation (planned)

**Idea:** Ablate `frames_per_step` (2 vs 4) and optionally action-change
energy penalties. Lower FPS gives finer timing; higher FPS improves sample
efficiency. Keep `reduced_action_set` fixed when comparing rates.

---

## Experiment E — Split + hurdle fine-tune (planned)

**Idea:** Use 10m / 50m / 100m split times (already in `info`) plus hurdle
approach shaping / episode filters to optimize the second half of the race
and the sand-pit landing. Curriculum: freeze early-race policy, fine-tune
on segments past 50m or near the hurdle.

Split metrics (always present; `-1.0` until the mark is crossed):

- `split_10m_time` — physics `score_time` at first ≥10m
- `split_50m_time` — at first ≥50m
- `split_100m_time` — at first ≥100m

---

## Suggested order

1. **A** Phase A until upright ≥20m is routine  
2. **A** Phase B velocity fine-tune  
3. **B** extended-knee bonus if gait stays too crouched  
4. **C** demo bootstrap (`record_model` → `train_bc`) if from-scratch stalls; keep WR QRDQN from-scratch  
5. **D** confirm fps=4 vs 2 for the best Phase B checkpoint  
6. **E** mid-race / hurdle split optimization toward sub-45.530s
