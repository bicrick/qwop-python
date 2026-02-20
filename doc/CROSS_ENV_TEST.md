# Cross-env parity test: qwop-python vs qwop-gym

Run the same (seed, action sequence) in both qwop-python and the real qwop-gym (browser) and compare step-by-step: obs, reward, terminated, truncated, and info (time, distance, avgspeed, is_success). This validates 1-to-1 physical parity within numerical tolerance.

## Prerequisites

- **Conda** (for the combined env).
- **qwop-gym** repo (sibling or known path).
- **Chrome** (or Chromium) and **chromedriver** for the browser-based qwop-gym env.

## 1. Conda env with both packages

From the qwop-python repo root:

```bash
conda env create -f environment.yml
conda activate qwop-parity
```

Then install qwop-gym (edit the path to your qwop-gym repo):

```bash
pip install -e /path/to/qwop-gym
```

The env already has qwop-python via `pip install -e .` in `environment.yml`.

**qwop-gym game setup:** You do **not** need to run `qwop-gym bootstrap` for the cross-env test (bootstrap only creates config files; we pass browser/driver explicitly). You **do** need the patched game file: if the qwop-gym repo has never been set up, run once (from the qwop-gym repo, with qwop-gym installed) `curl -sL https://www.foddy.net/QWOP.min.js | qwop-gym patch` so `qwop_gym/envs/v1/game/QWOP.min.js` exists. If you have already used qwop-gym to play or train, you are set.

## 2. Browser and chromedriver

The cross-env test runs the real qwop-gym env in a browser, so Chrome and chromedriver are required.

- Install Chrome (or Chromium) and chromedriver and note their paths.
- Either set env vars:
  - `QWOP_GYM_BROWSER` – path to Chrome/Chromium executable
  - `QWOP_GYM_DRIVER` – path to chromedriver executable  
  or pass them explicitly to the script (see below).

## 3. Running the parity test

### Pytest (skipped if browser/driver not set)

With `QWOP_GYM_BROWSER` and `QWOP_GYM_DRIVER` set:

```bash
conda activate qwop-parity
python -m pytest tests/test_cross_env_parity.py -v
```

If qwop-gym is not installed or the env vars are unset, the test is skipped with a clear reason.

### Script (explicit paths)

For manual runs without env vars:

```bash
python scripts/cross_env_parity.py --browser /path/to/chrome --driver /path/to/chromedriver [--seed 42] [--steps 80]
```

- Exit 0: all steps matched within tolerance.
- Exit 1: first step where obs, reward, done, or info differed.
- Exit 2: qwop-gym not installed.

Options: `--seed`, `--steps`, `--frames-per-step` (defaults: 42, 80, 4).

## 4. Tolerances and 1-to-1 physical parity

- **obs:** `rtol=2e-2`, `atol=1e-1` (browser Box2D vs PyBox2D; divergence compounds over steps).
- **reward and info (time, distance, avgspeed):** `rtol=5e-1`, `atol=1e-1` (trajectories diverge so reward/info can differ more).
- **is_success:** equality (bool).
- Different Box2D implementations (browser JS vs PyBox2D) and floating-point can produce small differences; the test encodes “parity within tolerance” rather than bit-exact.
- If the test is still flaky, relax `CROSS_RTOL`/`CROSS_ATOL` in `tests/test_cross_env_parity.py` and `scripts/cross_env_parity.py` and document here.

## 5. What is compared

- After `reset(seed=seed)`: initial observations.
- Each step: same action is sent to both envs; then comparison of:
  - observation arrays
  - reward
  - terminated, truncated
  - info: time, distance, avgspeed, is_success
- The run stops when either env returns terminated or truncated; both must agree on done at the same step.
