# GCS control plane — architecture lock-in

Canonical bucket: **`gs://qwop-wr-training`**

```text
gs://qwop-wr-training/
  queue/
    pending/<job_id>.json
    running/<job_id>.json
    done/<job_id>.json
    failed/<job_id>.json
  metrics/runs/<job_id>/heartbeat.json
  artifacts/runs/<job_id>/          # checkpoints, evals, logs
  state/
    fleet.json                      # desired/actual spot fleet
    leaderboard.json                # best HUD times
    backlog.json                    # ideas / next experiments
  code/
    qwop-python.tgz                 # optional training tarball
    startup.sh                      # optional copy of worker startup
```

## Roles (do not blur)

| Actor | Responsibility |
|-------|----------------|
| **Grok Bot** (~15m routine) | **Orchestrator** — enqueue jobs, move queue states, reconcile spot fleet size, kill collapsed runs, refresh `state/*.json` |
| **Cursor Cloud Agents** | **Code only** — land training/dashboard/infra *code* in git. Do **not** create VMs, mutate the live queue, or act as the fleet controller in PRs |
| **Spot VMs** | **Training only** — pull job + code, train, write heartbeats + artifacts. No product UI / no orchestration |
| **Dashboard** (`scripts/wr_dashboard.py`) | **Read-only** — local TensorBoard + GCS queue/fleet/leaderboard/heartbeats |

## Who writes what

| Path | Writer | Readers |
|------|--------|---------|
| `queue/pending/` | Grok Bot | Bot, workers (claim), dashboard |
| `queue/running/` | Bot and/or worker claim | Bot, dashboard |
| `queue/done\|failed/` | Bot / worker on exit | Bot, dashboard |
| `metrics/runs/*/heartbeat.json` | Spot VM (~60s) | Dashboard, Bot (collapse detect) |
| `artifacts/runs/*/` | Spot VM | Humans, Bot, eval jobs |
| `state/fleet.json` | Grok Bot | Dashboard, Bot |
| `state/leaderboard.json` | Grok Bot | Dashboard |
| `state/backlog.json` | Grok Bot (from humans) | Bot |
| `code/` | Humans / CI (from git) | Spot VM startup |

## Job object (queue)

See [`schemas/job.schema.json`](./schemas/job.schema.json) and fixtures under
[`fixtures/queue/`](./fixtures/).

Minimum fields: `job_id`, `config`, `created_at`, `enqueued_by`.

## Heartbeat

See [`metrics_schema.md`](./metrics_schema.md). Path:

`metrics/runs/<job_id>/heartbeat.json`

## State objects

- **fleet.json** — `size`, `desired`, `instances[]` (`name`, `zone`, `job_id`, `status`)
- **leaderboard.json** — `entries[]` with `best_hud_time` (**HUD seconds**), vs targets 45.530 / 47.34 / 55.6
- **backlog.json** — free-form experiment ideas for the Bot to enqueue later

Example fixtures (for local dashboard without GCS):

```bash
python scripts/wr_dashboard.py --port 8787 \
  --fixture-dir infra/gcp/fixtures
```

## Init prefixes (no VMs)

```bash
./infra/gcp/init_bucket.sh   # creates empty prefixes + seed state JSON
```

## Worker startup (training only)

`startup.sh` expects metadata `job-id` (same as queue job id) and writes:

- heartbeat → `metrics/runs/<job_id>/heartbeat.json`
- artifacts → `artifacts/runs/<job_id>/`

Optional metadata `train-action` (e.g. `train_qrdqn`) overrides filename
inference. Inference matches `*qrdqn*` before `*dqn*` so
`scout_qrdqn_phase_a.yml` does not become `train_dqn`.
`create_workers.sh --train-action …` always writes the resolved action into
instance metadata.

Claiming / moving queue objects is orchestrator policy (Bot). Workers may
be handed an already-`running` job id via metadata.

## Out of scope for Cursor agent PRs

- Actually creating or deleting GCE instances against a live project
- Writing to the production queue or leaderboard
- Embedding service-account keys

Provide scripts + schema + a working **local** dashboard (fixtures or TB).
