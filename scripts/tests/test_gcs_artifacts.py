#!/usr/bin/env python3
"""Unit tests for mid-run GCS artifact upload helpers.

Does not call real GCS — mocks CLI/SDK and exercises env-var gating.
Imports gcs_artifacts.py by path so this runs without SB3 installed.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "qwop_python" / "tools" / "gcs_artifacts.py"


def _load():
    spec = importlib.util.spec_from_file_location("gcs_artifacts", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load()
resolve_artifact_prefix = _mod.resolve_artifact_prefix
gcs_uri_for_file = _mod.gcs_uri_for_file
upload_artifact = _mod.upload_artifact
ENV_PREFIX = _mod.ENV_PREFIX


def test_resolve_unset_is_none() -> None:
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop(ENV_PREFIX, None)
        assert resolve_artifact_prefix() is None
        assert resolve_artifact_prefix("") is None
        assert resolve_artifact_prefix("   ") is None


def test_resolve_normalizes_trailing_slash() -> None:
    prefix = "gs://qwop-wr-training/artifacts/runs/job-1"
    assert resolve_artifact_prefix(prefix) == prefix + "/"
    assert resolve_artifact_prefix(prefix + "/") == prefix + "/"


def test_gcs_uri_uses_basename() -> None:
    dest = gcs_uri_for_file(
        "data/scout-qrdqn-abc/model_1000_steps.zip",
        "gs://qwop-wr-training/artifacts/runs/job-1/",
    )
    assert dest == (
        "gs://qwop-wr-training/artifacts/runs/job-1/model_1000_steps.zip"
    )


def test_upload_noop_when_unset(tmp_path: Path | None = None) -> None:
    # Compatible with plain unittest-style call (no pytest tmp_path).
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "model_100_steps.zip"
        local.write_bytes(b"fake")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_PREFIX, None)
            assert upload_artifact(str(local)) is None


def test_upload_uses_gcloud_when_prefix_set() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "model_200_steps.zip"
        local.write_bytes(b"fake")
        prefix = "gs://qwop-wr-training/artifacts/runs/job-x/"
        env = {ENV_PREFIX: prefix}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(_mod.shutil, "which", side_effect=lambda c: c == "gcloud"):
                with mock.patch.object(_mod.subprocess, "run") as run:
                    run.return_value = mock.Mock(returncode=0)
                    dest = upload_artifact(str(local))
        assert dest == prefix + "model_200_steps.zip"
        run.assert_called_once()
        cmd = run.call_args[0][0]
        assert cmd[:3] == ["gcloud", "storage", "cp"]
        assert cmd[3] == str(local)
        assert cmd[4] == dest


def test_upload_falls_back_to_gsutil() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "model.zip"
        local.write_bytes(b"fake")
        prefix = "gs://bucket/artifacts/runs/j/"
        with mock.patch.dict(os.environ, {ENV_PREFIX: prefix}, clear=False):
            with mock.patch.object(
                _mod.shutil, "which", side_effect=lambda c: c == "gsutil"
            ):
                with mock.patch.object(_mod.subprocess, "run") as run:
                    run.return_value = mock.Mock(returncode=0)
                    dest = upload_artifact(str(local))
        assert dest == prefix + "model.zip"
        assert run.call_args[0][0][:2] == ["gsutil", "cp"]


def test_upload_missing_file_returns_none() -> None:
    with mock.patch.dict(
        os.environ,
        {ENV_PREFIX: "gs://bucket/artifacts/runs/j/"},
        clear=False,
    ):
        assert upload_artifact("/no/such/model.zip") is None


def main() -> int:
    tests = [
        test_resolve_unset_is_none,
        test_resolve_normalizes_trailing_slash,
        test_gcs_uri_uses_basename,
        test_upload_noop_when_unset,
        test_upload_uses_gcloud_when_prefix_set,
        test_upload_falls_back_to_gsutil,
        test_upload_missing_file_returns_none,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("ok", fn.__name__)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__, exc, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
