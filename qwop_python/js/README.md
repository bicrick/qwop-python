# QWOP Physics (JS) for PyMiniRacer

This folder contains the physics-only JavaScript bundle that runs inside Python via PyMiniRacer (or similar), so training uses the same JS Box2D behavior as the browser game without Chrome.

## Dependencies

**Python:** `mini-racer` (PyMiniRacer; import: `py_mini_racer`). Install with:
```bash
pip install mini-racer
# or: pip install qwop-python[js]
```

**Planck.js** (Box2D 2.3 port, headless). Download once:

```bash
curl -sL -o planck.min.js "https://unpkg.com/planck-js@0.3.0/dist/planck.min.js"
```

Or with wget:

```bash
wget -q -O planck.min.js "https://unpkg.com/planck-js@0.3.0/dist/planck.min.js"
```

Place `planck.min.js` in this directory (`qwop_python/js/`).

## Files

- `planck.min.js` – Planck.js library (download as above).
- `qwop_physics.js` – QWOP world, bodies, joints, controls, getObservation, reset, setAction, step. No DOM; callable from Python. Constants and control logic match `qwop_python/data.py` and `doc/reference/` (QWOP_JOINTS_EXACT_DATA.md, QWOP_CONTROLS.md, QWOP_FUNCTIONS_EXACT.md); joint creation order matches OG QWOP.min.js (qwop-gym).

## Usage from Python

Load Planck then the physics bundle, then call:

- `reset(seed)` – reinit world and player.
- `setAction(q, w, o, p)` – set key state (booleans).
- `step(dt)` – advance physics (typically dt = 0.04).
- `getObservation()` – returns `{ time, distance, obs, gameEnded, success }` (obs is 60 floats).

Reward and normalization stay in Python; this module only runs physics and returns state.
