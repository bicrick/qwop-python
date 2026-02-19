# QWOP Python

A Gymnasium environment for Bennet Foddy's game [QWOP](https://www.foddy.net/Athletics.html) - a pure Python Box2D implementation forked from [qwop-gym](https://github.com/smanolloff/qwop-gym).

![qwop-python](./doc/qwop-python.gif)

This project reimplements the qwop-gym environment and tooling in pure Python, running entirely headless (no browser, no chromedriver). Designed for high-throughput training with parallelization in mind.

## Differences from qwop-gym

* **Pure Python + Box2D** - No browser, WebGL, or chromedriver. Runs entirely in process.
* **Headless by default** - Training uses no rendering; play, spectate, and replay use Pygame.
* **Parallelization-ready** - Single-process training matches qwop-gym; parallel envs can be re-added later for higher throughput.
* **Same interface** - 60-dim observations, Discrete 9/16 actions, compatible reward model. Behavior matches qwop-gym.

## Install

Python 3.10+:

```bash
pip install -e .
```

For RL training (stable-baselines3, PyTorch, TensorBoard):

```bash
pip install -e ".[sb3]"
```

## The `qwop-python` tool

The `qwop-python` executable mirrors qwop-gym's CLI. Run from a directory with `config/` and `data/` (or repo root).

First-time setup:

```bash
qwop-python bootstrap
```

Play the game (use Q, W, O, P keys):

```bash
qwop-python play
```

Explore the other commands:

```bash
$ qwop-python -h
usage: qwop-python [options] <action>

options:
  -h, --help    show this help message and exit
  -c FILE       config file, defaults to config/<action>.yml
  --run-id ID   run id (train_*)

action:
  bootstrap      create config/ with templates
  play           interactive gameplay
  record         play with recording (-c config/record.yml)
  replay         replay recorded actions
  spectate       watch trained model play
  benchmark      measure env steps/sec
  train_ppo      train using PPO
  train_dqn      train using DQN
  train_qrdqn    train using QRDQN
  train_rppo     train using RPPO
  train_a2c      train using A2C

examples:
  qwop-python bootstrap
  qwop-python play
  qwop-python -c config/record.yml play
  qwop-python spectate
  qwop-python train_ppo
```

Record your own gameplay:

```bash
qwop-python -c config/record.yml play
```

Train a PPO agent (edit `config/train_ppo.yml` if needed):

```bash
qwop-python train_ppo
```

Visualize TensorBoard logs:

```bash
tensorboard --logdir data/
```

Configure `model_file` in `config/spectate.yml` and watch a trained agent:

```bash
qwop-python spectate
```

Replay recorded episodes:

```bash
qwop-python replay
```

Benchmark env throughput (steps/sec):

```bash
qwop-python benchmark
```

## Create an instance in code

```python
import gymnasium as gym

# Headless (default) - for training
env = gym.make("local/QWOP-v1", seed=42)

# With rendering - for play, spectate, replay
env = gym.make("local/QWOP-v1", render_mode="human", seed=42)
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(0)
env.render()
env.close()
```

## Project structure

```
qwop_python/           # Main package
  qwop_env.py          # Gymnasium environment
  game.py              # Game loop, physics integration
  tools/               # CLI (play, train_*, spectate, replay, benchmark)
  wrappers/            # VerboseWrapper, RecordWrapper
config/                # YAML configs (created by bootstrap)
data/                  # Models, logs, checkpoints, recordings
```

## License

Apache-2.0 (same as qwop-gym).
