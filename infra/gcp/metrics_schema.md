# GCS heartbeat metrics schema

Workers write a small JSON document so the WR dashboard can show live farm
status without scraping TensorBoard from every VM.

## Object path

```text
gs://qwop-wr-training/metrics/runs/<run_id>/heartbeat.json
```

Optional siblings (future): `summary.json`, `events.jsonl`. The dashboard
MVP only requires `heartbeat.json` (or any `*.json` under the metrics prefix
that parses as an object).

## Cadence

Write / overwrite about every **60 seconds** while training. Include
`updated_at` in UTC ISO-8601. The dashboard treats a run as dead if
`status` is not active **or** `updated_at` is older than ~3 minutes.

## Schema (JSON object)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | string | yes | Unique run id (matches local `--run-id` / out dir) |
| `hostname` | string | yes | VM hostname |
| `zone` | string | no | GCE zone (e.g. `us-central1-a`) |
| `steps` | number | no | Latest training timestep |
| `success_rate` | number | no | Latest `rollout/success_rate` or `user/is_success` |
| `ep_rew` / `ep_rew_mean` | number | no | Latest episode reward mean |
| `best_hud_time` | number | no | Best finish time seen (**HUD seconds**) |
| `last_hud_time` | number | no | Latest `user/time` (**HUD seconds**) |
| `split_100m_time` | number | no | Latest `user/split_100m_time` if logged |
| `fps` | number | no | Env / training FPS if known |
| `status` | string | yes | `starting` \| `running` \| `finished` \| `failed` \| `preempted` |
| `updated_at` | string | yes | UTC timestamp, e.g. `2026-09-07T22:00:00Z` |
| `config` | string | no | Training config path |
| `source` | string | no | Should be `gcp` (dashboard also sets this) |

### Example

```json
{
  "run_id": "scout-ppo-fps2-a1b2",
  "hostname": "qwop-wr-1",
  "zone": "us-central1-a",
  "steps": 120000,
  "success_rate": 0.02,
  "ep_rew_mean": 1.4,
  "best_hud_time": 62.1,
  "last_hud_time": 71.3,
  "split_100m_time": null,
  "fps": 380.0,
  "status": "running",
  "updated_at": "2026-09-07T22:15:01Z",
  "config": "config/sweeps/scout_ppo_fps2.yml",
  "source": "gcp"
}
```

## Time semantics

**All times are HUD seconds** (QWOP on-screen score clock / `score_time`),
not W&B protocol time and not qwop-gym's compressed protocol clock
(≈ HUD / 10). Human WR **45.530s** is HUD time.

## TensorBoard tag mapping (local + workers)

When scraping SB3 event files locally, the dashboard / `monitor_runs.py` look for:

| Metric | Tags (first match / latest step) |
|--------|-----------------------------------|
| success | `rollout/success_rate`, `user/is_success`, `eval/success_rate` |
| ep reward | `rollout/ep_rew_mean`, `train/ep_rew_mean` |
| HUD time | `user/time` |
| 100m split | `user/split_100m_time` |
| fps | `time/fps`, `rollout/fps` |

Workers should mirror the same numbers into the heartbeat when possible
(see `startup.sh` helper that tails TB or reads a side-car metrics file).
