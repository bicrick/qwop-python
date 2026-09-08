# Demo bootstrap (Liao-style) — record → BC → WR from scratch

Recipe for using an expert **only to generate demonstration `.rec` files**,
then behavioral-cloning a policy that can warm-start **on-policy** RL — while
keeping WR QRDQN runs **from-scratch** (no `expert_dqnfd.zip` as
`model_load_file`).

## Why

Loading `data/saved_models/expert_dqnfd.zip` directly as the WR Phase A/B
checkpoint mixes expert weights into the WR run and muddies baselines.
Instead:

1. Expert → headless rollouts → `.rec` demos  
2. `.rec` → `train_bc` → `model.zip` (+ optional `ppo_warmup.zip`)  
3. WR QRDQN scout / Phase A → **no** `model_load_file` (from scratch)  
4. Optional: PPO finetune from `ppo_warmup.zip` (not QRDQN)

## 1. Record demos from a model

```bash
# Uses config/record_model.yml (expert_dqnfd.zip → data/recordings/*.rec)
qwop-python record_model
```

Key knobs in `config/record_model.yml`:

| Key | Role |
|-----|------|
| `model_file` | SB3 zip used **only** to generate demos |
| `n_episodes` | How many headless episodes to attempt |
| `env_wrappers.RecordWrapper.min_distance` / `max_time` | Keep filters |
| `env_kwargs.frames_per_step` / `reduced_action_set` | Must match model |

Output format matches human `play` + `RecordWrapper` and
`common.load_recordings`.

## 2. Behavioral cloning

```bash
# Optional (preferred): pip install "imitation>=1.0"
qwop-python train_bc
```

- Prefer **`imitation.algorithms.bc.BC`** when importable.  
- If imitation is missing or incompatible with the project SB3 pin
  (`imitation` declares `stable-baselines3~=2.2` while this repo targets
  SB3 2.9), **`train_bc` falls back to a minimal supervised ActorCriticPolicy
  trainer** and still writes a loadable zip.

Artifacts under `data/BC-{run_id}/`:

| File | Use |
|------|-----|
| `model.zip` | BC policy (`torch.save` of `ActorCriticPolicy`); spectate with `config/spectate_bc.yml` |
| `ppo_warmup.zip` | PPO checkpoint for **on-policy** RL finetune via `model_load_file` |

```bash
# Watch the BC policy
qwop-python -c config/spectate_bc.yml spectate
# (edit model_file to your data/BC-*/model.zip)
```

## 3. WR path — from scratch (no expert weights)

```bash
# Short scout (no model_load_file)
qwop-python train_qrdqn -c config/sweeps/scout_qrdqn_wr_from_scratch.yml

# Long Phase A no-demo baseline (16M steps, n_envs=4)
qwop-python train_qrdqn -c config/train_qrdqn_wr_phase_a_long.yml
```

Both YAMLs set `model_load_file: ~`. Do **not** point them at
`expert_dqnfd.zip`.

## 4. Optional PPO finetune from BC

```yaml
# e.g. config/train_ppo.yml fragment
model_load_file: "data/BC-<run_id>/ppo_warmup.zip"
```

This is the supported “BC then RL-finetune” path. QRDQN does not share the
ActorCritic policy network, so BC warmup does **not** load into QRDQN; use
demos for bootstrap research and keep QRDQN WR runs from scratch (or future
DQfD / demo-buffer work — see Experiment C in `doc/WR_EXPERIMENTS.md`).

## Blockers / notes

| Topic | Status |
|-------|--------|
| `imitation` + SB3 2.9 | Declared pin conflict (`~=2.2`); often still imports. Fallback BC always available. |
| GAIL / AIRL | Still not implemented (`train_gail` / `train_airl` exit with message). |
| Expert as WR checkpoint | **Disallowed** for this recipe — demos only. |

## Suggested order

1. `record_model` until `data/recordings/` has kept episodes (`min_distance` OK)  
2. `train_bc` (raise `n_epochs` for real runs)  
3. Spectate BC; optionally PPO-finetune from `ppo_warmup.zip`  
4. Run `scout_qrdqn_wr_from_scratch` then `train_qrdqn_wr_phase_a_long` as no-demo WR baseline  
