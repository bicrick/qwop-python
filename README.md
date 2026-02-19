# QWOP Python

A Gymnasium environment for QWOP - pure Python Box2D implementation.

## Install

Python 3.10+

```bash
pip install -e .
```

For RL training (SB3, PyTorch, TensorBoard):

```bash
pip install -e ".[sb3]"
```

Alternative: `pip install -r requirements.txt`

On a GPU instance, run the setup script to configure Git/SSH and install the GPU stack:

```bash
./scripts/setup.sh
```

## Project Structure

```
qwop_python/          # Main package
  tools/              # CLI (play, train_ppo, evaluate, collect_demos, bootstrap)
config/               # YAML configs (run from repo root)
data/                 # Models, logs, checkpoints
doc/                  # Documentation
```

## Usage

All commands via `qwop-python` CLI. Run from a directory with `config/` and `data/` (or repo root).
If `config/` is missing: `qwop-python bootstrap`

**Play:**
```bash
qwop-python play
```

**Train (tools config):**
```bash
qwop-python train_ppo
qwop-python train_qrdqn
```

**Train (standalone config, DQNfD):**
```bash
qwop-python train -c config/train_qrdqn_single.yml
qwop-python train -c config/train_dqnfd_stage1.yml --resume-from data/QRDQN_*/final_model.zip
```

**Evaluate:**
```bash
qwop-python evaluate --model data/models/QRDQN_*/final_model.zip --episodes 50
```

**Collect demos (DQNfD):**
```bash
qwop-python collect_demos -c config/collect_demos.yml
```

```bash
tensorboard --logdir data/
```

## Dev / Run without install

From repo root:

```bash
PYTHONPATH=. python qwop-python.py train_ppo
```
