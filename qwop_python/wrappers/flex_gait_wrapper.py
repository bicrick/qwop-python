"""
Flexible two-beat cross-gait bonus (QP then WO).

Open-loop search: same-leg QO-then-WP never walks in this sim (stuck ~1.7m).
The cross pairing that finishes 100m is QP then WO, period 1.0s HUD, phase
shift 0.5, start delay 0.2s. Reference holds (cycle seconds, not a clock
the agent must hit):

    Q [0.00, 0.28)   P [0.05, 0.32)   → QP overlap
    W [0.45, 0.84)   O [0.48, 0.68)   → WO overlap

Not a timestamp clone. After the runner is upright, pay a small bonus for
alternating a QP-like beat and a WO-like beat. Early or late is fine. The
env distance / HUD reward stays the primary term. 133.2s HUD on the open-loop
rec is a finish, not a world record.

Hard gait-breakers are penalized lightly, never as the main term:
  - both thighs driven the same way for a sustained stretch
  - knee-scrape (low torso and flexed knees), if that signal exists
"""

from __future__ import annotations

import numpy as np
import gymnasium as gymnasium

from ..data import SCORE_TIME_STEP


# Knee joints: more negative angle ~= more flexed (see data.py joint limits).
_KNEE_JOINTS = (
    ("leftKnee", -1.6, 0.0),
    ("rightKnee", -1.3, 0.3),
)

# Target beats. Same-leg QO / WP are intentionally not in this set.
_CROSS_BEATS = ("QP", "WO")


class FlexibleGaitImitationWrapper(gymnasium.Wrapper):
    """
    Soft QP-then-WO imitation on top of the existing env reward.

    Phase is a short memory of the last cross-pair beat, not a clock locked
    to the open-loop recording or a start delay. A switch from QP-like to
    WO-like (or the reverse) scores inside a wide window around a 0.5s
    half-cycle (1.0s HUD period, phase shift 0.5). Holding one chord
    forever, or driving both thighs the same direction, stops earning the
    bonus and picks up a small penalty.
    """

    def __init__(
        self,
        env,
        # Primary signal is the wrapped env reward. These are nudges.
        hold_bonus: float = 0.04,
        soft_hold_scale: float = 0.55,
        switch_bonus: float = 0.12,
        upright_min_height: float = 1.15,
        # 1.0s HUD period, phase shift 0.5. Slack around that, not a lock.
        ideal_half_s: float = 0.50,
        hold_full_s: float = 0.40,
        switch_lo_s: float = 0.28,
        switch_hi_s: float = 0.85,
        late_ok_s: float = 1.25,
        none_grace_s: float = 0.22,
        none_reset_s: float = 0.45,
        both_thigh_penalty: float = 0.03,
        same_dir_penalty: float = 0.02,
        same_dir_after_s: float = 0.55,
        same_dir_speed: float = 0.20,
        scrape_weight: float = 0.12,
        scrape_torso_max_height: float = 1.0,
        scrape_flexion_min: float = 0.45,
        log_every: int = 500,
    ):
        super().__init__(env)

        self.hold_bonus = float(hold_bonus)
        self.soft_hold_scale = float(soft_hold_scale)
        self.switch_bonus = float(switch_bonus)
        self.upright_min_height = float(upright_min_height)
        self.ideal_half_s = float(ideal_half_s)
        self.hold_full_s = float(hold_full_s)
        self.switch_lo_s = float(switch_lo_s)
        self.switch_hi_s = float(switch_hi_s)
        self.late_ok_s = float(late_ok_s)
        self.none_grace_s = float(none_grace_s)
        self.none_reset_s = float(none_reset_s)
        self.both_thigh_penalty = float(both_thigh_penalty)
        self.same_dir_penalty = float(same_dir_penalty)
        self.same_dir_after_s = float(same_dir_after_s)
        self.same_dir_speed = float(same_dir_speed)
        self.scrape_weight = float(scrape_weight)
        self.scrape_torso_max_height = float(scrape_torso_max_height)
        self.scrape_flexion_min = float(scrape_flexion_min)
        self.log_every = int(log_every)

        base = self._qwop_env()
        n_actions = int(base.action_space.n)
        if n_actions != 16:
            raise RuntimeError(
                "FlexibleGaitImitationWrapper requires the full 16-action set "
                "(reduced_action_set: false); got Discrete(%d)" % n_actions
            )
        # HUD seconds, same clock as the 1.0s open-loop period.
        self._dt = float(base.frames_per_step) * float(SCORE_TIME_STEP)

        self._step_i = 0
        self._ep_steps = 0
        self._beat = None  # "QP" | "WO" | None
        self._beat_age_s = 0.0
        self._gap_s = 0.0
        self._same_dir_s = 0.0
        self._logged_first = False

        print(
            "flex_gait ready: n_actions=%d frames_per_step=%s dt_hud=%.3fs "
            "pattern=QP-then-WO period=1.0s half~%.2fs window=[%.2f, %.2f]s "
            "model_load=none"
            % (
                n_actions,
                base.frames_per_step,
                self._dt,
                self.ideal_half_s,
                self.switch_lo_s,
                self.switch_hi_s,
            ),
            flush=True,
        )

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._ep_steps = 0
        self._beat = None
        self._beat_age_s = 0.0
        self._gap_s = 0.0
        self._same_dir_s = 0.0
        return obs, info

    def step(self, action):
        obs, base_reward, terminated, truncated, info = self.env.step(action)
        self._step_i += 1
        self._ep_steps += 1

        action_i = int(np.asarray(action).reshape(-1)[0])
        beat, kind, both_thighs = self._classify(action_i)
        upright = self._torso_height() >= self.upright_min_height

        gait_bonus = 0.0
        switch_score = 0.0
        hold_score = 0.0
        switched = False

        if not upright:
            # Do not shape a gait while down. Keep phase from locking on a crawl.
            self._beat = None
            self._beat_age_s = 0.0
            self._gap_s = 0.0
        elif beat in _CROSS_BEATS:
            self._gap_s = 0.0
            if self._beat is None:
                self._beat = beat
                self._beat_age_s = 0.0
                hold_score = self._hold_score(0.0, kind)
            elif beat == self._beat:
                hold_score = self._hold_score(self._beat_age_s, kind)
                self._beat_age_s += self._dt
            else:
                switch_score = self._switch_score(self._beat_age_s)
                switched = switch_score > 0.0
                gait_bonus += self.switch_bonus * switch_score
                self._beat = beat
                self._beat_age_s = 0.0
                hold_score = self._hold_score(0.0, kind)
            gait_bonus += self.hold_bonus * hold_score
        elif beat == "none":
            self._gap_s += self._dt
            if self._gap_s > self.none_reset_s:
                self._beat = None
                self._beat_age_s = 0.0
            elif self._beat is not None and self._gap_s <= self.none_grace_s:
                # Short release between the thigh key and the other pair is
                # part of the 0.5s phase shift. Count it so a bit-late switch
                # still lands in the window. Do not pay for holding nothing.
                self._beat_age_s += self._dt
        else:
            # Same-leg QO/WP and other junk: no bonus, not a beat switch.
            # Those chords did not walk in open-loop search.
            self._gap_s += self._dt
            if self._gap_s > self.none_reset_s:
                self._beat = None
                self._beat_age_s = 0.0

        breaker = 0.0
        both_pen = 0.0
        if both_thighs:
            both_pen = -self.both_thigh_penalty
            breaker += both_pen

        same_pen = 0.0
        if upright and self._thighs_same_direction():
            self._same_dir_s += self._dt
            if self._same_dir_s > self.same_dir_after_s:
                overflow = min(1.0, (self._same_dir_s - self.same_dir_after_s) / 1.0)
                same_pen = -self.same_dir_penalty * overflow
                breaker += same_pen
        else:
            self._same_dir_s = 0.0

        scrape_pen, scrape_signal, mean_flexion = self._scrape_penalty()
        breaker += scrape_pen

        shaped = float(base_reward) + gait_bonus + breaker
        torso_h = self._torso_height()

        components = {
            "base": float(base_reward),
            "gait_bonus": float(gait_bonus),
            "gait_hold": float(self.hold_bonus * hold_score) if upright else 0.0,
            "gait_switch": float(self.switch_bonus * switch_score) if upright else 0.0,
            "both_thigh": float(both_pen),
            "same_dir": float(same_pen),
            "scrape": float(scrape_pen),
            "total": float(shaped),
            "beat": self._beat or "",
            "beat_kind": kind,
            "beat_age_s": float(self._beat_age_s),
            "upright": bool(upright),
            "torso_height": float(torso_h),
            "mean_knee_flexion": float(mean_flexion),
            "scrape_signal": float(scrape_signal),
            "switched": bool(switched),
        }
        if "shaped_rewards" not in info:
            info["shaped_rewards"] = {}
        info["shaped_rewards"].update(components)
        info["flex_gait_beat"] = self._beat or ""
        info["flex_gait_upright"] = bool(upright)

        if (not self._logged_first) or (
            self.log_every > 0 and self._step_i % self.log_every == 0
        ):
            self._logged_first = True
            print(
                "flex_gait stepped n=%d ep=%d action=%d beat=%s kind=%s "
                "upright=%s h=%.2f base=%.4f gait=%.4f breaker=%.4f reward=%.4f"
                % (
                    self._step_i,
                    self._ep_steps,
                    action_i,
                    beat,
                    kind,
                    upright,
                    torso_h,
                    float(base_reward),
                    gait_bonus,
                    breaker,
                    shaped,
                ),
                flush=True,
            )

        return obs, shaped, terminated, truncated, info

    # ------------------------------------------------------------------ classify
    def _classify(self, action_index: int):
        """
        Return (beat, kind, both_thighs).

        beat: "QP" | "WO" | "none" | "other"
        kind: "exact" | "soft" | "none" | "other"
        both_thighs: Q and W both requested (physics will take only one).

        Exact: QP (Q+P, not W/O) or WO (W+O, not Q/P).
        Soft: the same cross family with only one of the pair down
        (Q or P leading/trailing the QP beat; W or O leading/trailing WO).
        Same-leg QO and WP are "other" — no bonus.
        """
        keys = self._qwop_env().action_mapper.action_to_keys[action_index]
        q = bool(keys["q"])
        w = bool(keys["w"])
        o = bool(keys["o"])
        p = bool(keys["p"])
        both = q and w

        if q and (not w) and p and (not o):
            return "QP", "exact", both
        if w and (not q) and o and (not p):
            return "WO", "exact", both
        # Cross family without requiring both keys on the same tick.
        if q and (not w) and (not o):
            return "QP", "soft", both
        if p and (not o) and (not q) and (not w):
            return "QP", "soft", both
        if w and (not q) and (not p):
            return "WO", "soft", both
        if o and (not p) and (not q) and (not w):
            return "WO", "soft", both
        if not (q or w or o or p):
            return "none", "none", False
        return "other", "other", both

    def _hold_score(self, age_s: float, kind: str) -> float:
        """Pay for a short cross-pair hold; stop paying if it never flips."""
        base = 1.0 if kind == "exact" else self.soft_hold_scale
        if age_s <= self.hold_full_s:
            return base
        if age_s <= self.switch_hi_s:
            span = max(1e-6, self.switch_hi_s - self.hold_full_s)
            return base * max(0.25, 1.0 - (age_s - self.hold_full_s) / span)
        return 0.0

    def _switch_score(self, age_s: float) -> float:
        """
        Alternation quality around a 0.5s half-cycle. Flat through the
        early/late window so phase does not have to match the recording
        or the 0.2s start delay. Jitter scores 0.
        """
        if age_s < self.switch_lo_s:
            return 0.0
        sweet_lo = max(self.switch_lo_s, self.ideal_half_s - 0.12)
        sweet_hi = min(self.switch_hi_s, self.ideal_half_s + 0.15)
        if sweet_lo <= age_s <= sweet_hi:
            return 1.0
        if age_s < sweet_lo:
            span = max(1e-6, sweet_lo - self.switch_lo_s)
            return 0.75 + 0.25 * ((age_s - self.switch_lo_s) / span)
        if age_s <= self.switch_hi_s:
            span = max(1e-6, self.switch_hi_s - sweet_hi)
            return 0.70 + 0.30 * ((self.switch_hi_s - age_s) / span)
        if age_s <= self.late_ok_s:
            return 0.40
        return 0.15

    # ------------------------------------------------------------------ sensors
    def _qwop_env(self):
        env = self.env
        while env is not None:
            if hasattr(env, "game") and hasattr(env, "action_mapper"):
                return env
            env = getattr(env, "env", None)
        raise RuntimeError("FlexibleGaitImitationWrapper could not find QWOPEnv")

    def _physics(self):
        return self._qwop_env().game.physics

    def _torso_height(self) -> float:
        """Positive meters above the ground plane. Box2D y is negative-up."""
        torso = self._physics().get_body("torso")
        if torso is None:
            return 0.0
        return float(-torso.worldCenter[1])

    def _thighs_same_direction(self) -> bool:
        physics = self._physics()
        left = physics.get_joint("leftHip")
        right = physics.get_joint("rightHip")
        if left is None or right is None:
            return False
        ls = float(left.speed)
        rs = float(right.speed)
        return (ls * rs > 0.0) and abs(ls) > self.same_dir_speed and abs(rs) > self.same_dir_speed

    def _scrape_penalty(self):
        """Light penalty only when torso is low and knees are flexed."""
        physics = self._physics()
        flexions = []
        for name, lower, upper in _KNEE_JOINTS:
            joint = physics.get_joint(name)
            if joint is None:
                continue
            span = max(upper - lower, 1e-6)
            angle = float(joint.angle)
            flexions.append(float(np.clip((upper - angle) / span, 0.0, 1.0)))
        mean_flexion = float(np.mean(flexions)) if flexions else 0.0
        height = self._torso_height()
        signal = 0.0
        if height < self.scrape_torso_max_height and mean_flexion >= self.scrape_flexion_min:
            signal = (self.scrape_torso_max_height - height) * mean_flexion
        return -self.scrape_weight * signal, signal, mean_flexion
