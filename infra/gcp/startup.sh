#!/usr/bin/env bash
# GCE startup script for QWOP WR spot workers (TRAINING ONLY).
#
# Control plane: gs://qwop-wr-training
#   metrics/runs/<job_id>/heartbeat.json
#   artifacts/runs/<job_id>/
#
# Orchestration (enqueue / fleet reconcile / kill collapses) is Grok Bot.
# This script does not mutate queue/ or state/ except via heartbeats+artifacts.
#
# Metadata:
#   job-id          — required for canonical paths (falls back to hostname-ts)
#   train-config    — repo-relative YAML (default config/train_ppo.yml)
#   train-action    — optional explicit CLI action (train_qrdqn, train_ppo, …).
#                     When set, skips filename inference. Prefer this for scouts.
#   git-url / git-ref
#   code-tarball    — default gs://qwop-wr-training/code/qwop-python.tgz
#   metrics-bucket  — default gs://qwop-wr-training
#   max-timesteps   — optional
#   heartbeat-secs  — default 60

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
JOB_ID="$(meta job-id)"
# back-compat
if [[ -z "$JOB_ID" ]]; then
  JOB_ID="$(meta run-id)"
fi
TRAIN_CONFIG="$(meta train-config)"
TRAIN_ACTION="$(meta train-action)"
GIT_URL="$(meta git-url)"
GIT_REF="$(meta git-ref)"
CODE_TARBALL="$(meta code-tarball)"
METRICS_BUCKET="$(meta metrics-bucket)"
MAX_TIMESTEPS="$(meta max-timesteps)"
HEARTBEAT_SECS="$(meta heartbeat-secs)"

JOB_ID="${JOB_ID:-${HOSTNAME}-$(date -u +%Y%m%d%H%M%S)}"
TRAIN_CONFIG="${TRAIN_CONFIG:-config/train_ppo.yml}"
GIT_REF="${GIT_REF:-main}"
METRICS_BUCKET="${METRICS_BUCKET:-gs://qwop-wr-training}"
METRICS_BUCKET="${METRICS_BUCKET%/}"
HEARTBEAT_SECS="${HEARTBEAT_SECS:-60}"
CODE_TARBALL="${CODE_TARBALL:-${METRICS_BUCKET}/code/qwop-python.tgz}"

# Infer qwop-python <action> from config path. Order matters: *qrdqn* MUST be
# matched before *dqn* (and *rppo* before *ppo*), or scout_qrdqn_*.yml becomes
# train_dqn. Prefer metadata train-action when set.
infer_train_action() {
  local cfg="$1"
  local override="${2:-}"
  if [[ -n "$override" ]]; then
    # Accept bare names (qrdqn) or full actions (train_qrdqn)
    case "$override" in
      train_*) echo "$override" ;;
      *) echo "train_${override}" ;;
    esac
    return 0
  fi
  local base
  base="$(basename "$cfg")"
  case "$base" in
    *qrdqn*) echo "train_qrdqn" ;;
    *dqn*)   echo "train_dqn" ;;
    *rppo*)  echo "train_rppo" ;;
    *ppo*)   echo "train_ppo" ;;
    *a2c*)   echo "train_a2c" ;;
    *)       echo "train_ppo" ;;
  esac
}

WORK_ROOT="/opt/qwop"
REPO_DIR="${WORK_ROOT}/qwop-python"
METRICS_DIR="${WORK_ROOT}/metrics"
ART_DIR="${WORK_ROOT}/artifacts"
HB_LOCAL="${METRICS_DIR}/heartbeat.json"
HB_GCS="${METRICS_BUCKET}/metrics/runs/${JOB_ID}/heartbeat.json"
ART_GCS="${METRICS_BUCKET}/artifacts/runs/${JOB_ID}/"
VENV="${WORK_ROOT}/venv"
LOG="${WORK_ROOT}/train.log"

mkdir -p "$WORK_ROOT" "$METRICS_DIR" "$ART_DIR"
exec > >(tee -a "$LOG") 2>&1

echo "[startup] job_id=${JOB_ID} zone=${ZONE} config=${TRAIN_CONFIG}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv git curl ca-certificates \
  build-essential swig libgl1

rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR"
if [[ -n "${GIT_URL}" ]]; then
  echo "[startup] cloning ${GIT_URL} @ ${GIT_REF}"
  git clone --depth 1 --branch "$GIT_REF" "$GIT_URL" "$REPO_DIR" \
    || { git clone "$GIT_URL" "$REPO_DIR"; (cd "$REPO_DIR" && git checkout "$GIT_REF"); }
else
  echo "[startup] fetching tarball ${CODE_TARBALL}"
  TMP_TGZ="/tmp/qwop-python.tgz"
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp "$CODE_TARBALL" "$TMP_TGZ"
  elif command -v gsutil >/dev/null 2>&1; then
    gsutil cp "$CODE_TARBALL" "$TMP_TGZ"
  else
    pip3 install --break-system-packages google-cloud-storage 2>/dev/null \
      || pip3 install google-cloud-storage
    python3 - <<PY
from google.cloud import storage
uri = "${CODE_TARBALL}"
bucket_name, _, blob_name = uri[5:].partition("/")
storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename("${TMP_TGZ}")
PY
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

upload_hb() {
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp "$HB_LOCAL" "$HB_GCS" || true
  else
    python3 - <<PY
from google.cloud import storage
uri = "${HB_GCS}"
bucket_name, _, blob_name = uri[5:].partition("/")
storage.Client().bucket(bucket_name).blob(blob_name).upload_from_filename("${HB_LOCAL}")
PY
  fi
}

write_heartbeat() {
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
    "job_id": os.environ["JOB_ID"],
    "run_id": os.environ["JOB_ID"],
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
  upload_hb || true
}

sync_artifacts() {
  # Best-effort: copy data/ checkpoints for this job into GCS artifacts/
  if [[ -d data ]]; then
    if command -v gcloud >/dev/null 2>&1; then
      gcloud storage cp -r data "${ART_GCS}" || true
    elif command -v gsutil >/dev/null 2>&1; then
      gsutil -m rsync -r data "${ART_GCS}" || true
    fi
  fi
}

export JOB_ID HOSTNAME ZONE TRAIN_CONFIG HB_LOCAL
export HB_STATUS=starting HB_STEPS= HB_SUCCESS= HB_EP_REW= HB_BEST_HUD= HB_LAST_HUD= HB_FPS=
write_heartbeat

heartbeat_loop() {
  while true; do
    sleep "$HEARTBEAT_SECS"
    METRICS_JSON="$(python3 - <<'PY' || true
import json, os, sys
from pathlib import Path
sys.path.insert(0, "scripts")
try:
    import monitor_runs
except Exception as e:
    print(json.dumps({"error": str(e)}))
    raise SystemExit(0)
rows = monitor_runs.collect_all_local_rows(Path("data"))
rid = os.environ.get("JOB_ID", "")
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
    HB_SUCCESS="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); v=d.get("success_rate"); print("" if v is None else v)' "$METRICS_JSON")"
    HB_EP_REW="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); v=d.get("ep_rew"); print("" if v is None else v)' "$METRICS_JSON")"
    HB_BEST_HUD="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); v=d.get("best_hud_time"); print("" if v is None else v)' "$METRICS_JSON")"
    HB_LAST_HUD="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); v=d.get("last_hud_time"); print("" if v is None else v)' "$METRICS_JSON")"
    HB_FPS="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); v=d.get("fps"); print("" if v is None else v)' "$METRICS_JSON")"
    export HB_STATUS HB_STEPS HB_SUCCESS HB_EP_REW HB_BEST_HUD HB_LAST_HUD HB_FPS
    write_heartbeat || true
  done
}

heartbeat_loop &
HB_PID=$!

ACTION="$(infer_train_action "$TRAIN_CONFIG" "$TRAIN_ACTION")"
echo "[startup] train-action=${ACTION} (override='${TRAIN_ACTION:-}' config=${TRAIN_CONFIG})"

TRAIN_CMD=(qwop-python -c "$TRAIN_CONFIG" --run-id "$JOB_ID")
if [[ -n "${MAX_TIMESTEPS}" ]]; then
  TRAIN_CMD+=(--max-timesteps "$MAX_TIMESTEPS")
fi
TRAIN_CMD+=("$ACTION")

set +e
"${TRAIN_CMD[@]}"
TRAIN_RC=$?
set -e

kill "$HB_PID" 2>/dev/null || true
sync_artifacts || true

if [[ "$TRAIN_RC" -eq 0 ]]; then
  export HB_STATUS=finished
else
  export HB_STATUS=failed
fi
write_heartbeat || true
exit "$TRAIN_RC"
