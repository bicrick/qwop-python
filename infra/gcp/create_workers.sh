#!/usr/bin/env bash
# EXAMPLE helper to create spot n2d-standard-8 trainers.
#
# Live fleet reconcile belongs to Grok Bot. Cursor Cloud Agents should not
# treat this as something to run against production in a PR. Prefer --dry-run.
#
# Usage:
#   ./create_workers.sh --dry-run --count 1 --job-id job-scout-001 \
#       --config config/sweeps/scout_ppo_fps2.yml
#   ./create_workers.sh --dry-run --config config/sweeps/scout_qrdqn.yml \
#       --train-action train_qrdqn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECT_ID="${PROJECT_ID:-qwop-wr}"
ZONE="${ZONE:-us-central1-a}"
MACHINE_TYPE="${MACHINE_TYPE:-n2d-standard-8}"
SA_EMAIL="${SA_EMAIL:-qwop-wr-trainer@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2204-lts}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud}"
METRICS_BUCKET="${METRICS_BUCKET:-gs://qwop-wr-training}"
GIT_URL="${GIT_URL:-}"
GIT_REF="${GIT_REF:-main}"
CODE_TARBALL="${CODE_TARBALL:-gs://qwop-wr-training/code/qwop-python.tgz}"
MAX_TIMESTEPS="${MAX_TIMESTEPS:-}"
JOB_ID="${JOB_ID:-}"
TRAIN_ACTION="${TRAIN_ACTION:-}"
COUNT=1
TRAIN_CONFIG="config/train_ppo.yml"
NAME_PREFIX="qwop-wr"
DRY_RUN=0

# Mirror startup.sh inference so dry-run / logs show the resolved action.
# *qrdqn* before *dqn*, *rppo* before *ppo*. Prefer --train-action when set.
infer_train_action() {
  local cfg="$1"
  local override="${2:-}"
  if [[ -n "$override" ]]; then
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --count) COUNT="$2"; shift 2 ;;
    --config) TRAIN_CONFIG="$2"; shift 2 ;;
    --train-action) TRAIN_ACTION="$2"; shift 2 ;;
    --job-id) JOB_ID="$2"; shift 2 ;;
    --zone) ZONE="$2"; shift 2 ;;
    --project) PROJECT_ID="$2"; shift 2 ;;
    --git-url) GIT_URL="$2"; shift 2 ;;
    --git-ref) GIT_REF="$2"; shift 2 ;;
    --max-timesteps) MAX_TIMESTEPS="$2"; shift 2 ;;
    --prefix) NAME_PREFIX="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

RESOLVED_ACTION="$(infer_train_action "$TRAIN_CONFIG" "$TRAIN_ACTION")"

STARTUP="${SCRIPT_DIR}/startup.sh"
if [[ ! -f "$STARTUP" ]]; then
  echo "Missing startup.sh at $STARTUP" >&2
  exit 1
fi

echo "NOTE: Grok Bot owns live orchestration. This script is an example helper."
echo "Project:     $PROJECT_ID"
echo "Zone:        $ZONE"
echo "Machine:     $MACHINE_TYPE (SPOT)"
echo "SA:          $SA_EMAIL"
echo "Config:      $TRAIN_CONFIG"
echo "Action:      $RESOLVED_ACTION${TRAIN_ACTION:+ (explicit)}"
echo "Bucket:      $METRICS_BUCKET"
echo "Count:       $COUNT"
echo "Labels:      qwop-wr=1"

for i in $(seq 1 "$COUNT"); do
  TS="$(date -u +%Y%m%d%H%M%S)"
  NAME="${NAME_PREFIX}-${TS}-${i}"
  THIS_JOB="${JOB_ID:-$NAME}"

  METADATA=(
    "job-id=${THIS_JOB}"
    "train-config=${TRAIN_CONFIG}"
    "train-action=${RESOLVED_ACTION}"
    "metrics-bucket=${METRICS_BUCKET}"
    "code-tarball=${CODE_TARBALL}"
    "git-ref=${GIT_REF}"
    "heartbeat-secs=60"
  )
  if [[ -n "$GIT_URL" ]]; then
    METADATA+=("git-url=${GIT_URL}")
  fi
  if [[ -n "$MAX_TIMESTEPS" ]]; then
    METADATA+=("max-timesteps=${MAX_TIMESTEPS}")
  fi

  META_FLAGS=()
  for kv in "${METADATA[@]}"; do
    META_FLAGS+=("--metadata=${kv}")
  done

  CMD=(
    gcloud compute instances create "$NAME"
    --project="$PROJECT_ID"
    --zone="$ZONE"
    --machine-type="$MACHINE_TYPE"
    --provisioning-model=SPOT
    --instance-termination-action=STOP
    --service-account="$SA_EMAIL"
    --scopes=cloud-platform
    --image-family="$IMAGE_FAMILY"
    --image-project="$IMAGE_PROJECT"
    --boot-disk-size=50GB
    --labels=qwop-wr=1
    --metadata-from-file=startup-script="$STARTUP"
    "${META_FLAGS[@]}"
  )

  echo "----"
  echo "Creating $NAME (job_id=$THIS_JOB)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf ' %q' "${CMD[@]}"
    echo
  else
    "${CMD[@]}"
  fi
done

echo "Heartbeats → ${METRICS_BUCKET}/metrics/runs/<job_id>/heartbeat.json"
echo "Artifacts  → ${METRICS_BUCKET}/artifacts/runs/<job_id>/"
echo "Dashboard: python scripts/wr_dashboard.py --gcs-bucket ${METRICS_BUCKET}"
