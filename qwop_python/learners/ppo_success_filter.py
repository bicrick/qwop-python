"""
PPOSuccessFilter: PPO that trains only on successful episodes.

Uses SuccessFilteredRolloutBuffer to exclude failed-episode transitions
from policy updates. Used for PPO5.
"""

from stable_baselines3 import PPO

from ..buffers import SuccessFilteredRolloutBuffer


class PPOSuccessFilter(PPO):
    """
    PPO with success-only episode filtering.

    Only transitions from episodes that finish successfully (is_success=1)
    contribute to the policy gradient. Failed episodes are ignored entirely.
    """

    def __init__(self, *args, **kwargs):
        kwargs["rollout_buffer_class"] = SuccessFilteredRolloutBuffer
        kwargs.setdefault("rollout_buffer_kwargs", {})
        super().__init__(*args, **kwargs)

    def train(self) -> None:
        """Skip training when no successful transitions (avoids NaN from empty batches)."""
        buffer = self.rollout_buffer
        if hasattr(buffer, "_n_successful") and buffer._n_successful == 0:
            return
        super().train()
