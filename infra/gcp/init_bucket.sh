#!/usr/bin/env bash
# Create control-plane prefixes + seed empty state JSON in gs://qwop-wr-training.
# Does NOT create VMs. Safe for humans / Bot; Cursor agents use fixtures locally.
#
# Usage:
#   ./infra/gcp/init_bucket.sh
#   BUCKET=gs://qwop-wr-training ./infra/gcp/init_bucket.sh

set -euo pipefail

BUCKET="${BUCKET:-gs://qwop-wr-training}"
BUCKET="${BUCKET%/}"

echo "Initializing control plane at ${BUCKET}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Need $1 on PATH (gcloud storage or gsutil)" >&2
    exit 1
  }
}

if command -v gcloud >/dev/null 2>&1; then
  UPLOAD=(gcloud storage cp)
  MKBUCKET=(gcloud storage buckets create)
else
  need_cmd gsutil
  UPLOAD=(gsutil cp)
  MKBUCKET=(gsutil mb -l us-central1)
fi

# Bucket may already exist
"${MKBUCKET[@]}" "$BUCKET" 2>/dev/null || true

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Placeholders so prefixes exist
for p in \
  queue/pending queue/running queue/done queue/failed \
  metrics/runs artifacts/runs state code
do
  echo "placeholder $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${TMP}/.keep"
  "${UPLOAD[@]}" "${TMP}/.keep" "${BUCKET}/${p}/.keep" || true
done

# Seed state if missing (Bot owns ongoing updates)
cat > "${TMP}/fleet.json" <<'EOF'
{
  "updated_at": "1970-01-01T00:00:00Z",
  "updated_by": "init_bucket",
  "desired": 0,
  "size": 0,
  "provisioning_model": "SPOT",
  "machine_type": "n2d-standard-8",
  "instances": []
}
EOF

cat > "${TMP}/leaderboard.json" <<'EOF'
{
  "updated_at": "1970-01-01T00:00:00Z",
  "updated_by": "init_bucket",
  "unit": "HUD seconds",
  "targets": {
    "human_wr_hud": 45.53,
    "ai_best_hud": 47.34,
    "expert_baseline_hud": 55.6
  },
  "entries": []
}
EOF

cat > "${TMP}/backlog.json" <<'EOF'
{
  "updated_at": "1970-01-01T00:00:00Z",
  "updated_by": "init_bucket",
  "ideas": [],
  "blocked": []
}
EOF

for name in fleet leaderboard backlog; do
  # Do not clobber existing Bot-owned state
  if command -v gcloud >/dev/null 2>&1; then
    if gcloud storage ls "${BUCKET}/state/${name}.json" >/dev/null 2>&1; then
      echo "keep existing state/${name}.json"
      continue
    fi
  else
    if gsutil -q stat "${BUCKET}/state/${name}.json"; then
      echo "keep existing state/${name}.json"
      continue
    fi
  fi
  "${UPLOAD[@]}" "${TMP}/${name}.json" "${BUCKET}/state/${name}.json"
  echo "wrote state/${name}.json"
done

echo "Done. Dashboard:"
echo "  python scripts/wr_dashboard.py --port 8787 --gcs-bucket ${BUCKET}"
echo "Local fixture smoke (no GCP):"
echo "  python scripts/wr_dashboard.py --port 8787 --fixture-dir infra/gcp/fixtures"
