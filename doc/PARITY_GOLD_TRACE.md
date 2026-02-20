# Gold trace format and generation (qwop-python vs qwop-gym parity)

Gold traces are step-by-step logs (seed, actions, obs, reward, done, info) used to validate that qwop-python matches qwop-gym within numerical tolerance when replaying the same seed and actions.

## Format

Single JSON file per run:

- `seed` (int): Environment seed.
- `frames_per_step` (int): Env frames_per_step.
- `reduced_action_set` (bool): Whether 9-action set was used.
- `reward_dt_mode` (string): `"sim"` or `"protocol_30hz"`.
- `steps` (array): One object per step after each `env.step(action)`:
  - `action` (int): Action index taken.
  - `obs` (array of 60 floats): Observation vector.
  - `reward` (float): Step reward.
  - `terminated` (bool): Episode terminated.
  - `truncated` (bool): Episode truncated.
  - `info` (object): At least `time`, `distance`, `avgspeed`, `is_success` (floats).

Example:

```json
{
  "seed": 42,
  "frames_per_step": 4,
  "reduced_action_set": true,
  "reward_dt_mode": "protocol_30hz",
  "steps": [
    {
      "action": 0,
      "obs": [ ... ],
      "reward": -0.033,
      "terminated": false,
      "truncated": false,
      "info": { "time": 0.0133, "distance": 0.0, "avgspeed": 0.0, "is_success": 0.0 }
    }
  ]
}
```

## Generate from qwop-python

Use the script (from project root):

```bash
python scripts/gold_trace.py generate --seed 42 --frames-per-step 4 --steps 100 --out tests/fixtures/gold_trace_seed42_fps4.json
```

This writes a trace using random actions (seeded). For a fixed action sequence you can edit the script or use a recording (same format as qwop-gym: seed + list of action indices).

## Generate from qwop-gym

1. Run qwop-gym with a fixed seed and record actions (or use a fixed list).
2. While stepping, log after each step: `action`, `obs.tolist()`, `reward`, `terminated`, `truncated`, and `info` keys `time`, `distance`, `avgspeed`, `is_success`.
3. Save as JSON in the format above with the same seed and `frames_per_step` (and `reduced_action_set` / `reward_dt_mode` if you use them).

You can add a small script in the qwop-gym repo that creates an env, runs a replay or fixed actions, and writes this JSON. Then copy the file into qwop-python `tests/fixtures/` (e.g. `gold_trace_seed42_fps4.json`).

## Compare qwop-python to gold

From qwop-python project root:

```bash
python scripts/gold_trace.py compare --gold tests/fixtures/gold_trace_seed42_fps4.json
```

Optional tolerances: `--rtol 1e-3 --atol 1e-5` (default). Different Box2D implementations (browser vs PyBox2D) may require these tolerances for obs/reward to pass.

## Running the parity test

From project root, install test deps then run (use `python -m pytest` so the env's pytest is used):

```bash
pip install -e ".[test]"
python -m pytest tests/test_parity.py -v
```

- `test_determinism_*` always run (no gold needed).
- `test_gold_trace_parity` runs only if `tests/fixtures/gold_trace_seed42_fps4.json` exists; otherwise skipped with reason pointing to this doc.
