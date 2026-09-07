# GCP WR Training Farm (scaffold)

Control-plane bucket: **`gs://qwop-wr-training`**. Full layout + roles:
[`CONTROL_PLANE.md`](./CONTROL_PLANE.md).

**Architecture lock-in**

| Actor | Role |
|-------|------|
| Grok Bot (~15m) | Orchestrator (enqueue, reconcile spot fleet, kill collapses) |
| Cursor Cloud Agents | Code only |
| Spot VMs | Training only |
| Dashboard | Read-only |

This PR ships **schemas, fixtures, worker startup, and bucket init** — not live
VM creation as part of agent work.

## Prerequisites

1. GCP project (examples use `qwop-wr` — replace).
2. `gcloud` authenticated (`gcloud auth login` / ADC).
3. Billing enabled.

## One-time setup

```bash
export PROJECT_ID=qwop-wr
export REGION=us-central1
export ZONE=us-central1-a
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  compute.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com

gcloud storage buckets create gs://qwop-wr-training \
  --location="$REGION" \
  --uniform-bucket-level-access || true

gcloud iam service-accounts create qwop-wr-trainer \
  --display-name="QWOP WR trainer" || true

SA="qwop-wr-trainer@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/monitoring.metricWriter"

gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="user:YOUR_ACCOUNT" \
  --role="roles/iam.serviceAccountUser"
```

Seed prefixes + empty state (no VMs):

```bash
chmod +x infra/gcp/init_bucket.sh
./infra/gcp/init_bucket.sh
```

## Upload code tarball (optional)

```bash
tar -czf /tmp/qwop-python.tgz \
  --exclude=.git --exclude=data --exclude='*.egg-info' .
gcloud storage cp /tmp/qwop-python.tgz gs://qwop-wr-training/code/qwop-python.tgz
gcloud storage cp infra/gcp/startup.sh gs://qwop-wr-training/code/startup.sh
```

## Spot workers (orchestrator / humans — not Cursor agent duty)

Example helper only:

```bash
cd infra/gcp
./create_workers.sh --dry-run --count 1 --config config/sweeps/scout_ppo_fps2.yml
# QRDQN scouts: *qrdqn* is matched before *dqn*; prefer an explicit action:
./create_workers.sh --dry-run --config config/sweeps/scout_qrdqn.yml \
  --train-action train_qrdqn
# Grok Bot owns live reconcile; pass --job-id matching queue/running/<id>.json
```

`startup.sh` reads metadata `train-action` when set; otherwise infers from the
config basename (`*qrdqn*` before `*dqn*`, `*rppo*` before `*ppo*`).

Default: spot `n2d-standard-8`, label `qwop-wr=1`, SA
`qwop-wr-trainer@qwop-wr.iam.gserviceaccount.com`.

Workers write:

```text
gs://qwop-wr-training/metrics/runs/<job_id>/heartbeat.json
gs://qwop-wr-training/artifacts/runs/<job_id>/
```

## Dashboard (read-only)

```bash
# Local fixtures (no GCP credentials)
python scripts/wr_dashboard.py --port 8787 --fixture-dir infra/gcp/fixtures

# Live bucket
python scripts/wr_dashboard.py --port 8787 --gcs-bucket gs://qwop-wr-training

# Local TensorBoard only
python scripts/wr_dashboard.py --port 8787 --local-only
```

## Docs

- [`CONTROL_PLANE.md`](./CONTROL_PLANE.md) — layout + writers
- [`metrics_schema.md`](./metrics_schema.md) — heartbeat fields
- [`schemas/`](./schemas/) — JSON schemas
- [`fixtures/`](./fixtures/) — sample control-plane mirror for local UI

## Security

No secrets in git. Prefer worker SA + metadata; never embed JSON keys.
