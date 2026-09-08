# =============================================================================
# Copyright 2023 Simeon Manolov <s.manolloff@gmail.com>.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""SB3 learn() timestep budget helpers.

Config / CLI ``total_timesteps`` (and ``--max-timesteps``) always mean the
*additional* env steps to run in this training call.

Stable-Baselines3 treats ``learn(total_timesteps=N, reset_num_timesteps=False)``
as an *absolute* counter: training stops once ``model.num_timesteps >= N``.
Loading a checkpoint that already exceeds N therefore exits immediately with
zero new steps. To preserve checkpoint timestep continuity while still
honouring the requested additional budget, pass
``num_timesteps + requested`` when ``reset_num_timesteps`` is False.

When ``reset_num_timesteps`` is True, SB3 resets the counter and already
interprets ``N`` as additional steps, so the value is passed through unchanged.
"""

from __future__ import annotations


def resolve_learn_total_timesteps(
    requested_timesteps: int,
    num_timesteps: int,
    *,
    reset_num_timesteps: bool = False,
) -> int:
    """Map config additional budget to SB3 ``learn(total_timesteps=...)``.

    Args:
        requested_timesteps: Additional steps requested for this run
            (config ``total_timesteps`` / ``--max-timesteps``).
        num_timesteps: Current ``model.num_timesteps`` after load (or 0).
        reset_num_timesteps: Forwarded to ``model.learn``. Default False
            keeps the loaded counter for TensorBoard / schedule continuity.

    Returns:
        Absolute ``total_timesteps`` argument for ``model.learn`` when
        ``reset_num_timesteps`` is False; otherwise ``requested_timesteps``.
    """
    requested = int(requested_timesteps)
    loaded = int(num_timesteps)
    if requested < 0:
        raise ValueError(
            "requested_timesteps must be >= 0, got %r" % requested_timesteps
        )
    if loaded < 0:
        raise ValueError("num_timesteps must be >= 0, got %r" % num_timesteps)
    if reset_num_timesteps:
        return requested
    return loaded + requested


def format_learn_budget_log(
    *,
    loaded_num_timesteps: int,
    requested_additional: int,
    reset_num_timesteps: bool,
    learn_total_timesteps: int,
) -> str:
    """Single operator-facing line for train.log / stdout."""
    return (
        "Learn timestep budget: loaded num_timesteps=%d, "
        "requested_additional=%d, reset_num_timesteps=%s, "
        "learn(total_timesteps=%d)"
        % (
            int(loaded_num_timesteps),
            int(requested_additional),
            bool(reset_num_timesteps),
            int(learn_total_timesteps),
        )
    )
