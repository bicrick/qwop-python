"""
Anti-scrape / high-CoG reward curriculum (WR Experiment A).

Phase A (shaping on):
  - Reward forward velocity and upright torso / CoM height.
  - Penalize knee/ground scrape: low torso + high knee flexion (thigh-drag).
  - Optional small knee-flexion penalty (keeps strides more extended).

Phase B (pure velocity):
  - Anneal posture / scrape / knee penalties toward 0 via set_progress(),
    or load a Phase B YAML with near-zero penalty weights.
  - Velocity (and optional height) incentives remain the main signal.

Experiment B scaffolding:
  - Optional knee_extension_bonus_weight rewards extended knees (near upper
    joint limit). Default 0; turn on in a later Exp B config.

Do NOT change fall detection — original JS is head/arms/forearms only (no torso).

See doc/WR_EXPERIMENTS.md for the full A–E plan.
"""

from __future__ import annotations

import numpy as np
import gymnasium as gymnasium


# Knee joints: more negative angle ~= more flexed (see data.py joint limits).
_KNEE_JOINTS = (
    ("leftKnee", -1.6, 0.0),    # lower, upper
    ("rightKnee", -1.3, 0.3),
)


class AntiScrapeCurriculumWrapper(gymnasium.Wrapper):
    """
    Curriculum wrapper for upright-stride learning, then velocity fine-tune.

    Reward additions each step (on top of the base env reward)::

        + velocity_weight * max(0, forward_velocity)
        + height_weight   * max(0, torso_height - height_floor)
        - scrape_weight   * scrape_signal          # low torso AND flexed knees
        - knee_flex_weight * mean_knee_flexion     # optional small penalty
        + knee_extension_bonus_weight * mean_extension  # Exp B scaffold (default 0)

    Annealing (Phase A → B within one run):
      Call ``set_progress(progress_remaining)`` from VelocityRewardSchedulerCallback
      (already wired in train_sb3). Penalty weights lerp from initial_* toward
      final_* as training progresses. Set final_* near 0 for pure-velocity Phase B.

    Config knobs (YAML ``env_wrappers[].kwargs``):
      velocity_weight, height_weight, height_floor,
      scrape_weight, scrape_torso_max_height, scrape_flexion_min,
      knee_flex_weight, knee_extension_bonus_weight,
      initial_*/final_* penalty weights + anneal_ramp_fraction / anneal_hold_fraction.
    """

    def __init__(
        self,
        env,
        # Phase A core signals
        velocity_weight: float = 0.5,
        height_weight: float = 0.2,
        height_floor: float = 1.2,
        scrape_weight: float = 0.5,
        scrape_torso_max_height: float = 1.0,
        scrape_flexion_min: float = 0.45,
        knee_flex_weight: float = 0.05,
        # Exp B scaffold (off by default)
        knee_extension_bonus_weight: float = 0.0,
        # Anneal targets for posture-related penalties (Phase B = near zero)
        initial_scrape_weight: float | None = None,
        final_scrape_weight: float = 0.0,
        initial_height_weight: float | None = None,
        final_height_weight: float | None = None,
        initial_knee_flex_weight: float | None = None,
        final_knee_flex_weight: float = 0.0,
        anneal_ramp_fraction: float = 1.0,
        anneal_hold_fraction: float = 0.0,
        anneal_penalties: bool = False,
    ):
        super().__init__(env)

        self.velocity_weight = float(velocity_weight)
        self.height_floor = float(height_floor)
        self.scrape_torso_max_height = float(scrape_torso_max_height)
        self.scrape_flexion_min = float(scrape_flexion_min)
        self.knee_extension_bonus_weight = float(knee_extension_bonus_weight)

        # Active (possibly annealed) weights
        self.scrape_weight = float(scrape_weight)
        self.height_weight = float(height_weight)
        self.knee_flex_weight = float(knee_flex_weight)

        # Anneal endpoints — default initial_* to the Phase A weights above
        self.initial_scrape_weight = (
            float(scrape_weight) if initial_scrape_weight is None
            else float(initial_scrape_weight)
        )
        self.final_scrape_weight = float(final_scrape_weight)
        self.initial_height_weight = (
            float(height_weight) if initial_height_weight is None
            else float(initial_height_weight)
        )
        self.final_height_weight = (
            float(height_weight) if final_height_weight is None
            else float(final_height_weight)
        )
        self.initial_knee_flex_weight = (
            float(knee_flex_weight) if initial_knee_flex_weight is None
            else float(initial_knee_flex_weight)
        )
        self.final_knee_flex_weight = float(final_knee_flex_weight)
        self.anneal_ramp_fraction = float(anneal_ramp_fraction)
        self.anneal_hold_fraction = float(anneal_hold_fraction)
        self.anneal_penalties = bool(anneal_penalties)

        self._progress_remaining = 1.0
        self.last_distance = 0.0
        self.last_time = 0.0
        self.shaped_reward_components = {}

    # ------------------------------------------------------------------ progress
    def set_progress(self, progress_remaining: float):
        """
        Update annealed weights from training progress.

        Called by VelocityRewardSchedulerCallback (same hook as
        ProgressiveVelocityIncentiveWrapper). No-op unless anneal_penalties=True.
        """
        self._progress_remaining = float(progress_remaining)
        if not self.anneal_penalties:
            return

        fraction_done = 1.0 - self._progress_remaining
        if fraction_done <= self.anneal_hold_fraction:
            ramp = 0.0
        else:
            span = max(1e-6, self.anneal_ramp_fraction - self.anneal_hold_fraction)
            ramp = min(1.0, (fraction_done - self.anneal_hold_fraction) / span)

        self.scrape_weight = self._lerp(
            self.initial_scrape_weight, self.final_scrape_weight, ramp
        )
        self.height_weight = self._lerp(
            self.initial_height_weight, self.final_height_weight, ramp
        )
        self.knee_flex_weight = self._lerp(
            self.initial_knee_flex_weight, self.final_knee_flex_weight, ramp
        )

    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        return a + t * (b - a)

    # ------------------------------------------------------------------ gym API
    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.last_distance = float(info.get("distance", 0.0))
        self.last_time = float(info.get("time", 0.0))
        self.shaped_reward_components = {}
        return obs, info

    def step(self, action):
        obs, base_reward, terminated, truncated, info = self.env.step(action)

        velocity = self._forward_velocity(info)
        torso_height = self._torso_height()
        mean_flexion, mean_extension = self._knee_flexion_extension()

        velocity_bonus = self.velocity_weight * max(0.0, velocity)
        height_bonus = self.height_weight * max(0.0, torso_height - self.height_floor)

        # Scrape: low CoG AND flexed knees (thigh-drag / belly-scoot signature)
        scrape_signal = 0.0
        if (
            torso_height < self.scrape_torso_max_height
            and mean_flexion >= self.scrape_flexion_min
        ):
            low = self.scrape_torso_max_height - torso_height
            scrape_signal = low * mean_flexion
        scrape_penalty = -self.scrape_weight * scrape_signal

        knee_flex_penalty = -self.knee_flex_weight * mean_flexion
        knee_ext_bonus = self.knee_extension_bonus_weight * mean_extension

        shaped = (
            base_reward
            + velocity_bonus
            + height_bonus
            + scrape_penalty
            + knee_flex_penalty
            + knee_ext_bonus
        )

        components = {
            "base": float(base_reward),
            "velocity": float(velocity_bonus),
            "height": float(height_bonus),
            "scrape": float(scrape_penalty),
            "knee_flex": float(knee_flex_penalty),
            "knee_extension": float(knee_ext_bonus),
            "total": float(shaped),
            "torso_height": float(torso_height),
            "mean_knee_flexion": float(mean_flexion),
            "scrape_weight": float(self.scrape_weight),
            "height_weight": float(self.height_weight),
            "knee_flex_weight": float(self.knee_flex_weight),
        }
        self.shaped_reward_components = components
        if "shaped_rewards" not in info:
            info["shaped_rewards"] = {}
        info["shaped_rewards"].update(components)
        info["velocity"] = float(velocity)

        self.last_distance = float(info.get("distance", self.last_distance))
        self.last_time = float(info.get("time", self.last_time))

        return obs, float(shaped), terminated, truncated, info

    # ------------------------------------------------------------------ sensors
    def _forward_velocity(self, info: dict) -> float:
        """Prefer smoothed avgspeed; fall back to instantaneous distance/time."""
        if "avgspeed" in info:
            return max(0.0, float(info["avgspeed"]))
        dist = float(info.get("distance", self.last_distance))
        t = float(info.get("time", self.last_time))
        dt = max(t - self.last_time, 1e-8)
        return max(0.0, (dist - self.last_distance) / dt)

    def _torso_height(self) -> float:
        """
        Positive meters above ground plane.

        QWOP Box2D y is negative-upward (torso start ~ -1.87). Height = -y.
        """
        physics = self._physics()
        if physics is None:
            return 0.0
        torso = physics.get_body("torso")
        if torso is None:
            return 0.0
        return float(-torso.worldCenter[1])

    def _knee_flexion_extension(self) -> tuple[float, float]:
        """
        Mean knee flexion and extension in [0, 1].

        flexion 1 = fully bent (at lower limit); extension 1 = fully straight
        (at upper limit). Used for scrape / Exp B extended-knee shaping.
        """
        physics = self._physics()
        if physics is None:
            return 0.0, 0.0

        flexions = []
        extensions = []
        for name, lower, upper in _KNEE_JOINTS:
            joint = physics.get_joint(name)
            if joint is None:
                continue
            span = max(upper - lower, 1e-6)
            angle = float(joint.angle)
            # 0 at upper (extended), 1 at lower (flexed)
            flexion = float(np.clip((upper - angle) / span, 0.0, 1.0))
            flexions.append(flexion)
            extensions.append(1.0 - flexion)

        if not flexions:
            return 0.0, 0.0
        return float(np.mean(flexions)), float(np.mean(extensions))

    def _physics(self):
        """Unwrap to the QWOP game physics world."""
        env = self.env
        # Walk past other wrappers to reach QWOPEnv.game.physics
        while env is not None:
            game = getattr(env, "game", None)
            if game is not None and hasattr(game, "physics"):
                return game.physics
            env = getattr(env, "env", None)
        return None
