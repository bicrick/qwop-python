# QWOP WR Cloud Orchestration

## Roles

| Layer | Who | Job |
|-------|-----|-----|
| Brain | Grok Bot (`QWOP World Record`) + 15m routine | Design experiments, enqueue jobs, scale fleet, kill collapses, promote winners, launch Cloud Agents for *code* changes |
| Muscle | GCP spot/preemptible VMs (`n2d`/`c2`) | High-throughput Box2D training only |
| Code factory | Cursor Cloud Agents | Harness/dashboard/env fixes as PRs — **not** training rollouts |
| Memory | GCS `gs://qwop-wr-training` | Source of truth for queue, fleet, metrics, artifacts |
| Eyes | Live dashboard | Read-only view of queue + fleet + leaderboard (HUD times) |

Local box stays a small scout / dashboard host. Never treat Cloud Agents as a training farm.

## GCS layout (`gs://qwop-wr-training`)

```
code/                     # pinned training tarball + startup.sh
queue/
  pending/<job_id>.json   # experiment specs waiting
  running/<job_id>.json
  done/<job_id>.json
  failed/<job_id>.json
metrics/runs/<job_id>/
  heartbeat.json          # steps, success_rate, best_hud_time, zone, status
  done.json
artifacts/runs/<job_id>/  # checkpoints, TB, final models
state/
  fleet.json              # desired/actual instance count, budget caps
  leaderboard.json        # best HUD finishes (local+gcp)
  backlog.json            # ranked experiment ideas
```

### Job JSON (pending)

```json
{
  "job_id": "scout-phaseA-20260907-a1",
  "config": "config/scout_qrdqn_phase_a.yml",
  "action": "train_qrdqn",
  "max_timesteps": 400000,
  "machine_type": "n2d-standard-8",
  "preemptible": true,
  "priority": 10,
  "hypothesis": "Phase A competence from scratch",
  "created_at": "ISO8601"
}
```

## Control loop (every 15m, intentional overnight)

1. **Ingest** — pull heartbeats + local TB → update `leaderboard.json`
2. **Health** — mark dead workers / collapses (success crash, reward hack); move jobs to failed; delete idle VMs
3. **Decide** — pick next backlog experiments that fit remaining CPU budget
4. **Enqueue** — write pending job JSON
5. **Reconcile fleet** — create/delete spot VMs so `running + pending` ≈ desired capacity (never exceed budget caps)
6. **Code** — if harness bug/blocker, launch/reply Cloud Agent (not a new training VM)
7. **Notify** — user only on new best HUD, budget hit, or hard blocker; else quiet

## Budget guardrails (defaults — tune in fleet.json)

- Max concurrent vCPUs: **24** (3× n2d-standard-8) until raised
- Spot/preemptible **only**
- Auto-delete VM when job finishes or heartbeat stale >20m
- No GPU until we prove CPU farm is saturated usefully
- Daily soft cap tracked in `state/fleet.json` (`max_daily_usd_estimate`)

## Clock / WR claims

- Dashboard + leaderboard store **HUD seconds** only
- Never compare W&B protocol time (`≈ HUD/10`) to 45.530 / 47.34
- Targets: human 45.530 · Liao AI 47.34 · expert baseline ~55.6

## Dashboard

`scripts/wr_dashboard.py` reads:
- Local `data/**` TensorBoard
- GCS `metrics/` + `state/leaderboard.json` + `queue/` + compute instance list (optional)

Shows: leaderboard vs targets, live runs table, queue depth, fleet size.

## Why this shape

- Grok Bot can die/restart; **GCS queue survives**
- Preemptible VMs can die; jobs return to pending with partial artifact resume later
- Cloud Agents stay cheap/correct for code; training stays on spot CPUs
- Dashboard is read-only so orchestration never depends on a browser session
