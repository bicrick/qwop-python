# Parallel WR scout sweeps (CPU)

Lightweight harness for running several short QWOP training experiments at once on a typical **8 vCPU / 16GB** machine. No GPU required.

## What you get

1. **`n_envs` works** — train configs honor `n_envs` via `SubprocVecEnv` (falls back to `DummyVecEnv` if subprocess startup fails).
2. **`scripts/sweep_parallel.py`** — launch up to N concurrent `qwop-python train_*` processes; writes PIDs + logs under `data/sweeps/<timestamp>/`.
3. **`scripts/monitor_runs.py`** — table of run_id, alive?, last success rate, episode reward, and `user/time` from TensorBoard events.

Single-run CLI is unchanged: `qwop-python train_ppo`, etc.

## Safe defaults on 8 vCPU / 16GB

| Knob | Scout recommendation | Why |
|------|----------------------|-----|
| Concurrent train processes (`-n`) | **2–4** (default `cpu_count//2`) | Leaves headroom for OS + PyTorch |
| `n_envs` inside each config | **1** (scout YAMLs) | Avoid process × env oversubscription |
| `--max-timesteps` | **100k–200k** | Fast scouting before long WR runs |
| BLAS/OMP threads | set to 1 by the launcher | Prevents silent CPU oversubscription |

Rule of thumb: **concurrent_runs × n_envs ≤ number of physical cores**, and keep total RAM under ~12GB so the machine stays responsive.

For a longer single run after scouting, raise `n_envs` (e.g. 4–8) in one config and run alone — do not also stack 4 parallel train processes each with `n_envs: 8`.

## Built-in scout set

```bash
# From repo root, with sb3 extras installed:
pip install -e ".[sb3]"

# Dry-run to see the plan
python scripts/sweep_parallel.py --builtin --dry-run

# Launch (default concurrency = max(1, cpu_count//2))
python scripts/sweep_parallel.py --builtin --max-timesteps 200000

# Safer on 16GB: only 2 at a time
python scripts/sweep_parallel.py --builtin -n 2 --max-timesteps 100000
```

Built-in configs (`config/sweeps/`):

| Config | Intent |
|--------|--------|
| `scout_ppo_fps1.yml` | PPO, `frames_per_step=1` |
| `scout_ppo_fps2.yml` | PPO, `frames_per_step=2` |
| `scout_ppo_fps4.yml` | PPO, `frames_per_step=4` |
| `scout_ppo_phase_a.yml` | Phase A — competence (low speed weight, keep fall penalty) |
| `scout_ppo_speed_safe.yml` | Mild progressive velocity incentive |
| `scout_qrdqn.yml` | Short QRDQN vs PPO comparison |

## Custom config list

```bash
python scripts/sweep_parallel.py \
  -c config/sweeps/scout_ppo_phase_a.yml config/sweeps/scout_qrdqn.yml \
  -n 2 --max-timesteps 150000
```

Each child is started as:

```text
qwop-python -c <config> <train_action> --run-id <id> [--max-timesteps N]
```

Action is inferred from the config filename (`ppo` → `train_ppo`, `qrdqn` → `train_qrdqn`, …), or set explicitly with `action:` / `train_action:` in the YAML.

## Sweep outputs

```text
data/sweeps/<YYYYMMDD-HHMMSS>/
  manifest.yml          # all runs, concurrency, cmds
  <run_id>.pid          # training process PID
  <run_id>.log          # stdout/stderr
  <run_id>.yml          # per-run metadata
```

Training artifacts / TB logs still go to each config’s `out_dir_template` (e.g. `data/scout-ppo-fps4-<run_id>/`).

## Monitor

```bash
# Most recent sweep
python scripts/monitor_runs.py --latest

# Specific sweep dir
python scripts/monitor_runs.py data/sweeps/20260307-221500

# Refresh every 30s
python scripts/monitor_runs.py --latest --watch 30
```

Columns: `run_id`, `alive`, `success` (`user/is_success`), `ep_rew` (`rollout/ep_rew_mean`), `time` (`user/time`), `step`, `pid`.

Also useful:

```bash
tensorboard --logdir data/
```

## Using `n_envs` in a single train

```yaml
# in any train_*.yml
n_envs: 4
```

```bash
qwop-python -c config/train_qrdqn_wr.yml train_qrdqn --max-timesteps 500000
```

With `n_envs > 1`, training uses `SubprocVecEnv`. If spawn fails (platform / Box2D), it warns and falls back to `DummyVecEnv` with the same `n_envs`.

## Stopping a sweep

The launcher detaches children into their own session so Ctrl+C on the launcher does **not** kill trains (PIDs remain under `data/sweeps/...`). To stop them:

```bash
# kill all PIDs recorded for a sweep
for f in data/sweeps/<timestamp>/*.pid; do kill "$(cat "$f")" 2>/dev/null || true; done
```
