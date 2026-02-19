# QWOP Gym Migration – Agent Task List

This document breaks the qwop-gym training integration into discrete tasks for separate agents. Each task is self-contained; prerequisites are noted.

**End goal:** qwop-python becomes a pip-installable package (`pip install qwop-python`) with a CLI (`qwop-python train_ppo`) mirroring qwop-gym, using the pure Python Box2D environment.

**Reference codebase:** qwop-gym at `qwop-gym/` (or `/Users/b407404/Desktop/Misc/qwop-gym` if in workspace)

---

## Task 1: Add speed_rew_mult to QWOPEnv

**Prerequisites:** None

**Context:** qwop-gym scales velocity in the reward by 0.01. qwop-python uses raw velocity. Add the same scaling for consistent training.

**Instructions:**

1. Open `src/qwop_env.py`
2. Add `speed_rew_mult=0.01` to `__init__` parameters
3. Store it as `self.speed_rew_mult`
4. In `_calc_reward()`, change the base reward from:
   ```python
   reward = velocity - (self.time_cost_mult * dt / self.frames_per_step)
   ```
   to:
   ```python
   reward = velocity * self.speed_rew_mult - (self.time_cost_mult * dt / self.frames_per_step)
   ```
5. Leave terminal bonuses (success_reward, failure_cost) unchanged

**Files:**

- `src/qwop_env.py` (modify)

**Acceptance:**

- QWOPEnv accepts `speed_rew_mult` and uses it in reward calculation
- Default is 0.01
- Existing callers work without changes (optional param)

---

## Task 2: Create src/tools/ and port common.py

**Prerequisites:** Task 1 (speed_rew_mult exists)

**Context:** common.py provides env registration, config expansion, and utilities. We port it from qwop-gym but use QWOPEnv (Python) instead of QwopEnv (browser).

**Instructions:**

1. Create `src/tools/__init__.py` (can be empty or `"""QWOP training tools."""`)
2. Create `src/tools/common.py` by porting from `qwop-gym/qwop_gym/tools/common.py`
3. Changes from original:
   - Replace `from .. import QwopEnv` with `from ..qwop_env import QWOPEnv`
   - In `register_env()`, the wrapped creator should call `QWOPEnv(**kwargs)` instead of `QwopEnv(**kwargs)`
   - Add a filter: before passing kwargs to QWOPEnv, keep only: `frames_per_step`, `reduced_action_set`, `failure_cost`, `success_reward`, `time_cost_mult`, `seed`, `speed_rew_mult`
   - Remove browser-specific kwargs: `browser`, `driver`, `render_mode`, `stat_in_browser`, `game_in_browser`, `text_in_browser`, `reload_on_reset`, `auto_draw`, `t_for_terminate`, `loglevel`, `browser_mock`
4. Keep: `expand_env_kwargs`, `INFO_KEYS`, `out_dir_from_template`, `lr_from_schedule`, `save_model`, `save_config`, `gen_seed`, `gen_id`
5. For gymnasium, use `gymnasium.envs.registration.register` (check qwop-gym for exact API; it may use `gym.envs.register` or `gymnasium.envs.register`)

**Files:**

- `src/tools/__init__.py` (create)
- `src/tools/common.py` (create, port from qwop-gym)

**Acceptance:**

- `register_env(env_kwargs, env_wrappers)` registers `local/QWOP-v1` with a creator that builds QWOPEnv
- `expand_env_kwargs` supports `__include__` to merge YAML from another file
- No import errors; QWOPEnv is imported from the correct location

---

## Task 3: Port train_sb3.py

**Prerequisites:** Task 2 (common.py exists and register_env works)

**Context:** train_sb3.py creates the vectorized env and runs SB3 training. It calls `create_vec_env` and `train_sb3`.

**Instructions:**

1. Create `src/tools/train_sb3.py` by porting from `qwop-gym/qwop_gym/tools/train_sb3.py`
2. Change the import: `from . import common` (relative import within tools)
3. In `create_vec_env`, ensure the env id is `"local/QWOP-v1"` (same as qwop-gym) – this env is registered by common.register_env before training runs
4. Use `stable_baselines3.common.env_util.make_vec_env`
5. Use `gymnasium.wrappers.TimeLimit` for max_episode_steps
6. Pass `monitor_kwargs={"info_keywords": common.INFO_KEYS}` to make_vec_env
7. Do not add `save_vecnormalize=True` to CheckpointCallback (qwop-python does not use VecNormalize)
8. Keep LogCallback, CheckpointCallback, init_model, and the algorithm dispatch (A2C, PPO, DQN, QRDQN, RPPO)

**Files:**

- `src/tools/train_sb3.py` (create, port from qwop-gym)

**Acceptance:**

- train_sb3(learner_cls, seed, run_id, ...) runs SB3 training
- Uses `local/QWOP-v1` – caller must have called `common.register_env()` first
- Supports PPO, A2C, DQN, QRDQN, RPPO

---

## Task 4: Port main.py and create CLI entry point

**Prerequisites:** Tasks 2, 3

**Context:** main.py parses the action (e.g. train_ppo), loads config, registers the env, and dispatches to the appropriate trainer.

**Instructions:**

1. Create `src/tools/main.py` by porting from `qwop-gym/qwop_gym/tools/main.py`
2. Simplify: remove `ensure_patched()` (no QWOP.min.js)
3. Simplify `ensure_bootstrapped()`: only check that `config/` exists and contains the required YAML for the action. If not, print a message like "Run from project root or ensure config/ exists with config/<action>.yml" and exit
4. In the `run()` function, keep the flow: pop env_kwargs and env_wrappers, call `common.expand_env_kwargs`, call `common.register_env`
5. For actions `train_a2c`, `train_ppo`, `train_dqn`, `train_qrdqn`, `train_rppo`: dispatch to `train_sb3.train_sb3` with the appropriate learner_cls
6. For `play`, `replay`, `spectate`, `benchmark`, `train_bc`, `train_gail`, `train_airl`: either stub with "not implemented" or omit if not in scope (focus on SB3 training first)
7. Config loading: load from `config/<action>.yml` by default, or from `-c FILE` if provided

**Files:**

- `src/tools/main.py` (create, port from qwop-gym)

**Acceptance:**

- `python -m src.tools.main train_ppo` (run from repo root with `PYTHONPATH=src` or equivalent) loads config, registers env, and runs training
- Works when `config/train_ppo.yml` exists (Task 5 creates it)

---

## Task 5: Create config templates

**Prerequisites:** None (can run in parallel with Tasks 1–4)

**Context:** qwop-gym uses per-action YAML configs with `__include__` to merge env.yml. We create Python-specific configs (no browser/driver).

**Instructions:**

1. Create `config/env.yml`:
   ```yaml
   failure_cost: 10
   success_reward: 50
   time_cost_mult: 10
   frames_per_step: 1
   reduced_action_set: false
   speed_rew_mult: 0.01
   ```

2. Create `config/train_ppo.yml` (reference: `qwop-gym/qwop_gym/tools/templates/train_ppo.yml`):
   - Use `env_kwargs: { __include__: "config/env.yml", frames_per_step: 4, reduced_action_set: false }` (adjust per action)
   - Include: seed, run_id, model_load_file, out_dir_template, log_tensorboard, total_timesteps, max_episode_steps, n_checkpoints, learner_kwargs, learner_lr_schedule
   - learner_lr_schedule: `"const_0.001"` or similar
   - learner_kwargs: PPO hyperparams from qwop-gym template

3. Create `config/train_qrdqn.yml` (reference: `qwop-gym/qwop_gym/tools/templates/train_qrdqn.yml`):
   - Same structure, QRDQN-specific learner_kwargs

4. Create `config/train_dqn.yml` if desired (or document that train_qrdqn covers it with learner_cls)

**Files:**

- `config/env.yml` (create)
- `config/train_ppo.yml` (create)
- `config/train_qrdqn.yml` (create)

**Acceptance:**

- Configs parse with PyYAML
- `__include__` is resolved by common.expand_env_kwargs (merge env.yml into env_kwargs)
- Training runs using these configs

---

## Task 6: Add run script for tools.main

**Prerequisites:** Tasks 2, 3, 4, 5

**Context:** Users need a simple way to run the qwop-gym-style CLI. Add a script that sets up the path and invokes main.

**Instructions:**

1. Create `run_tools.py` at project root (or add to an existing script)
2. It should:
   - Add `src` to `sys.path` so `from tools.main import main` works (when running from repo root)
   - Or use `python -m src.tools.main` – in that case, ensure the package can be run as a module. If `src` is not a package, use a wrapper that does `sys.path.insert(0, 'src')` then `from tools.main import main; main()`
3. Document in a comment: "Run from project root: python run_tools.py train_ppo"

**Files:**

- `run_tools.py` (create)

**Acceptance:**

- From repo root: `python run_tools.py train_ppo` runs training
- Config is loaded from `config/train_ppo.yml`

---

## Task 7: Package restructure – create qwop_python/

**Prerequisites:** Tasks 1–6 complete and verified

**Context:** Move from `src/` flat layout to `qwop_python/` package for pip installability.

**Instructions:**

1. Create directory `qwop_python/`
2. Move all files from `src/` into `qwop_python/` (game.py, physics.py, qwop_env.py, observations.py, actions.py, controls.py, collision.py, data.py, renderer.py, wrappers/, callbacks/, tools/)
3. Update all internal imports:
   - Within qwop_python: use relative imports where logical (e.g. `from .game import QWOPGame`) or absolute (`from qwop_python.game import QWOPGame`)
   - In qwop_env.py: `from .game import QWOPGame`, `from .observations import ObservationExtractor`, etc.
   - In tools/common.py: `from ..qwop_env import QWOPEnv`
   - In tools/train_sb3.py: `from . import common`
   - In tools/main.py: imports from tools and common
4. Update gymnasium registration in qwop_env.py: `entry_point="qwop_python.qwop_env:QWOPEnv"` for QWOP-v0
5. Remove or keep `src/` – if you remove it, ensure nothing references it

**Files:**

- `qwop_python/` (create, move contents from src/)
- All `.py` files in qwop_python/ (update imports)

**Acceptance:**

- `from qwop_python import QWOPEnv` works
- `from qwop_python.qwop_env import QWOPEnv` works
- No remaining references to `src` or old import paths
- Tools still work (paths to config may need adjustment – config/ stays at project root)

---

## Task 8: Create pyproject.toml

**Prerequisites:** Task 7 (qwop_python/ exists)

**Context:** Make the project pip-installable with optional sb3 deps and CLI script.

**Instructions:**

1. Create `pyproject.toml` at project root
2. Use this structure (adjust versions as needed):
   ```toml
   [build-system]
   requires = ["setuptools>=61.0"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "qwop-python"
   version = "0.1.0"
   description = "A Gymnasium environment for QWOP - pure Python Box2D implementation"
   requires-python = ">=3.10"
   dependencies = [
       "gymnasium ~= 0.29",
       "numpy ~= 1.24",
       "pygame ~= 2.5",
       "Box2D ~= 2.3",
       "pyyaml >= 6.0",
   ]

   [project.optional-dependencies]
   sb3 = [
       "stable_baselines3 ~= 2.1",
       "sb3-contrib ~= 2.1",
       "torch >= 2.0",
       "tensorboard",
       "tqdm",
       "rich",
   ]

   [project.scripts]
   "qwop-python" = "qwop_python.tools.main:main"

   [tool.setuptools.packages.find]
   where = ["."]
   include = ["qwop_python*"]
   ```
3. Ensure `qwop_python.tools.main` has a `main()` function callable from the CLI

**Files:**

- `pyproject.toml` (create)

**Acceptance:**

- `pip install -e .` succeeds
- `qwop-python train_ppo` runs after install (when config/ exists in CWD)
- Core deps installed by default; sb3 deps with `pip install -e ".[sb3]"`

---

## Task 9: Update top-level scripts (train, evaluate, play, collect_demos)

**Prerequisites:** Task 7, 8

**Context:** train.py, evaluate.py, play.py, collect_demos.py currently import from `src` or use `sys.path.insert(0, 'src')`. Update them to use the package.

**Instructions:**

1. **train.py**: Replace `sys.path.insert(0, 'src')` and `from qwop_env import QWOPEnv` with `from qwop_python import QWOPEnv` or `from qwop_python.qwop_env import QWOPEnv`. Ensure it still works when run from repo root after `pip install -e .`
2. **evaluate.py**: Same import updates
3. **play.py**: Same import updates
4. **collect_demos.py**: Same import updates
5. Any callbacks or wrappers they import: update to `from qwop_python.callbacks...` or `from qwop_python.wrappers...` as applicable

**Files:**

- `train.py`
- `evaluate.py`
- `play.py`
- `collect_demos.py`

**Acceptance:**

- All scripts run without import errors
- Work both: (a) from repo root without install, (b) after `pip install -e .` from any directory (if they need config/data paths, document CWD requirements)

---

## Task 10: Config path handling for installed package

**Prerequisites:** Task 8, 9

**Context:** When `qwop-python` is installed, `config/` may not exist in CWD. We need config templates available.

**Instructions:**

1. Create `qwop_python/tools/templates/` with copies of config/env.yml, train_ppo.yml, train_qrdqn.yml
2. In main.py (or common.py), when `config/<action>.yml` does not exist:
   - Fall back to package templates: `pkg_resources` or `importlib.resources` to read from `qwop_python/tools/templates/`
   - Or: on first run, copy templates from package into `./config/` and tell the user
3. Implement a simple `bootstrap` action: `qwop-python bootstrap` creates `config/` in CWD and copies templates from the package
4. Update `ensure_bootstrapped` to suggest `qwop-python bootstrap` when config/ is missing

**Files:**

- `qwop_python/tools/templates/env.yml`
- `qwop_python/tools/templates/train_ppo.yml`
- `qwop_python/tools/templates/train_qrdqn.yml`
- `qwop_python/tools/main.py` (add bootstrap action, config fallback)
- Optionally `qwop_python/tools/bootstrap.py`

**Acceptance:**

- `qwop-python bootstrap` creates config/ with templates
- `qwop-python train_ppo` works after bootstrap, from any directory
- Installed package is usable without a pre-existing config/ in the repo

---

## Task Dependencies Summary

```
Task 1 (speed_rew_mult)     ────────────────────────────────────────────┐
                                                                         │
Task 2 (common.py)          ────────────────────────────┐                │
                                                         │                │
Task 3 (train_sb3.py)       ────────────────────┐       │                │
                                                  │       │                │
Task 4 (main.py)             ──────────┐          │       │                │
                                       │          │       │                │
Task 5 (config templates)   ───────────┼──────────┼───────┤                │
                                       │          │       │                │
Task 6 (run_tools.py)       ───────────┴──────────┴───────┘                │
                                                                         │
Task 7 (restructure)        ────────────────────────────────────────────┘
                                                                         │
Task 8 (pyproject.toml)     ─────────────────────────────────────────────┘
                                                                         │
Task 9 (update scripts)     ─────────────────────────────────────────────┘
                                                                         │
Task 10 (config path)       ─────────────────────────────────────────────┘
```

**Suggested agent assignment:**

- Agent A: Tasks 1, 2, 3 (env + tools core)
- Agent B: Tasks 4, 5, 6 (CLI + config + run script)
- Agent C: Tasks 7, 8 (package restructure + pyproject)
- Agent D: Tasks 9, 10 (scripts + config path)

Or run sequentially: 1 -> 2 -> 3 -> 4 -> 5 -> 6, then 7 -> 8 -> 9 -> 10.
