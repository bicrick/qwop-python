# QWOP Python

## Install

Python 3.10+

```bash
pip install -r requirements.txt
```

If you are on a GPU instance, run the setup script to configure Git/SSH and install the GPU stack:

```bash
./scripts/setup.sh
```

## Play

```bash
python play.py
```

## Train

```bash
python train.py --config config/train_qrdqn_single.yml
tensorboard --logdir data/
```

## Eval

```bash
python evaluate.py --model data/models/QRDQN_*/final_model.zip --episodes 50
```
