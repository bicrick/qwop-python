"""CheckpointCallback that uploads each saved .zip to GCS when configured."""

from __future__ import annotations

from typing import Optional

from stable_baselines3.common.callbacks import CheckpointCallback

from ..tools.gcs_artifacts import resolve_artifact_prefix, upload_artifact


class GcsCheckpointCallback(CheckpointCallback):
    """SB3 CheckpointCallback + optional mid-run GCS upload.

    After each local ``model_*_steps.zip`` save, best-effort upload to
    ``QWOP_GCS_ARTIFACT_PREFIX`` (or ``gcs_prefix``). Unset prefix → identical
    to CheckpointCallback (local-only).
    """

    def __init__(
        self,
        *args,
        gcs_prefix: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.gcs_prefix = resolve_artifact_prefix(gcs_prefix)

    def _on_step(self) -> bool:
        result = super()._on_step()
        if self.gcs_prefix and self.n_calls % self.save_freq == 0:
            model_path = self._checkpoint_path(extension="zip")
            upload_artifact(model_path, prefix=self.gcs_prefix)
        return result
