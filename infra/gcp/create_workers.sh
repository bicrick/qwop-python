#!/usr/bin/env bash
# Example: create spot n2d-standard-8 workers for QWOP WR training.
#
# Usage:
#   ./create_workers.sh --count 2 --config config/sweeps/scout_ppo_fps2.yml
#
# Env overrides:
#   PROJECT_ID, ZONE, MACHINE_TYPE, SA_EMAIL, IMAGE_FAMILY, IMAGE_PROJECT,
#   METRICS_BUCKET, GIT_URL, GIT_REF, CODE_TARBALL, MAX_TIMESTEPS

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
COUNT=1
TRAIN_CONFIG="config/train_ppo.yml"
NAME_PREFIX="qwop-wr"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --count) COUNT="$2"; shift 2 ;;
    --config) TRAIN_CONFIG="$2"; shift 2 ;;
    --zone) ZONE="$2"; shift 2 ;;
    --project) PROJECT_ID="$2"; shift 2 ;;
    --git-url) GIT_URL="$2"; shift 2 ;;
    --git-ref) GIT_REF="$2"; shift 2 ;;
    --max-timesteps) MAX_TIMESTEPS="$2"; shift 2 ;;
    --prefix) NAME_PREFIX="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

STARTUP="${SCRIPT_DIR}/startup.sh"
if [[ ! -f "$STARTUP" ]]; then
  echo "Missing startup.sh at $STARTUP" >&2
  exit 1
fi

echo "Project:     $PROJECT_ID"
echo "Zone:        $ZONE"
echo "Machine:     $MACHINE_TYPE (SPOT)"
echo "SA:          $SA_EMAIL"
echo "Config:      $TRAIN_CONFIG"
echo "Count:       $COUNT"
echo "Labels:      qwop-wr=1"

for i in $(seq 1 "$COUNT"); do
  TS="$(date -u +%Y%m%d%H%M%S)"
  NAME="${NAME_PREFIX}-${TS}-${i}"
  RUN_ID="${NAME}"

  METADATA=(
    "run-id=${RUN_ID}"
    "train-config=${TRAIN_CONFIG}"
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
  echo "Creating $NAME (run_id=$RUN_ID)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf ' %q' "${CMD[@]}"
    echo
  else
    "${CMD[@]}"
  fi
done

echo "Done. Heartbeats → ${METRICS_BUCKET}/metrics/runs/<run_id>/heartbeat.json"
echo "Dashboard: python scripts/wr_dashboard.py --port 8787 --gcs-prefix ${METRICS_BUCKET}/metrics/"
