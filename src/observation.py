"""
Observation format - 1:1 match with qwop-wr qwop_env.

Raw: 60 floats (12 bodies x 5) in OBS_PARTS order.
Per body: pos_x, pos_y, angle, vel_x, vel_y.
Both use same Box2D world layout (meters); no unit conversion.
Normalization: exact same ranges and formula as qwop_env.py _normalize().
"""

import numpy as np

DTYPE = np.float32

# Both use same Box2D layout: body positions 2.51 etc, floor at 32-unit spacing (QWOP_BODY_EXACT_DATA).
# No unit conversion needed; raw values match.
POS_SCALE = 1.0
VEL_SCALE = 1.0

# Body order from qwop-wr extensions.js OBS_PARTS
OBS_PARTS = [
    "torso",
    "head",
    "leftArm",
    "leftCalf",
    "leftFoot",
    "leftForearm",
    "leftThigh",
    "rightArm",
    "rightCalf",
    "rightFoot",
    "rightForearm",
    "rightThigh",
]

# Normalization ranges from qwop_env.py lines 204-207 (exact match)
OBS_LIMITS = {
    "pos_x": (-10.0, 1050.0),
    "pos_y": (-10.0, 10.0),
    "angle": (-6.0, 6.0),
    "vel_x": (-20.0, 60.0),
    "vel_y": (-25.0, 60.0),
}


def _make_normalizers():
    """Create normalizers matching qwop_env Normalizable class."""
    norm = {}
    for name, (lo, hi) in OBS_LIMITS.items():
        center = DTYPE((lo + hi) / 2)
        maxdev = DTYPE(hi - center)
        norm[name] = (center, maxdev)
    return norm


_NORM = _make_normalizers()


def extract_raw(physics):
    """
    Extract raw 60-float state from PhysicsWorld in qwop-wr units.

    Uses body.position to match getPosition() in extensions.js.
    Uses body.position to match getPosition() in extensions.js.
    """
    out = np.zeros(60, dtype=DTYPE)
    for i, name in enumerate(OBS_PARTS):
        body = physics.get_body(name)
        if body is None:
            continue
        base = i * 5
        pos = body.position
        vel = body.linearVelocity
        out[base] = pos[0] * POS_SCALE
        out[base + 1] = pos[1] * POS_SCALE
        out[base + 2] = body.angle
        out[base + 3] = vel[0] * VEL_SCALE
        out[base + 4] = vel[1] * VEL_SCALE
    return out


def normalize(raw):
    """
    Normalize raw 60 floats to [-1, 1] matching qwop_env._normalize exactly.
    Formula: (value - center) / maxdev, then np.clip to [-1, 1]
    """
    nobs = np.zeros(60, dtype=DTYPE)
    for i in range(0, 60, 5):
        cx, mx = _NORM["pos_x"]
        nobs[i] = (raw[i] - cx) / mx
        cy, my = _NORM["pos_y"]
        nobs[i + 1] = (raw[i + 1] - cy) / my
        ca, ma = _NORM["angle"]
        nobs[i + 2] = (raw[i + 2] - ca) / ma
        cvx, mvx = _NORM["vel_x"]
        nobs[i + 3] = (raw[i + 3] - cvx) / mvx
        cvy, mvy = _NORM["vel_y"]
        nobs[i + 4] = (raw[i + 4] - cvy) / mvy
    np.clip(nobs, -1.0, 1.0, out=nobs)
    return nobs
