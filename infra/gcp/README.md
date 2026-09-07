# GCP WR Training Farm (scaffold)

Scaffolding for spot / preemptible QWOP WR training workers that report
heartbeat metrics to GCS. **No secrets belong in this repo** — use gcloud
auth, Workload Identity, or Secret Manager outside git.

## Prerequisites

1. A GCP project (example below uses `qwop-wr` — replace with yours).
2. `gcloud` CLI authenticated (`gcloud auth login` / application-default).
3. Billing enabled.

## One-time setup

```bash
export PROJECT_ID=qwop-wr          # change me
export REGION=us-central1
export ZONE=us-central1-a
gcloud config set project "$PROJECT_ID"

# APIs
gcloud services enable \
  compute.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com

# Bucket for code tarballs + metrics heartbeats
gcloud storage buckets create "gs://${PROJECT_ID}-training" \
  --location="$REGION" \
  --uniform-bucket-level-access || true
# Canonical name used by scripts (create or alias):
gcloud storage buckets create gs://qwop-wr-training \
  --location="$REGION" \
  --uniform-bucket-level-access || true

# Service account for workers
gcloud iam service-accounts create qwop-wr-trainer \
  --display-name="QWOP WR trainer" || true

SA="qwop-wr-trainer@${PROJECT_ID}.iam.gserviceaccount.com"

# Minimal roles: read/write training artifacts + write metrics + logging
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/monitoring.metricWriter"

# Allow the SA to use itself on GCE (needed for custom SA on VMs)
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="serviceAccount:${SA}" \
  --role="roles/iam.serviceAccountUser"
```

## Upload code (optional tarball path)

Workers can clone from git **or** fetch a tarball from GCS:

```bash
# From repo root (exclude .git / large artifacts)
tar -czf /tmp/qwop-python.tgz \
  --exclude=.git --exclude=data --exclude='*.egg-info' .
gcloud storage cp /tmp/qwop-python.tgz gs://qwop-wr-training/code/qwop-python.tgz
```

Or set instance metadata `git_url` / `git_ref` and let `startup.sh` clone.

## Launch spot workers

```bash
cd infra/gcp
chmod +x create_workers.sh startup.sh
./create_workers.sh --count 2 --config config/sweeps/scout_ppo_fps2.yml
```

See `create_workers.sh` for flags. Default machine: **spot** `n2d-standard-8`,
label `qwop-wr=1`, service account
`qwop-wr-trainer@qwop-wr.iam.gserviceaccount.com` (override with env vars).

## Heartbeats

Every ~60s each worker writes:

```text
gs://qwop-wr-training/metrics/runs/<run_id>/heartbeat.json
```

Schema: [`metrics_schema.md`](./metrics_schema.md).

Point the local dashboard at the prefix:

```bash
python scripts/wr_dashboard.py --port 8787 \
  --gcs-prefix gs://qwop-wr-training/metrics/
```

Requires `gsutil` or `pip install google-cloud-storage` and credentials that
can list/read the bucket.

## Preemption

Spot VMs can stop at any time. `startup.sh` sets status `running` while
training; on clean exit it writes `finished`. Preempted instances simply
stop updating — the dashboard marks them dead after ~3 minutes without a
fresh `updated_at`.

## Cost notes

- Prefer spot / preemptible for scouts.
- Cap disk size; store checkpoints in GCS, not large local disks.
- Tear down idle workers: `gcloud compute instances list --filter='labels.qwop-wr=1'`

## Security

- Do **not** commit JSON keys or `.env` files.
- Prefer the worker SA + metadata; avoid embedding tokens in startup scripts.
- Bucket IAM should grant the trainer SA objectAdmin only on
  `gs://qwop-wr-training` if you tighten from project-level roles.
