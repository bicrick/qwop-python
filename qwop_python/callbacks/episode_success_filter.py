"""
EpisodeSuccessFilterCallback: Accumulates infos and dones during rollout,
then updates the buffer's success mask in on_rollout_end.

Used with SuccessFilteredRolloutBuffer for PPO5 to filter failed episodes.
"""

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback


class EpisodeSuccessFilterCallback(BaseCallback):
    """
    Accumulates (infos, dones) per step during rollout collection,
    then calls rollout_buffer.update_success_mask() in on_rollout_end.

    Only active when the model's rollout buffer has update_success_mask
    (i.e. SuccessFilteredRolloutBuffer).
    """

    def __init__(self):
        super().__init__()
        self._infos_list: list = []
        self._dones_list: list = []

    def _on_rollout_start(self) -> None:
        self._infos_list = []
        self._dones_list = []

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        dones = self.locals.get("dones", np.array([]))
        if hasattr(dones, "__len__") and len(dones) > 0:
            self._dones_list.append(np.array(dones))
        else:
            self._dones_list.append(np.array([dones]))
        self._infos_list.append(infos)
        return True

    def _on_rollout_end(self) -> None:
        buffer = self.model.rollout_buffer
        if hasattr(buffer, "update_success_mask"):
            buffer.update_success_mask(self._infos_list, self._dones_list)
