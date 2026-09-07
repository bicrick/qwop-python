# WR Live Dashboard

Track QWOP world-record chase progress from local TensorBoard logs and
optional GCP farm heartbeats.

## Quick start

```bash
pip install -e ".[sb3]"   # tensorboard + pyyaml
python scripts/wr_dashboard.py --port 8787
```

Open [http://127.0.0.1:8787/](http://127.0.0.1:8787/). The page auto-refreshes
about every 8 seconds. JSON snapshot:

```bash
curl -s http://127.0.0.1:8787/api/status | head
# or without a server:
python scripts/wr_dashboard.py --dump-status
```

With GCP farm metrics:

```bash
python scripts/wr_dashboard.py --port 8787 \
  --gcs-prefix gs://qwop-wr-training/metrics/
```

(`gsutil` or `pip install google-cloud-storage` + ADC / `gcloud auth`.)

## What it shows

| Block | Content |
|-------|---------|
| Targets | Human WR **45.530s HUD** (kurodo1916), AI **47.34s** (Liao), expert baseline ~**55.6s HUD** |
| Summary | Best finish across runs, gaps to WR / AI, alive run count |
| Progress bars | Rough progress toward 47.34 and 45.530 |
| Runs table | `run_id`, alive?, steps, success_rate, ep_rew_mean, best/last HUD, split_100m, fps, source (`local` \| `gcp`) |

**Important:** all times are **HUD seconds** (on-screen score clock /
`score_time`, +1/30 per update). They are **not** W&B protocol time and not
qwop-gym's compressed protocol clock (≈ HUD ÷ 10).

## Data sources

### Local TensorBoard

Reuses / extends `scripts/monitor_runs.py`:

- `data/scout/*`
- `data/sweeps/*` (manifest + PID files when present)
- any `events.out.tfevents.*` under `data/`

CLI monitor (table in the terminal):

```bash
python scripts/monitor_runs.py --all
python scripts/monitor_runs.py --latest
```

### GCP heartbeats

Workers write `gs://qwop-wr-training/metrics/runs/<run_id>/heartbeat.json`
about every 60s. See [`infra/gcp/`](../infra/gcp/README.md) and
[`infra/gcp/metrics_schema.md`](../infra/gcp/metrics_schema.md).

## TensorBoard tags

SB3 + this repo's `LogCallback` record:

| Metric | Tags |
|--------|------|
| success | `rollout/success_rate`, `user/is_success`, `eval/success_rate` |
| episode reward | `rollout/ep_rew_mean`, `train/ep_rew_mean` |
| HUD time | `user/time` |
| 100m split | `user/split_100m_time` (when Phase A/B split metrics are present) |
| fps | `time/fps`, `rollout/fps` |

Verify parsing against a log dir:

```bash
python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
import monitor_runs
# Point at a real run dir containing events.out.tfevents.*
m = monitor_runs.read_tb_metrics([Path("data")])
print(m)
PY
```

A small self-check (synthetic scalars) lives in
`scripts/tests/test_tb_tags.py`.

## Related work

WR Phase A/B curriculum, HUD-time eval, and the parallel sweep harness may
land via separate PRs. This dashboard only needs TensorBoard event files
(and optional GCS heartbeats) to run.

## API shape (`GET /api/status`)

```json
{
  "updated_at": "2026-09-07T22:00:00Z",
  "note": "All finish / split times are HUD seconds ...",
  "targets": {
    "human_wr_hud": 45.53,
    "ai_best_hud": 47.34,
    "expert_baseline_hud": 55.6
  },
  "summary": {
    "runs_total": 0,
    "runs_alive": 0,
    "best_finish_hud": null,
    "progress_to_human_wr_pct": null,
    "progress_to_ai_best_pct": null
  },
  "runs": []
}
```
