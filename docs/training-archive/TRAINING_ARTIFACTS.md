# WR auto-research training artifacts

Where the September 2026 QWOP WR training logs / TensorBoard / farm state live for commentary + video viz.

## In this repo (`docs/training-archive/`)
| Path | What |
|------|------|
| `screenshots/` | TensorBoard UI stills ready for video overlays |
| `summaries/leaderboard.json` | Farm leaderboard snapshot (targets, best finishes) |
| `summaries/early1_tb_summary.json` | Parsed early1 TB scalars |
| `summaries/ANALYSIS_GAP_REPORT.md` | Sim↔browser gap writeup |
| `tb-curated/` | Small subset of event files (early1, stride14) — open with TensorBoard |

```bash
tensorboard --logdir docs/training-archive/tb-curated
```

## On this machine (box) — not all committed (too large / gitignored under `data/*`)
| Path | Size (approx) | What |
|------|---------------|------|
| `data/gcp/` | ~160MB, ~90 runs, ~147 event files | Mirrored GCP trainer TensorBoard |
| `data/scout/` | ~54MB | Local scout runs |
| `/workspace/qwop-gap-analysis/` | ~79MB | Gap analysis + TB copies + evals |
| `/workspace/analysis-gap/` | — | REPORT + TB + plots |
| `/workspace/qwop-orchestration/state/` | — | fleet, leaderboard, backlog JSON |

## On GCS (`gs://qwop-wr-training/`) — full farm archive
| Prefix | What |
|--------|------|
| `tb/` | Live/browser TB streams (incl. `tb/browser-real/`) |
| `artifacts/runs/` | Per-run artifacts + event files |
| `metrics/` | Aggregated metrics |
| `models/` | Checkpoints |
| `spectate/` | Spectate hunt outputs |
| `state/` | Orchestrator state |

Auth: `gcloud config set account qwop-wr-trainer@qwop-wr.iam.gserviceaccount.com`

## Why not everything on `main`?
Raw TB under `data/*` is gitignored and ~200MB+. This branch commits **code + configs + curated viz**. Full events stay on GCS + the box mirror.

## Related uncommitted research code (same PR)
Gait/stride wrappers, settle_spawn, experiment YAMLs, stride_*.py scripts — the auto-research loop itself.
