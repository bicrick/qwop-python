"""Best-effort mid-run GCS uploads for training checkpoints.

When ``QWOP_GCS_ARTIFACT_PREFIX`` is set (e.g.
``gs://qwop-wr-training/artifacts/runs/<job_id>/``), each saved model
``.zip`` is copied to ``{prefix}/{basename}`` so preempt/kill does not
lose all checkpoints.

Unset → no-op (local training unchanged). Upload failures are logged and
swallowed so training continues.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

ENV_PREFIX = "QWOP_GCS_ARTIFACT_PREFIX"


def resolve_artifact_prefix(explicit: Optional[str] = None) -> Optional[str]:
    """Return a normalized ``gs://...`` prefix, or None when disabled."""
    raw = explicit if explicit is not None else os.environ.get(ENV_PREFIX, "")
    if raw is None:
        return None
    prefix = str(raw).strip()
    if not prefix:
        return None
    return prefix.rstrip("/") + "/"


def gcs_uri_for_file(local_path: str, prefix: str) -> str:
    """Stable object URI: ``{prefix}{basename(local_path)}``."""
    prefix = resolve_artifact_prefix(prefix) or prefix.rstrip("/") + "/"
    return prefix + os.path.basename(local_path)


def _run_cmd(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            "[gcs_artifacts] upload failed (%s): %s"
            % (" ".join(cmd[:3]), exc),
            flush=True,
        )
        return False


def _upload_via_cli(local_path: str, dest_uri: str) -> bool:
    if shutil.which("gcloud"):
        return _run_cmd(["gcloud", "storage", "cp", local_path, dest_uri])
    if shutil.which("gsutil"):
        return _run_cmd(["gsutil", "cp", local_path, dest_uri])
    return False


def _upload_via_sdk(local_path: str, dest_uri: str) -> bool:
    if not dest_uri.startswith("gs://"):
        return False
    try:
        from google.cloud import storage  # type: ignore
    except ImportError:
        return False
    try:
        without = dest_uri[len("gs://") :]
        bucket_name, _, blob_name = without.partition("/")
        if not bucket_name or not blob_name:
            return False
        client = storage.Client()
        client.bucket(bucket_name).blob(blob_name).upload_from_filename(local_path)
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort; never abort train
        print("[gcs_artifacts] SDK upload failed: %s" % exc, flush=True)
        return False


def upload_artifact(
    local_path: str,
    prefix: Optional[str] = None,
) -> Optional[str]:
    """Upload ``local_path`` under the artifact prefix if enabled.

    Returns the destination URI on success, None when skipped or failed.
    """
    resolved = resolve_artifact_prefix(prefix)
    if resolved is None:
        return None
    if not local_path or not os.path.isfile(local_path):
        print(
            "[gcs_artifacts] skip missing file: %s" % local_path,
            flush=True,
        )
        return None

    dest = gcs_uri_for_file(local_path, resolved)
    ok = _upload_via_cli(local_path, dest) or _upload_via_sdk(local_path, dest)
    if ok:
        print("[gcs_artifacts] uploaded %s -> %s" % (local_path, dest), flush=True)
        return dest
    print(
        "[gcs_artifacts] no uploader succeeded for %s "
        "(need gcloud, gsutil, or google-cloud-storage)" % local_path,
        flush=True,
    )
    return None
