# QWOP Python

A faithful recreation of QWOP in Python using Box2D physics, with full RL training support.

## Installation

```bash
pip install -r requirements.txt

# If you get progress bar errors, also install:
pip install tqdm rich
```

## Playing the Game

```bash
python main.py
```

**Controls**: Q/W/O/P to move, R to reset, ESC to quit

## Training RL Agents

```bash
# Quick training (100k timesteps, ~2 minutes)
python3 train_simple.py

# Evaluate trained model
python3 evaluate.py --model data/models/QRDQN_simple_*/final_model.zip --episodes 50

# Monitor with TensorBoard
tensorboard --logdir data/
```

**Performance**: 100-500x faster than WebSocket-based training (native Python, no browser overhead)

See `docs/` for detailed guides.
