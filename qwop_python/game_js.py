"""
QWOP Game backend using JS physics (Planck.js) via PyMiniRacer.

Provides the same interface as game.QWOPGame so qwop_env can use
either PyBox2D or this JS backend via backend="js".

Requires: mini-racer (PyMiniRacer; import: py_mini_racer) and planck.min.js in qwop_python/js/.
"""

import os
import numpy as np

from .data import (
    PHYSICS_TIMESTEP,
    WORLD_SCALE,
    INITIAL_CAMERA_X,
    INITIAL_CAMERA_Y,
    CAMERA_HORIZONTAL_OFFSET,
    CAMERA_VERTICAL_THRESHOLD,
    CAMERA_VERTICAL_OFFSET,
)
from .observations import ObservationExtractor

# Browser (extensions.js) uses TIMESTEP_SIZE = 1/30 for time clock; physics still uses 0.04 in world.step.
# Pass this as timeDt so scoreTime advances match gym and obs/time align.
GAME_TIME_DT = 1.0 / 30.0

# Body order must match qwop_physics.js BODY_ORDER
BODY_ORDER = [
    "torso", "head", "leftArm", "leftCalf", "leftFoot", "leftForearm",
    "leftThigh", "rightArm", "rightCalf", "rightFoot", "rightForearm", "rightThigh",
]


class _BodyProxy:
    """Body-like object built from cached observation slice (5 floats per body)."""
    __slots__ = ("worldCenter", "angle", "linearVelocity")

    def __init__(self, x, y, angle, vx, vy):
        self.worldCenter = (float(x), float(y))
        self.angle = float(angle)
        self.linearVelocity = (float(vx), float(vy))

    @property
    def position(self):
        """Renderer expects body.position; same as worldCenter for center-of-mass."""
        return self.worldCenter


class _PhysicsProxy:
    """Physics-like object that returns body proxies from the last JS observation."""
    hurdle_base = None
    hurdle_top = None

    def __init__(self, body_order):
        self._body_order = body_order
        self._obs = None  # 60 floats, set by game

    def set_observation(self, obs):
        self._obs = obs

    def get_body(self, name):
        if self._obs is None or len(self._obs) != 60:
            return None
        try:
            i = self._body_order.index(name)
        except ValueError:
            return None
        base = i * 5
        return _BodyProxy(
            self._obs[base],
            self._obs[base + 1],
            self._obs[base + 2],
            self._obs[base + 3],
            self._obs[base + 4],
        )


class _DummyPhysics:
    """No-op physics for ControlsHandler when using JS backend (motors are in JS)."""
    def get_joint(self, name):
        return None


class _GameStateProxy:
    """Game state built from last JS getObservation()."""
    def __init__(self):
        self.game_ended = False
        self.fallen = False
        self.jump_landed = False
        self.jumped = False
        self.score = 0.0
        self.high_score = 0.0
        self.score_time = 0.0

    def update(self, obs_result):
        self.game_ended = bool(obs_result.get("gameEnded", False))
        self.score = float(obs_result.get("distance", 0))  # distance in metres (torso x/10)
        # JS returns time = scoreTime/10 (match gym); convert to seconds for Python
        self.score_time = float(obs_result.get("time", 0)) * 10.0
        self.fallen = bool(obs_result.get("fallen", False))
        self.jumped = bool(obs_result.get("jumped", False))
        self.jump_landed = bool(obs_result.get("jumpLanded", False))
        if self.game_ended and obs_result.get("success"):
            self.jump_landed = True
        if self.game_ended and not obs_result.get("success"):
            self.fallen = True


class QWOPGameJS:
    """
    QWOP game using JS physics (Planck.js) inside PyMiniRacer.

    Same public interface as QWOPGame: .physics, .game_state, .controls,
    .initialize(), .start(), .reset(seed), .update(dt).
    """

    def __init__(self, seed=None, verbose=False, headless=True, js_dir=None):
        self.verbose = verbose
        self.headless = headless
        self.seed = seed
        if js_dir is None:
            js_dir = os.path.join(os.path.dirname(__file__), "js")
        self._js_dir = js_dir
        self._ctx = None
        self._physics_proxy = _PhysicsProxy(BODY_ORDER)
        self.game_state = _GameStateProxy()
        from .controls import ControlsHandler
        self.controls = ControlsHandler(_DummyPhysics())
        self.pause = False
        self.first_click = True
        self.help_up = False
        self.score_time = 0.0
        self.camera_x = INITIAL_CAMERA_X
        self.camera_y = INITIAL_CAMERA_Y
        self.camera_offset = CAMERA_HORIZONTAL_OFFSET

    def _update_camera(self):
        """Update camera position from torso (matches game.py _update_camera)."""
        if not self.first_click:
            return
        torso = self._physics_proxy.get_body("torso")
        if torso is None:
            return
        world_center = torso.worldCenter
        if world_center[1] < CAMERA_VERTICAL_THRESHOLD:
            self.camera_y = world_center[1] * WORLD_SCALE + CAMERA_VERTICAL_OFFSET
        elif not self.game_state.fallen:
            self.camera_x = (world_center[0] + self.camera_offset) * WORLD_SCALE

    def initialize(self):
        try:
            from py_mini_racer import MiniRacer
        except ImportError:
            raise RuntimeError(
                "JS backend requires mini-racer (PyMiniRacer). Install with: pip install mini-racer"
            )
        planck_path = os.path.join(self._js_dir, "planck.min.js")
        physics_path = os.path.join(self._js_dir, "qwop_physics.js")
        if not os.path.isfile(planck_path):
            raise FileNotFoundError(
                "Planck.js not found at %s. See qwop_python/js/README.md to download it."
                % planck_path
            )
        if not os.path.isfile(physics_path):
            raise FileNotFoundError("qwop_physics.js not found at %s" % physics_path)
        self._ctx = MiniRacer()
        with open(planck_path, "r") as f:
            self._ctx.eval(f.read())
        with open(physics_path, "r") as f:
            self._ctx.eval(f.read())
        self.camera_x = INITIAL_CAMERA_X
        self.camera_y = INITIAL_CAMERA_Y
        seed = int(self.seed) if self.seed is not None else 12345
        self._ctx.call("qwop.reset", seed)
        obs_result = self._ctx.call("qwop.getObservation")
        self._sync_from_obs(obs_result)
        if self.verbose:
            print("QWOPGameJS initialized (Planck.js via PyMiniRacer)")

    def _sync_from_obs(self, obs_result):
        obs = obs_result.get("obs")
        if obs is not None:
            self._physics_proxy.set_observation(obs)
        self.game_state.update(obs_result)
        self.score_time = self.game_state.score_time
        self._update_camera()

    def start(self):
        self.first_click = True

    def reset(self, seed=None):
        if seed is not None:
            self.seed = seed
        self.camera_x = INITIAL_CAMERA_X
        self.camera_y = INITIAL_CAMERA_Y
        s = int(self.seed) if self.seed is not None else 12345
        self._ctx.call("qwop.reset", s)
        self.controls.reset()
        obs_result = self._ctx.call("qwop.getObservation")
        self._sync_from_obs(obs_result)
        self.pause = False
        self.first_click = True
        self.help_up = False
        self.score_time = 0.0

    def update(self, dt=None):
        if dt is None:
            dt = PHYSICS_TIMESTEP
        self._ctx.call(
            "qwop.setAction",
            self.controls.q_down,
            self.controls.w_down,
            self.controls.o_down,
            self.controls.p_down,
        )
        self._ctx.call("qwop.step", dt, GAME_TIME_DT)
        obs_result = self._ctx.call("qwop.getObservation")
        self._sync_from_obs(obs_result)

    @property
    def physics(self):
        return self._physics_proxy
