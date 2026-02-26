"""
SuccessFilteredRolloutBuffer: Only yields transitions from successful episodes.

Used for PPO5 to train exclusively on runs that finish (jump_landed, not fallen).
Failed episodes are excluded from policy updates entirely.
"""

import logging
import numpy as np
from collections.abc import Generator
from gymnasium import spaces

from stable_baselines3.common.buffers import RolloutBuffer
from stable_baselines3.common.type_aliases import RolloutBufferSamples

logger = logging.getLogger(__name__)


class SuccessFilteredRolloutBuffer(RolloutBuffer):
    """
    Rollout buffer that filters out transitions from failed episodes.

    Call update_success_mask(infos_list, dones_list) after the buffer is filled
    (e.g. from a callback in on_rollout_end) to mark which transitions belong
    to successful episodes. The get() method then only yields batches from
    successful transitions.
    """

    def __init__(
        self,
        buffer_size: int,
        observation_space: spaces.Space,
        action_space: spaces.Space,
        device: str = "auto",
        gae_lambda: float = 1,
        gamma: float = 0.99,
        n_envs: int = 1,
    ):
        super().__init__(
            buffer_size=buffer_size,
            observation_space=observation_space,
            action_space=action_space,
            device=device,
            gae_lambda=gae_lambda,
            gamma=gamma,
            n_envs=n_envs,
        )
        self.success_mask = np.ones((self.buffer_size, self.n_envs), dtype=bool)
        self._n_successful = self.buffer_size * self.n_envs

    def reset(self) -> None:
        super().reset()
        self.success_mask = np.ones((self.buffer_size, self.n_envs), dtype=bool)
        self._n_successful = self.buffer_size * self.n_envs

    def update_success_mask(
        self,
        infos_list: list,
        dones_list: list,
    ) -> None:
        """
        Mark which transitions belong to successful episodes.

        For each (step, env) where the episode ended (dones_list[step][env]),
        find the episode start and set success_mask[start:step+1, env] based on
        is_success from the terminal info.

        :param infos_list: List of infos dicts per step (each step has list of n_envs infos)
        :param dones_list: List of dones arrays per step (each shape (n_envs,))
        """
        n_steps = len(dones_list)
        if n_steps == 0:
            return

        # Track episode start per env (step index where current episode began)
        episode_start: dict[int, int] = {i: 0 for i in range(self.n_envs)}

        for step in range(n_steps):
            if step >= self.buffer_size:
                break

            dones = dones_list[step]
            infos = infos_list[step] if step < len(infos_list) else []

            for env_idx in range(self.n_envs):
                if dones[env_idx]:
                    is_success = False
                    if env_idx < len(infos):
                        info = infos[env_idx]
                        if isinstance(info, dict):
                            is_success = bool(info.get("is_success", 0))
                        elif hasattr(info, "get"):
                            is_success = bool(info.get("is_success", 0))

                    start = episode_start[env_idx]
                    self.success_mask[start : step + 1, env_idx] = is_success
                    episode_start[env_idx] = step + 1
                elif step > 0 and self.episode_starts[step, env_idx]:
                    episode_start[env_idx] = step

        # Exclude incomplete episodes (still running at end of rollout)
        for env_idx in range(self.n_envs):
            start = episode_start[env_idx]
            if start < n_steps:
                self.success_mask[start:n_steps, env_idx] = False

        self._n_successful = int(np.sum(self.success_mask))

    def get(
        self,
        batch_size: int | None = None,
    ) -> Generator[RolloutBufferSamples, None, None]:
        assert self.full, "Buffer must be full before get()"

        if not self.generator_ready:
            _tensor_names = [
                "observations",
                "actions",
                "values",
                "log_probs",
                "advantages",
                "returns",
            ]
            for tensor in _tensor_names:
                self.__dict__[tensor] = self.swap_and_flatten(self.__dict__[tensor])
            self.success_mask_flat = self.swap_and_flatten(
                self.success_mask.astype(np.float32)
            ).astype(bool)
            self.generator_ready = True

        successful_indices = np.where(self.success_mask_flat)[0]
        n_successful = len(successful_indices)

        if n_successful == 0:
            logger.warning(
                "SuccessFilteredRolloutBuffer: zero successful transitions in rollout, skipping training step"
            )
            return

        if batch_size is None:
            batch_size = n_successful

        indices = np.random.permutation(n_successful)
        successful_indices = successful_indices[indices]

        start_idx = 0
        while start_idx < n_successful:
            batch_inds = successful_indices[start_idx : start_idx + batch_size]
            if len(batch_inds) > 0:
                yield self._get_samples(batch_inds)
            start_idx += batch_size
