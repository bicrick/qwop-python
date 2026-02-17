# QWOP RL Training Guide

This guide explains how to train and evaluate RL agents for QWOP using the native Python environment.

## Features

- **Headless Training**: No rendering overhead, runs at maximum physics speed
- **Parallel Environments**: Train with multiple environments simultaneously via `SubprocVecEnv`
- **Native Python**: 100-500x faster than WebSocket-based qwop-wr (no browser overhead)
- **Proven Hyperparameters**: Based on qwop-wr's successful QRDQN configuration
- **Flexible Rewards**: Velocity-based rewards with optional reward shaping wrappers

## Quick Start

### 1. Install Dependencies

```bash
pip install stable-baselines3 sb3-contrib gymnasium pyyaml

# Optional: For progress bars during training
pip install tqdm rich
```

### 2. Train a Model

```bash
python train.py --config config/train_qrdqn.yml
```

This will:
- Create 4 parallel QWOP environments (headless, no rendering)
- Train QRDQN agent for 5M timesteps
- Save checkpoints every 100k timesteps to `data/checkpoints/`
- Save final model to `data/models/`
- Log training metrics to `data/logs/` (TensorBoard compatible)

Training runs much faster than qwop-wr because:
- No WebSocket round-trip per step
- No Chrome rendering overhead
- Pure Box2D physics computation in microseconds

### 3. Monitor Training (Optional)

```bash
tensorboard --logdir data/logs/
```

### 4. Evaluate the Model

```bash
python evaluate.py --model data/models/QRDQN_default_*/final_model.zip --episodes 100
```

This will:
- Run 100 evaluation episodes
- Print success rate, average distance, average time
- Save detailed results to JSON

## Configuration

Training is controlled via YAML config files. See `config/train_qrdqn.yml` for an example.

### Key Parameters

**Environment:**
- `frames_per_step: 4` - Each action lasts 0.16s (4 × 0.04s physics ticks)
- `reduced_action_set: true` - Use 9 actions instead of 16
- `failure_cost: 10.0` - Penalty for falling
- `success_reward: 50.0` - Bonus for completing course
- `time_cost_mult: 10.0` - Time penalty weight

**Training:**
- `total_timesteps: 5_000_000` - Total training steps
- `n_envs: 4` - Number of parallel environments
- `max_episode_steps: 1000` - Episode truncation limit

**QRDQN Hyperparameters:**
- `buffer_size: 100_000` - Replay buffer capacity
- `learning_starts: 10_000` - Steps before training begins
- `batch_size: 64` - Minibatch size
- `gamma: 0.997` - Discount factor (high for long-term planning)
- `target_update_interval: 512` - Target network update frequency
- `exploration_initial_eps: 0.2` - Initial epsilon
- `exploration_final_eps: 0.0` - Final epsilon
- `exploration_fraction: 0.3` - Fraction of training for epsilon decay

## Reward Function

The base reward is velocity-based:

```python
reward = velocity - time_cost + terminal_bonus
```

Where:
- `velocity = (distance - last_distance) / (time - last_time)` (meters/second)
- `time_cost = time_cost_mult * dt / frames_per_step` (penalize time)
- `terminal_bonus = +50 for success, -10 for fall`

This encourages:
- Fast forward movement (high velocity)
- Efficient time usage
- Reaching the goal without falling

## Reward Shaping (Optional)

For additional training signals, use reward shaping wrappers:

```python
from src.wrappers import RewardShapingWrapper

env = QWOPEnv(...)
env = RewardShapingWrapper(
    env,
    posture_weight=0.1,     # Penalize low torso (anti-scoot)
    energy_weight=0.01,     # Penalize action changes (anti-jitter)
    joint_weight=0.05       # Penalize extreme joint angles
)
```

Reward components:
1. **Posture Penalty**: Negative reward when torso is too low (discourages scooting)
2. **Energy Penalty**: Negative reward for changing actions (discourages jitter)
3. **Joint Limit Penalty**: Negative reward for extreme joint angles (discourages splits)

## Advanced Usage

### Custom Run ID

```bash
python train.py --config config/train_qrdqn.yml --run-id my_experiment
```

### Resume Training

```bash
python train.py --config config/train_qrdqn.yml --resume-from data/checkpoints/QRDQN_default_*/model_1000000_steps.zip
```

### Evaluate with Specific Settings

```bash
python evaluate.py \
    --model data/models/QRDQN_default_*/final_model.zip \
    --episodes 500 \
    --seed 42 \
    --frames-per-step 4 \
    --output data/eval_results/
```

### Create Custom Config

Copy `config/train_qrdqn.yml` and modify parameters:

```yaml
algorithm: PPO  # Try different algorithms
total_timesteps: 10_000_000
n_envs: 8  # More parallel environments
env_kwargs:
  frames_per_step: 1  # Faster actions (40ms)
  reduced_action_set: false  # Full 16-action set
```

Supported algorithms:
- `QRDQN` (Quantile Regression DQN) - Best for QWOP
- `DQN` (Deep Q-Network)
- `PPO` (Proximal Policy Optimization)
- `A2C` (Advantage Actor-Critic)

## Performance Tips

### Speed Optimization

The environment is already optimized for speed:
- ✓ Headless mode (no rendering)
- ✓ Verbose=False (no print overhead)
- ✓ Camera/speed tracking skipped

To maximize throughput:
1. **Increase parallel environments**: `n_envs: 8` or `n_envs: 16` (use your CPU cores)
2. **Use frames_per_step=4**: Reduces RL frequency, improves sample efficiency
3. **Monitor system**: `htop` to verify CPU utilization

Expected performance:
- Single env: ~10,000 steps/second
- 4 parallel envs: ~40,000 steps/second
- 8 parallel envs: ~80,000 steps/second

This is 100-500x faster than qwop-wr due to no WebSocket/browser overhead.

### Hyperparameter Tuning

Start with the proven config, then experiment:
1. **Learning rate**: Try `0.0001` or `0.0003` if training unstable
2. **Exploration**: Increase `exploration_initial_eps` to 0.5 for more exploration
3. **Buffer size**: Increase to `200_000` if you have RAM
4. **Network size**: Try `[512, 512]` for more capacity

## Troubleshooting

### Import Errors

Make sure `src/` is in your Python path:
```python
import sys
sys.path.insert(0, 'src')
```

### Out of Memory

Reduce:
- `n_envs` (fewer parallel environments)
- `buffer_size` (smaller replay buffer)
- `policy_kwargs.net_arch` (smaller network)

### Slow Training

Check:
- Is `verbose=False` and `headless=True`? (should be automatic in env)
- Are you using multiple `n_envs`?
- Is your CPU at 100% utilization? (good - maximize `n_envs`)

## Next Steps

1. **Train baseline**: Run with default config to establish baseline
2. **Experiment**: Try different algorithms (PPO, DQN) and hyperparameters
3. **Add shaping**: Use `RewardShapingWrapper` if agent learns bad behaviors
4. **Curriculum**: Gradually increase difficulty (reduce `frames_per_step`)
5. **Scale up**: Increase `n_envs` and `total_timesteps` for final training run

## File Structure

```
qwop-python/
├── src/
│   ├── qwop_env.py              # Gymnasium environment
│   ├── wrappers/
│   │   └── reward_shaping_wrapper.py  # Reward shaping
│   ├── game.py                  # Game logic (with headless mode)
│   ├── physics.py               # Box2D physics
│   ├── observations.py          # Observation extraction
│   └── actions.py               # Action mapping
├── config/
│   └── train_qrdqn.yml          # Training configuration
├── train.py                     # Training script
├── evaluate.py                  # Evaluation script
├── data/                        # Training outputs
│   ├── checkpoints/             # Periodic checkpoints
│   ├── models/                  # Final models
│   └── logs/                    # TensorBoard logs
└── TRAINING_GUIDE.md            # This file
```

## References

- [qwop-wr](https://github.com/user/qwop-wr) - Original WebSocket-based RL environment
- [Stable-Baselines3](https://stable-baselines3.readthedocs.io/) - RL library
- [Gymnasium](https://gymnasium.farama.org/) - Environment API
