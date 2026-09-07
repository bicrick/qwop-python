# GCS heartbeat metrics schema

Workers (spot VMs) overwrite a small JSON document so the read-only dashboard
and Grok Bot can see live farm status without scraping every VM's TensorBoard.

## Object path

```text
gs://qwop-wr-training/metrics/runs/<job_id>/heartbeat.json
```

`<job_id>` matches the queue object stem:
`queue/{pending,running,done,failed}/<job_id>.json`.

## Cadence

Overwrite about every **60 seconds** while training. Include UTC ISO-8601
`updated_at`. Dashboard treats a run as dead if `status` is inactive **or**
`updated_at` is older than ~3 minutes.

## Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | string | yes | Same id as queue job |
| `run_id` | string | no | Alias; dashboard accepts either |
| `hostname` | string | yes | VM hostname |
| `zone` | string | no | GCE zone |
| `steps` | number | no | Latest training timestep |
| `success_rate` | number | no | `rollout/success_rate` / `user/is_success` |
| `ep_rew` / `ep_rew_mean` | number | no | Episode reward mean |
| `best_hud_time` | number | no | Best finish (**HUD seconds**) |
| `last_hud_time` | number | no | Latest `user/time` (**HUD seconds**) |
| `split_100m_time` | number | no | Latest `user/split_100m_time` |
| `fps` | number | no | Env / training FPS |
| `status` | string | yes | `starting` \| `running` \| `finished` \| `failed` \| `preempted` |
| `updated_at` | string | yes | UTC, e.g. `2026-09-07T22:00:00Z` |
| `config` | string | no | Train config path |
| `source` | string | no | `gcp` |

### Example

```json
{
  "job_id": "job-scout-001",
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

**HUD seconds** only (score clock / `score_time`). Not W&B protocol time.
Human WR **45.530s** is HUD.

## TensorBoard tag mapping (local dashboard)

| Metric | Tags |
|--------|------|
| success | `rollout/success_rate`, `user/is_success`, `eval/success_rate` |
| ep reward | `rollout/ep_rew_mean`, `train/ep_rew_mean` |
| HUD time | `user/time` |
| 100m split | `user/split_100m_time` |
| fps | `time/fps`, `rollout/fps` |

## Related control-plane objects

See [`CONTROL_PLANE.md`](./CONTROL_PLANE.md) for queue / state / artifacts.
Artifacts land at `gs://qwop-wr-training/artifacts/runs/<job_id>/`.
