# WR Live Dashboard (read-only)

Track QWOP world-record chase progress from local TensorBoard logs and the
GCS control plane at `gs://qwop-wr-training`.

**Roles:** Grok Bot orchestrates; Cursor agents ship code; spot VMs train;
this dashboard only **reads**.

See [`infra/gcp/CONTROL_PLANE.md`](../infra/gcp/CONTROL_PLANE.md).

## Quick start

```bash
pip install -e ".[sb3]"   # tensorboard (+ optional google-cloud-storage)

# Local fixtures (no GCP) — recommended smoke test
python scripts/wr_dashboard.py --port 8787 --fixture-dir infra/gcp/fixtures

# Live control plane
python scripts/wr_dashboard.py --port 8787 --gcs-bucket gs://qwop-wr-training

# Local TensorBoard only
python scripts/wr_dashboard.py --port 8787 --local-only
```

Open http://127.0.0.1:8787/ (auto-refresh ~8s). JSON:

```bash
python scripts/wr_dashboard.py --dump-status --fixture-dir infra/gcp/fixtures
curl -s http://127.0.0.1:8787/api/status | head
```

## What it shows

| Block | Source |
|-------|--------|
| Targets | Human WR **45.530s HUD**, AI **47.34s**, expert ~**55.6s** |
| Leaderboard | `state/leaderboard.json` (+ refs); gap vs 45.530 |
| Queue depth | counts under `queue/{pending,running,done,failed}/` |
| Fleet size | `state/fleet.json` (`size` / `instances`) |
| Live runs | local TB via `monitor_runs.py` + `metrics/runs/*/heartbeat.json` |

All times are **HUD seconds**, not W&B protocol time.

## Local TensorBoard scan

`scripts/monitor_runs.py` / dashboard scan:

- `data/scout/*`
- `data/sweeps/*`
- any `events.out.tfevents.*` under `data/`

```bash
python scripts/monitor_runs.py --all
python scripts/tests/test_tb_tags.py
```

## GCS layout (dashboard reads)

```text
gs://qwop-wr-training/
  queue/{pending,running,done,failed}/<job_id>.json
  metrics/runs/<job_id>/heartbeat.json
  state/{fleet,leaderboard,backlog}.json
```

Fixtures mirror this under `infra/gcp/fixtures/`.

## API (`GET /api/status`)

Includes `targets`, `leaderboard`, `queue`, `fleet`, `summary`, `runs`,
and `read_only: true`.
