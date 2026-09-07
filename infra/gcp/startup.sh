#!/usr/bin/env bash
# GCE startup script for QWOP WR spot workers.
# Reads instance metadata for config / run_id / code source, trains, and
# writes heartbeat JSON to gs://qwop-wr-training/metrics/runs/<id>/heartbeat.json
#
# Metadata keys (optional unless noted):
#   run-id          — unique run id (default: hostname-timestamp)
#   train-config    — path relative to repo root (default: config/train_ppo.yml)
#   git-url         — git clone URL (if set, preferred over tarball)
#   git-ref         — branch/tag/sha (default: main)
#   code-tarball    — gs:// URI of source tarball
#   metrics-bucket  — default gs://qwop-wr-training
#   max-timesteps   — optional CLI override
#   heartbeat-secs  — default 60
#
# No secrets here — relies on the VM service account for GCS.

set -euo pipefail

META_URL="http://metadata.google.internal/computeMetadata/v1"
META_HEADER=("Metadata-Flavor: Google")

meta() {
  local key="$1"
  curl -sf -H "${META_HEADER[@]}" "${META_URL}/instance/attributes/${key}" 2>/dev/null || true
}

meta_zone() {
  curl -sf -H "${META_HEADER[@]}" "${META_URL}/instance/zone" 2>/dev/null | awk -F/ '{print $NF}'
}

HOSTNAME="$(hostname)"
ZONE="$(meta_zone)"
RUN_ID="$(meta run-id)"
TRAIN_CONFIG="$(meta train-config)"
GIT_URL="$(meta git-url)"
GIT_REF="$(meta git-ref)"
CODE_TARBALL="$(meta code-tarball)"
METRICS_BUCKET="$(meta metrics-bucket)"
MAX_TIMESTEPS="$(meta max-timesteps)"
HEARTBEAT_SECS="$(meta heartbeat-secs)"

RUN_ID="${RUN_ID:-${HOSTNAME}-$(date -u +%Y%m%d%H%M%S)}"
TRAIN_CONFIG="${TRAIN_CONFIG:-config/train_ppo.yml}"
GIT_REF="${GIT_REF:-main}"
METRICS_BUCKET="${METRICS_BUCKET:-gs://qwop-wr-training}"
HEARTBEAT_SECS="${HEARTBEAT_SECS:-60}"
CODE_TARBALL="${CODE_TARBALL:-gs://qwop-wr-training/code/qwop-python.tgz}"

WORK_ROOT="/opt/qwop"
REPO_DIR="${WORK_ROOT}/qwop-python"
METRICS_DIR="${WORK_ROOT}/metrics"
HB_LOCAL="${METRICS_DIR}/heartbeat.json"
HB_GCS="${METRICS_BUCKET}/metrics/runs/${RUN_ID}/heartbeat.json"
VENV="${WORK_ROOT}/venv"
LOG="${WORK_ROOT}/train.log"

mkdir -p "$WORK_ROOT" "$METRICS_DIR"
exec > >(tee -a "$LOG") 2>&1

echo "[startup] run_id=${RUN_ID} zone=${ZONE} config=${TRAIN_CONFIG}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv git curl ca-certificates \
  build-essential swig libgl1

# Fetch code
rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR"
if [[ -n "${GIT_URL}" ]]; then
  echo "[startup] cloning ${GIT_URL} @ ${GIT_REF}"
  git clone --depth 1 --branch "$GIT_REF" "$GIT_URL" "$REPO_DIR" \
    || git clone "$GIT_URL" "$REPO_DIR" && (cd "$REPO_DIR" && git checkout "$GIT_REF")
else
  echo "[startup] fetching tarball ${CODE_TARBALL}"
  TMP_TGZ="/tmp/qwop-python.tgz"
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp "$CODE_TARBALL" "$TMP_TGZ"
  else
    # gsutil ships with google-cloud-cli image; install if missing
    apt-get install -y --no-install-recommends apt-transport-https gnupg
    # Prefer gcloud storage via snap/package if present; else curl signed URL not used (SA).
    if command -v gsutil >/dev/null 2>&1; then
      gsutil cp "$CODE_TARBALL" "$TMP_TGZ"
    else
      echo "[startup] installing google-cloud-cli for GCS access"
      # Minimal: use python google-cloud-storage after venv — first get tarball via pip+ADC later
      pip3 install --break-system-packages google-cloud-storage 2>/dev/null \
        || pip3 install google-cloud-storage
      python3 - <<PY
from google.cloud import storage
uri = "${CODE_TARBALL}"
assert uri.startswith("gs://")
bucket_name, _, blob_name = uri[5:].partition("/")
client = storage.Client()
client.bucket(bucket_name).blob(blob_name).download_to_filename("${TMP_TGZ}")
print("downloaded", uri)
PY
    fi
  fi
  tar -xzf "$TMP_TGZ" -C "$REPO_DIR"
fi

cd "$REPO_DIR"
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
pip install -U pip setuptools wheel
pip install -e ".[sb3]"
pip install google-cloud-storage

write_heartbeat() {
  local status="$1"
  local steps="${2:-}"
  local success="${3:-}"
  local ep_rew="${4:-}"
  local best_hud="${5:-}"
  local last_hud="${6:-}"
  local fps="${7:-}"
  python3 - <<PY
import json, os
from datetime import datetime, timezone
from pathlib import Path

def num(x):
    if x is None or x == "" or x == "None":
        return None
    try:
        return float(x)
    except Exception:
        return None

payload = {
    "run_id": os.environ["RUN_ID"],
    "hostname": os.environ["HOSTNAME"],
    "zone": os.environ.get("ZONE") or None,
    "steps": num(os.environ.get("HB_STEPS")),
    "success_rate": num(os.environ.get("HB_SUCCESS")),
    "ep_rew_mean": num(os.environ.get("HB_EP_REW")),
    "best_hud_time": num(os.environ.get("HB_BEST_HUD")),
    "last_hud_time": num(os.environ.get("HB_LAST_HUD")),
    "fps": num(os.environ.get("HB_FPS")),
    "status": os.environ["HB_STATUS"],
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "config": os.environ.get("TRAIN_CONFIG"),
    "source": "gcp",
}
Path(os.environ["HB_LOCAL"]).write_text(json.dumps(payload, indent=2) + "\\n")
print("heartbeat", payload["status"], payload["updated_at"])
PY
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp "$HB_LOCAL" "$HB_GCS" || true
  else
    python3 - <<PY
from google.cloud import storage
from pathlib import Path
uri = "${HB_GCS}"
bucket_name, _, blob_name = uri[5:].partition("/")
client = storage.Client()
client.bucket(bucket_name).blob(blob_name).upload_from_filename("${HB_LOCAL}")
print("uploaded", uri)
PY
  fi
}

export RUN_ID HOSTNAME ZONE TRAIN_CONFIG HB_LOCAL
export HB_STATUS=starting HB_STEPS= HB_SUCCESS= HB_EP_REW= HB_BEST_HUD= HB_LAST_HUD= HB_FPS=
write_heartbeat starting

# Side-car: poll TensorBoard metrics from expected out dirs and refresh heartbeat
heartbeat_loop() {
  while true; do
    sleep "$HEARTBEAT_SECS"
    # Best-effort scrape via monitor_runs if event files exist
    METRICS_JSON="$(python3 - <<'PY' || true
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
try:
    import monitor_runs
except Exception as e:
    print(json.dumps({"error": str(e)}))
    raise SystemExit(0)
rows = monitor_runs.collect_all_local_rows(Path("data"))
# Prefer matching run_id, else first row with steps
import os
rid = os.environ.get("RUN_ID", "")
chosen = None
for r in rows:
    if r.get("run_id") and rid and rid in str(r["run_id"]):
        chosen = r
        break
if chosen is None and rows:
    chosen = rows[0]
print(json.dumps(chosen or {}))
PY
)"
    HB_STATUS=running
    HB_STEPS="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("steps") or "")' "$METRICS_JSON")"
    HB_SUCCESS="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("success_rate") if d.get("success_rate") is not None else "")' "$METRICS_JSON")"
    HB_EP_REW="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("ep_rew") if d.get("ep_rew") is not None else "")' "$METRICS_JSON")"
    HB_BEST_HUD="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("best_hud_time") if d.get("best_hud_time") is not None else "")' "$METRICS_JSON")"
    HB_LAST_HUD="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("last_hud_time") if d.get("last_hud_time") is not None else "")' "$METRICS_JSON")"
    HB_FPS="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("fps") if d.get("fps") is not None else "")' "$METRICS_JSON")"
    export HB_STATUS HB_STEPS HB_SUCCESS HB_EP_REW HB_BEST_HUD HB_LAST_HUD HB_FPS
    write_heartbeat running || true
  done
}

heartbeat_loop &
HB_PID=$!

TRAIN_CMD=(python -m qwop_python.tools.main -c "$TRAIN_CONFIG")
# Prefer installed entrypoint when available
if command -v qwop-python >/dev/null 2>&1; then
  # Infer action from config filename when possible
  ACTION="train_ppo"
  case "$TRAIN_CONFIG" in
    *qrdqn*) ACTION="train_qrdqn" ;;
    *dqn*) ACTION="train_dqn" ;;
    *rppo*) ACTION="train_rppo" ;;
    *a2c*) ACTION="train_a2c" ;;
    *ppo*) ACTION="train_ppo" ;;
  esac
  TRAIN_CMD=(qwop-python -c "$TRAIN_CONFIG" --run-id "$RUN_ID")
  if [[ -n "${MAX_TIMESTEPS}" ]]; then
    TRAIN_CMD+=(--max-timesteps "$MAX_TIMESTEPS")
  fi
  TRAIN_CMD+=("$ACTION")
fi

set +e
"${TRAIN_CMD[@]}"
TRAIN_RC=$?
set -e

kill "$HB_PID" 2>/dev/null || true
if [[ "$TRAIN_RC" -eq 0 ]]; then
  export HB_STATUS=finished
  write_heartbeat finished || true
else
  export HB_STATUS=failed
  write_heartbeat failed || true
fi

exit "$TRAIN_RC"
