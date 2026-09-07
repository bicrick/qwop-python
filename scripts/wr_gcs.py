#!/usr/bin/env python3
"""Read-only GCS control-plane helpers for the WR dashboard.

Control plane bucket (canonical)::

    gs://qwop-wr-training/
      queue/{pending,running,done,failed}/<job_id>.json
      metrics/runs/<job_id>/heartbeat.json
      artifacts/runs/<job_id>/
      state/{fleet,leaderboard,backlog}.json
      code/

Who writes what (architecture lock-in):
  - Grok Bot (~15m routine): orchestrator — enqueue, reconcile spot fleet,
    kill collapses, update state/*.json
  - Cursor Cloud Agents: code only (this repo) — never create VMs / mutate queue
  - Spot VMs: training only — heartbeats + artifacts; claim/move jobs as directed

This module is **read-only**. Dashboard never enqueues or scales fleet.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_BUCKET = "gs://qwop-wr-training"
QUEUE_STATES = ("pending", "running", "done", "failed")


def parse_gs_uri(uri: str) -> tuple[str, str]:
    """gs://bucket/prefix → (bucket, prefix)."""
    if not uri.startswith("gs://"):
        raise ValueError("URI must start with gs:// (got %r)" % uri)
    rest = uri[5:]
    bucket, _, prefix = rest.partition("/")
    if not bucket:
        raise ValueError("missing bucket in %s" % uri)
    return bucket, prefix.lstrip("/")


def normalize_bucket(bucket: str | None) -> str | None:
    if not bucket:
        return None
    b = bucket.strip().rstrip("/")
    if not b.startswith("gs://"):
        b = "gs://" + b
    return b


# ---------------------------------------------------------------------------
# Low-level I/O (GCS or local fixture mirror)
# ---------------------------------------------------------------------------
def _list_gcs_json(bucket: str, prefix: str) -> list[tuple[str, dict]]:
    """Return [(gs_path, obj), ...] for *.json under gs://bucket/prefix."""
    bucket_name, _ = parse_gs_uri(bucket if bucket.startswith("gs://") else "gs://" + bucket)
    # If bucket already includes path, parse carefully
    if bucket.startswith("gs://"):
        bucket_name, base = parse_gs_uri(bucket)
        full_prefix = "/".join(p for p in (base, prefix) if p).lstrip("/")
    else:
        full_prefix = prefix.lstrip("/")

    out: list[tuple[str, dict]] = []

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        for blob in client.list_blobs(bucket_name, prefix=full_prefix):
            if not blob.name.endswith(".json"):
                continue
            try:
                data = json.loads(blob.download_as_text())
            except Exception as ex:
                data = {"_error": str(ex), "_path": blob.name}
            if isinstance(data, dict):
                gs = "gs://%s/%s" % (bucket_name, blob.name)
                out.append((gs, data))
        return out
    except ImportError:
        pass
    except Exception as ex:
        return [("_gcs_error", {"error": "gcs list failed: %s" % ex})]

    list_uri = "gs://%s/%s" % (bucket_name, full_prefix)
    try:
        proc = subprocess.run(
            ["gsutil", "ls", "-r", list_uri],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except FileNotFoundError:
        return [
            (
                "_gcs_error",
                {
                    "error": "Install google-cloud-storage or gsutil to read GCS "
                    "(or pass --fixture-dir for local mirror)"
                },
            )
        ]
    except Exception as ex:
        return [("_gcs_error", {"error": str(ex)})]

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if "matched no objects" in err.lower() or "one or more urls matched no" in err.lower():
            return []
        return [("_gcs_error", {"error": err or "gsutil ls failed"})]

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".json"):
            continue
        try:
            cat = subprocess.run(
                ["gsutil", "cat", line],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if cat.returncode != 0:
                continue
            data = json.loads(cat.stdout)
            if isinstance(data, dict):
                out.append((line, data))
        except Exception:
            continue
    return out


def _read_gcs_object(bucket: str, rel_path: str) -> dict | None:
    items = _list_gcs_json(bucket, rel_path if rel_path.endswith(".json") else rel_path)
    # Exact file: list may return the file or prefix children
    target = rel_path.lstrip("/")
    for gs, data in items:
        if gs.endswith("/" + target) or gs.endswith(target):
            return data
    # Single object download fallback
    if bucket.startswith("gs://"):
        bucket_name, base = parse_gs_uri(bucket)
        blob_path = "/".join(p for p in (base, target) if p)
        uri = "gs://%s/%s" % (bucket_name, blob_path)
    else:
        uri = "gs://%s/%s" % (bucket, target)

    try:
        from google.cloud import storage  # type: ignore

        bname, bpath = parse_gs_uri(uri)
        client = storage.Client()
        blob = client.bucket(bname).blob(bpath)
        if not blob.exists():
            return None
        data = json.loads(blob.download_as_text())
        return data if isinstance(data, dict) else None
    except ImportError:
        pass
    except Exception:
        return None

    try:
        cat = subprocess.run(
            ["gsutil", "cat", uri],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if cat.returncode != 0:
            return None
        data = json.loads(cat.stdout)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _fixture_list_json(fixture_dir: Path, prefix: str) -> list[tuple[str, dict]]:
    """Mirror GCS layout under a local directory."""
    root = fixture_dir / prefix
    out: list[tuple[str, dict]] = []
    if not root.exists():
        return out
    paths = [root] if root.is_file() else list(root.rglob("*.json"))
    if root.is_file() and root.suffix == ".json":
        paths = [root]
    for p in paths:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text())
        except Exception as ex:
            data = {"_error": str(ex)}
        if isinstance(data, dict):
            rel = p.relative_to(fixture_dir).as_posix()
            out.append(("fixture://%s" % rel, data))
    return out


def _fixture_read(fixture_dir: Path, rel_path: str) -> dict | None:
    p = fixture_dir / rel_path
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Control-plane reads
# ---------------------------------------------------------------------------
def read_queue_depth(
    bucket: str | None = None,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    """Count jobs per queue/{pending,running,done,failed}/."""
    depth = {s: 0 for s in QUEUE_STATES}
    jobs: dict[str, list[dict]] = {s: [] for s in QUEUE_STATES}
    errors: list[str] = []

    for state in QUEUE_STATES:
        prefix = "queue/%s/" % state
        if fixture_dir is not None:
            items = _fixture_list_json(fixture_dir, prefix)
        elif bucket:
            items = _list_gcs_json(bucket, prefix)
        else:
            items = []
        for gs, data in items:
            if gs == "_gcs_error" or data.get("error") and "_error" in str(data):
                if data.get("error"):
                    errors.append(str(data["error"]))
                continue
            if data.get("error") and len(data) <= 2 and "run_id" not in data and "job_id" not in data:
                errors.append(str(data.get("error")))
                continue
            depth[state] += 1
            entry = dict(data)
            entry.setdefault("job_id", Path(gs).stem)
            entry["_path"] = gs
            entry["_queue_state"] = state
            jobs[state].append(entry)

    return {
        "depth": depth,
        "pending": depth["pending"],
        "running": depth["running"],
        "done": depth["done"],
        "failed": depth["failed"],
        "total_active": depth["pending"] + depth["running"],
        "jobs": jobs,
        "errors": errors,
    }


def read_state_object(
    name: str,
    bucket: str | None = None,
    fixture_dir: Path | None = None,
) -> dict | None:
    """Read state/{name}.json (fleet, leaderboard, backlog)."""
    rel = "state/%s.json" % name
    if fixture_dir is not None:
        return _fixture_read(fixture_dir, rel)
    if not bucket:
        return None
    return _read_gcs_object(bucket, rel)


def read_heartbeats(
    bucket: str | None = None,
    fixture_dir: Path | None = None,
) -> list[dict]:
    """Read metrics/runs/*/heartbeat.json."""
    prefix = "metrics/runs/"
    if fixture_dir is not None:
        items = _fixture_list_json(fixture_dir, prefix)
    elif bucket:
        items = _list_gcs_json(bucket, prefix)
    else:
        return []

    out: list[dict] = []
    for gs, data in items:
        if not gs.endswith("heartbeat.json") and "heartbeat" not in Path(gs).name:
            # Allow any json under metrics/runs/ for flexibility
            if "/metrics/runs/" not in gs and not gs.startswith("fixture://metrics/runs/"):
                continue
        if gs == "_gcs_error":
            out.append({"run_id": "_gcs_error", "source": "gcp", "error": data.get("error")})
            continue
        row = dict(data)
        row.setdefault("source", "gcp")
        row.setdefault("gcs_path", gs)
        if "run_id" not in row and "job_id" in row:
            row["run_id"] = row["job_id"]
        out.append(row)
    return out


def read_control_plane(
    bucket: str | None = DEFAULT_BUCKET,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    """Full read-only snapshot used by the dashboard."""
    bucket = normalize_bucket(bucket) if bucket and fixture_dir is None else (
        None if fixture_dir is not None else normalize_bucket(bucket)
    )
    queue = read_queue_depth(bucket=bucket, fixture_dir=fixture_dir)
    fleet = read_state_object("fleet", bucket=bucket, fixture_dir=fixture_dir) or {}
    leaderboard = read_state_object("leaderboard", bucket=bucket, fixture_dir=fixture_dir) or {}
    backlog = read_state_object("backlog", bucket=bucket, fixture_dir=fixture_dir) or {}
    heartbeats = read_heartbeats(bucket=bucket, fixture_dir=fixture_dir)

    fleet_size = fleet.get("size")
    if fleet_size is None:
        instances = fleet.get("instances") or fleet.get("vms") or []
        if isinstance(instances, list):
            fleet_size = len(instances)
        else:
            fleet_size = fleet.get("desired") or fleet.get("running") or 0

    return {
        "bucket": bucket or (str(fixture_dir) if fixture_dir else None),
        "queue": queue,
        "fleet": fleet,
        "fleet_size": int(fleet_size or 0),
        "leaderboard": leaderboard,
        "backlog": backlog,
        "heartbeats": heartbeats,
        "roles": {
            "orchestrator": "Grok Bot (~15m routine): enqueue, reconcile spot fleet, kill collapses",
            "code": "Cursor Cloud Agents: code only",
            "trainers": "Spot VMs: training only (heartbeats + artifacts)",
            "dashboard": "read-only",
        },
    }
