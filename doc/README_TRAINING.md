# QWOP RL Training System

Complete reinforcement learning training pipeline for QWOP, running natively in Python with Box2D physics.

## Quick Start

### Installation

```bash
# Install dependencies
pip install stable-baselines3 sb3-contrib gymnasium pyyaml

# Optional: For progress bars during training
pip install tqdm rich

# Verify installation
python -c "from qwop_python import QWOPEnv; print('OK')"
```

### Training (Recommended: Single Process)

```bash
# Single process training (stable on all platforms including macOS)
python3 train.py --config config/train_qrdqn_single.yml
```

This will:
- Create a QWOP environment in headless mode
- Train QRDQN (default: 1M timesteps)
- Save model to `data/models/QRDQN_<run_id>_<timestamp>/final_model.zip`

### Evaluation

```bash
# Evaluate trained model
python3 evaluate.py --model data/models/QRDQN_*/final_model.zip --episodes 50
```

## Training Options

### Option 1: Single Process (Recommended for Testing)

**Config**: `config/train_qrdqn_single.yml`

- Single process (no multiprocessing)
- 1M timesteps by default
- Stable on all platforms including macOS

```bash
python3 train.py --config config/train_qrdqn_single.yml
```

### Option 2: Parallel Environments

**Config**: `config/train_qrdqn.yml`

- Multi-process with `SubprocVecEnv`
- Full configuration via YAML
- Checkpointing, TensorBoard logging
- Up to 8x faster on multi-core systems

**Note**: May have issues on macOS due to multiprocessing + Box2D. Use single-process config if you encounter errors.

```bash
python3 train.py --config config/train_qrdqn.yml
```

## Performance

### Speed Comparison

| Setup | Steps/Second | 1M Steps |
|-------|-------------|----------|
| qwop-wr (WebSocket) | ~100-500 | 30-180 min |
| qwop-python (single) | ~10,000 | ~2 min |
| qwop-python (4 parallel) | ~40,000 | ~30 sec |

**100-500x faster than qwop-wr!**

### Why So Fast?

1. **No WebSocket overhead**: Direct Python function calls instead of network I/O
2. **No browser rendering**: Pure physics computation, no Chrome/DOM
3. **Headless mode**: Print statements and camera tracking disabled
4. **Native Box2D**: C++ physics with Python bindings

## Files

### Core Implementation
- `qwop_python/qwop_env.py` - Gymnasium environment wrapper
- `qwop_python/wrappers/` - Reward shaping and other wrappers
- `qwop_python/game.py` - Game logic (with headless/verbose flags)
- `qwop_python/physics.py` - Box2D physics

### Training Scripts
- `train.py` - Training (supports single or parallel envs via config)
- `evaluate.py` - Model evaluation

### Configuration
- `config/train_qrdqn_single.yml` - Single process config
- `config/train_qrdqn.yml` - Multi-process config

### Documentation
- `TRAINING_GUIDE.md` - Comprehensive usage guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `README_TRAINING.md` - This file

## Environment Details

### Observation Space
- **Type**: `Box(shape=(60,), low=-1, high=1, dtype=float32)`
- **Content**: 12 body parts × 5 values (x, y, angle, vel_x, vel_y)
- **Normalized**: All values mapped to [-1, 1]

### Action Space
- **Type**: `Discrete(9)` with reduced_action_set=True
- **Actions**: none, Q, W, O, P, QW, QP, WO, OP
- **Full set**: `Discrete(16)` includes all 16 QWOP combinations

### Reward Function
```python
reward = velocity - time_cost + terminal_bonus
```
- **Velocity**: Forward speed in meters/second
- **Time cost**: `time_cost_mult * dt / frames_per_step`
- **Terminal bonus**: +50 for success, -10 for fall

## Advanced Features

### Reward Shaping

Add auxiliary reward signals:

```python
from qwop_python.wrappers import RewardShapingWrapper

env = RewardShapingWrapper(
    env,
    posture_weight=0.1,   # Penalize low torso
    energy_weight=0.01,   # Penalize action changes
    joint_weight=0.05     # Penalize extreme angles
)
```

### Custom Configuration

Edit YAML files to customize training:

```yaml
# config/my_experiment.yml
algorithm: QRDQN
total_timesteps: 10_000_000
n_envs: 1
env_kwargs:
  frames_per_step: 1       # Faster actions
  reduced_action_set: false  # Full 16 actions
learner_kwargs:
  learning_rate: 0.0003    # Lower LR
```

Then train:
```bash
python3 train.py --config config/my_experiment.yml --run-id my_experiment
```

## Troubleshooting

### Import Errors

Install the package: `pip install -e .` and run from repo root.

### Multiprocessing Errors

If `train.py` fails with mutex/threading errors:
1. Use `config/train_qrdqn_single.yml` (single process)
2. Or set `n_envs: 1` in your config

### Memory Issues

Reduce:
- `n_envs` (fewer parallel environments)
- `buffer_size` (smaller replay buffer)
- `policy_kwargs.net_arch` (smaller network)

### Slow Training

Check:
- Environment is headless? (should be automatic)
- Using multiple envs? (set `n_envs > 1` if stable)
- CPU at 100%? (good - means no bottlenecks)

## Example Workflow

```bash
# 1. Quick test (single process)
python3 train.py --config config/train_qrdqn_single.yml

# 2. Evaluate
python3 evaluate.py --model data/models/QRDQN_*/final_model.zip --episodes 50

# 3. Longer training (edit total_timesteps in config to 5M+)
python3 train.py --config config/train_qrdqn_single.yml --run-id long_run

# 4. Compare performance
python3 evaluate.py --model data/models/QRDQN_*/final_model.zip --episodes 100 --output data/eval/
```

## Next Steps

1. **Baseline**: Train with default config (100k-1M steps)
2. **Evaluate**: Check success rate and average distance
3. **Tune**: Adjust hyperparameters (learning rate, exploration, reward weights)
4. **Scale**: Increase timesteps to 5M-20M for final training
5. **Compare**: Try different algorithms (PPO, DQN)

## Implementation Notes

### Headless Mode
- Game runs with `verbose=False, headless=True`
- Zero print overhead (all console output gated)
- Camera tracking and speed array disabled
- Result: Pure physics computation

### Frame Skipping
- `frames_per_step=4` means each action lasts 0.16s (4 × 0.04s)
- Reduces RL decision frequency
- Improves sample efficiency
- Matches qwop-wr's proven approach

### Determinism
- Physics is deterministic with same seed
- Observations are reproducible
- Useful for debugging and evaluation

## Credits

Architecture based on [qwop-wr](https://github.com/user/qwop-wr)'s proven QRDQN approach, adapted for native Python execution with 100-500x speedup.
