#!/usr/bin/env python3
"""Live QWOP World Record progress dashboard (read-only).

Control plane: ``gs://qwop-wr-training`` (see ``infra/gcp/CONTROL_PLANE.md``).

Serves:
  GET /           — dark single-page UI (auto-refresh ~8s)
  GET /api/status — JSON snapshot

Shows:
  - Leaderboard vs Human WR 45.530 / AI 47.34 / expert ~55.6 HUD
  - Live runs (local TensorBoard + GCS heartbeats)
  - Queue depth (pending/running/done/failed)
  - Fleet size (from state/fleet.json)

Dashboard never mutates GCS. Orchestration is Grok Bot; agents = code;
spot VMs = training.

Examples:
  python scripts/wr_dashboard.py --port 8787
  python scripts/wr_dashboard.py --port 8787 --gcs-bucket gs://qwop-wr-training
  python scripts/wr_dashboard.py --dump-status --fixture-dir infra/gcp/fixtures
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_runs  # noqa: E402
import wr_gcs  # noqa: E402

HUMAN_WR_HUD = 45.530  # kurodo1916
AI_BEST_HUD = 47.34  # Liao
EXPERT_BASELINE_HUD = 55.6

REFRESH_MS = 8000


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _progress_pct(best: float | None, target: float) -> float | None:
    if best is None or best != best or best <= 0:
        return None
    if best <= target:
        return 100.0
    far = max(EXPERT_BASELINE_HUD * 1.5, target + 30.0)
    if best >= far:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (far - best) / (far - target)))


def _finite_min(vals):
    good = [v for v in vals if isinstance(v, (int, float)) and v == v and v > 0]
    return min(good) if good else None


def _normalize_gcp_row(hb: dict) -> dict:
    status = (hb.get("status") or "").lower()
    updated = hb.get("updated_at")
    alive = status in ("running", "alive", "training")
    if updated and alive:
        try:
            ts = updated.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - dt).total_seconds() > 180:
                alive = False
        except ValueError:
            pass

    run_id = hb.get("run_id") or hb.get("job_id") or hb.get("hostname") or "unknown"
    return {
        "run_id": run_id,
        "job_id": hb.get("job_id") or run_id,
        "alive": alive if "error" not in hb else False,
        "pid": None,
        "source": "gcp",
        "hostname": hb.get("hostname"),
        "zone": hb.get("zone"),
        "status": hb.get("status"),
        "success_rate": hb.get("success_rate"),
        "ep_rew": hb.get("ep_rew") if "ep_rew" in hb else hb.get("ep_rew_mean"),
        "ep_rew_mean": hb.get("ep_rew_mean", hb.get("ep_rew")),
        "best_hud_time": hb.get("best_hud_time"),
        "last_hud_time": hb.get("last_hud_time") or hb.get("hud_time"),
        "split_100m_time": hb.get("split_100m_time"),
        "best_split_100m_time": hb.get("best_split_100m_time"),
        "fps": hb.get("fps"),
        "steps": hb.get("steps") if "steps" in hb else hb.get("step"),
        "updated_at": updated,
        "error": hb.get("error"),
        "gcs_path": hb.get("gcs_path"),
    }


def _leaderboard_entries(leaderboard: dict, runs: list[dict]) -> list[dict]:
    """Normalize leaderboard JSON, falling back to best times from live runs."""
    entries = []
    raw = leaderboard.get("entries") or leaderboard.get("rows") or []
    if isinstance(raw, list) and raw:
        for e in raw:
            if not isinstance(e, dict):
                continue
            hud = e.get("best_hud_time") or e.get("hud_time") or e.get("time")
            entries.append(
                {
                    "rank": e.get("rank"),
                    "label": e.get("label") or e.get("name") or e.get("run_id") or e.get("job_id"),
                    "best_hud_time": hud,
                    "source": e.get("source") or "leaderboard",
                    "job_id": e.get("job_id") or e.get("run_id"),
                    "notes": e.get("notes"),
                }
            )
    else:
        # Derive from runs
        scored = []
        for r in runs:
            t = r.get("best_hud_time") or r.get("best_split_100m_time") or r.get("split_100m_time")
            if isinstance(t, (int, float)) and t == t and t > 0:
                scored.append((t, r))
        scored.sort(key=lambda x: x[0])
        for i, (t, r) in enumerate(scored[:20], start=1):
            entries.append(
                {
                    "rank": i,
                    "label": r.get("run_id"),
                    "best_hud_time": t,
                    "source": r.get("source"),
                    "job_id": r.get("job_id") or r.get("run_id"),
                }
            )

    # Inject fixed reference rows for display context (not "our" runs)
    refs = [
        {"rank": None, "label": "Human WR (kurodo1916)", "best_hud_time": HUMAN_WR_HUD, "source": "ref"},
        {"rank": None, "label": "AI best (Liao)", "best_hud_time": AI_BEST_HUD, "source": "ref"},
        {"rank": None, "label": "Expert baseline", "best_hud_time": EXPERT_BASELINE_HUD, "source": "ref"},
    ]
    return {"references": refs, "entries": entries}


def build_status(
    gcs_bucket: str | None = wr_gcs.DEFAULT_BUCKET,
    data_root: Path | None = None,
    fixture_dir: Path | None = None,
    skip_gcs: bool = False,
) -> dict:
    local_rows = monitor_runs.collect_all_local_rows(data_root)

    if skip_gcs and fixture_dir is None:
        cp = {
            "bucket": None,
            "queue": {
                "depth": {s: 0 for s in wr_gcs.QUEUE_STATES},
                "pending": 0,
                "running": 0,
                "done": 0,
                "failed": 0,
                "total_active": 0,
                "jobs": {},
                "errors": [],
            },
            "fleet": {},
            "fleet_size": 0,
            "leaderboard": {},
            "backlog": {},
            "heartbeats": [],
            "roles": {
                "orchestrator": "Grok Bot (~15m routine)",
                "code": "Cursor Cloud Agents: code only",
                "trainers": "Spot VMs: training only",
                "dashboard": "read-only",
            },
        }
    else:
        cp = wr_gcs.read_control_plane(
            bucket=None if fixture_dir else gcs_bucket,
            fixture_dir=fixture_dir,
        )

    gcp_rows = [_normalize_gcp_row(h) for h in cp.get("heartbeats") or []]
    runs = local_rows + gcp_rows

    best_finish = _finite_min(
        [r.get("best_hud_time") for r in runs]
        + [r.get("last_hud_time") for r in runs]
        + [r.get("best_split_100m_time") for r in runs]
        + [r.get("split_100m_time") for r in runs]
    )
    # Also consider leaderboard entries
    lb = cp.get("leaderboard") or {}
    for e in lb.get("entries") or lb.get("rows") or []:
        if isinstance(e, dict):
            t = e.get("best_hud_time") or e.get("hud_time") or e.get("time")
            if isinstance(t, (int, float)) and t == t and t > 0:
                if best_finish is None or t < best_finish:
                    best_finish = t

    board = _leaderboard_entries(lb, runs)
    queue = cp.get("queue") or {}
    depth = queue.get("depth") or {}

    return {
        "updated_at": _utc_now_iso(),
        "read_only": True,
        "note": (
            "All finish / split times are HUD seconds (game score clock), "
            "not W&B protocol time. Human WR 45.530s is HUD time (kurodo1916). "
            "Dashboard is read-only; Grok Bot orchestrates the farm."
        ),
        "targets": {
            "human_wr_hud": HUMAN_WR_HUD,
            "human_wr_holder": "kurodo1916",
            "ai_best_hud": AI_BEST_HUD,
            "ai_best_holder": "Liao",
            "expert_baseline_hud": EXPERT_BASELINE_HUD,
        },
        "control_plane": {
            "bucket": cp.get("bucket"),
            "roles": cp.get("roles"),
        },
        "queue": {
            "pending": depth.get("pending", queue.get("pending", 0)),
            "running": depth.get("running", queue.get("running", 0)),
            "done": depth.get("done", queue.get("done", 0)),
            "failed": depth.get("failed", queue.get("failed", 0)),
            "total_active": queue.get("total_active", 0),
            "errors": queue.get("errors") or [],
        },
        "fleet": {
            "size": cp.get("fleet_size", 0),
            "raw": cp.get("fleet") or {},
        },
        "backlog": cp.get("backlog") or {},
        "leaderboard": board,
        "summary": {
            "runs_total": len(runs),
            "runs_alive": sum(1 for r in runs if r.get("alive")),
            "best_finish_hud": best_finish,
            "gap_to_human_wr": (
                None if best_finish is None else best_finish - HUMAN_WR_HUD
            ),
            "gap_to_ai_best": (
                None if best_finish is None else best_finish - AI_BEST_HUD
            ),
            "progress_to_human_wr_pct": _progress_pct(best_finish, HUMAN_WR_HUD),
            "progress_to_ai_best_pct": _progress_pct(best_finish, AI_BEST_HUD),
            "queue_pending": depth.get("pending", 0),
            "queue_running": depth.get("running", 0),
            "fleet_size": cp.get("fleet_size", 0),
        },
        "runs": runs,
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>QWOP WR Chase</title>
<style>
  :root {
    --bg0: #0c0f14;
    --bg1: #141a22;
    --bg2: #1c2430;
    --line: #2a3544;
    --text: #e8eef6;
    --muted: #8b9bb0;
    --accent: #3dbe8c;
    --warn: #e0a35c;
    --danger: #d96b6b;
    --human: #5eb3e8;
    --ai: #e0a35c;
    --mono: "IBM Plex Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    --sans: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; font-family: var(--sans); color: var(--text);
    background:
      radial-gradient(1200px 600px at 10% -10%, #1a2838 0%, transparent 55%),
      radial-gradient(900px 500px at 90% 0%, #1a3028 0%, transparent 50%),
      linear-gradient(180deg, var(--bg0), #0a0d12 80%);
  }
  header { padding: 1.5rem 1.75rem 0.75rem; border-bottom: 1px solid var(--line); }
  header h1 { margin: 0; font-size: 1.45rem; font-weight: 650; letter-spacing: 0.02em; }
  header .sub { margin-top: 0.35rem; color: var(--muted); font-size: 0.9rem; }
  .note {
    margin: 0.75rem 1.75rem; padding: 0.65rem 0.9rem;
    background: rgba(94, 179, 232, 0.08);
    border: 1px solid rgba(94, 179, 232, 0.25);
    border-radius: 6px; color: var(--human); font-size: 0.85rem;
  }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem; padding: 0.5rem 1.75rem 1rem;
  }
  .card {
    background: var(--bg1); border: 1px solid var(--line);
    border-radius: 8px; padding: 0.9rem 1rem;
  }
  .card .label {
    color: var(--muted); font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .card .value {
    margin-top: 0.25rem; font-family: var(--mono);
    font-size: 1.25rem; font-weight: 600;
  }
  .card .hint { color: var(--muted); font-size: 0.78rem; margin-top: 0.2rem; }
  .progress-wrap { padding: 0 1.75rem 1rem; }
  .progress-row { margin-bottom: 0.65rem; }
  .progress-row .meta {
    display: flex; justify-content: space-between;
    font-size: 0.8rem; color: var(--muted); margin-bottom: 0.25rem;
  }
  .bar {
    height: 10px; background: var(--bg2); border-radius: 999px; overflow: hidden;
    border: 1px solid var(--line);
  }
  .bar > span {
    display: block; height: 100%; border-radius: 999px;
    background: linear-gradient(90deg, var(--accent), #6ed4a8);
    width: 0%; transition: width 0.4s ease;
  }
  .bar.ai > span { background: linear-gradient(90deg, var(--ai), #f0c48a); }
  .section-title {
    padding: 0.5rem 1.75rem; font-size: 0.85rem; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em;
  }
  .cols {
    display: grid; grid-template-columns: 1fr 1.4fr; gap: 1rem;
    padding: 0 1.75rem 1rem;
  }
  @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
  .table-wrap { padding: 0 1.75rem 1.25rem; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; font-family: var(--mono); }
  th, td {
    text-align: left; padding: 0.5rem 0.55rem;
    border-bottom: 1px solid var(--line); white-space: nowrap;
  }
  th { color: var(--muted); font-weight: 500; font-family: var(--sans); }
  tr:hover td { background: rgba(255,255,255,0.02); }
  tr.ref td { color: var(--muted); }
  .pill {
    display: inline-block; padding: 0.1rem 0.45rem; border-radius: 4px;
    font-size: 0.75rem; border: 1px solid var(--line);
  }
  .pill.yes { color: var(--accent); border-color: rgba(61,190,140,0.4); background: rgba(61,190,140,0.1); }
  .pill.no { color: var(--muted); }
  .pill.gcp { color: var(--ai); border-color: rgba(224,163,92,0.4); }
  .pill.local { color: var(--human); border-color: rgba(94,179,232,0.4); }
  .pill.ref { color: var(--muted); }
  footer { padding: 0.75rem 1.75rem 1.5rem; color: var(--muted); font-size: 0.78rem; }
  .err { color: var(--danger); }
</style>
</head>
<body>
  <header>
    <h1>QWOP WR Chase</h1>
    <div class="sub">Read-only control-plane view — local TB + GCS queue / fleet / heartbeats</div>
  </header>
  <div class="note" id="note">Times are HUD seconds (not W&amp;B protocol time). Dashboard is read-only.</div>

  <div class="grid">
    <div class="card">
      <div class="label">Human WR</div>
      <div class="value" style="color:var(--human)">45.530s</div>
      <div class="hint">kurodo1916 · HUD</div>
    </div>
    <div class="card">
      <div class="label">AI best (Liao)</div>
      <div class="value" style="color:var(--ai)">47.34s</div>
      <div class="hint">published AI · HUD</div>
    </div>
    <div class="card">
      <div class="label">Expert baseline</div>
      <div class="value">~55.6s</div>
      <div class="hint">HUD reference</div>
    </div>
    <div class="card">
      <div class="label">Best finish (ours)</div>
      <div class="value" id="best-finish">—</div>
      <div class="hint" id="best-gap">gap to WR —</div>
    </div>
    <div class="card">
      <div class="label">Queue</div>
      <div class="value" id="queue-depth">0 / 0</div>
      <div class="hint" id="queue-detail">pending / running</div>
    </div>
    <div class="card">
      <div class="label">Fleet size</div>
      <div class="value" id="fleet-size">0</div>
      <div class="hint" id="run-counts">0 alive runs</div>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-row">
      <div class="meta"><span>Progress toward AI 47.34s</span><span id="pct-ai">—</span></div>
      <div class="bar ai"><span id="bar-ai"></span></div>
    </div>
    <div class="progress-row">
      <div class="meta"><span>Progress toward Human WR 45.530s</span><span id="pct-wr">—</span></div>
      <div class="bar"><span id="bar-wr"></span></div>
    </div>
  </div>

  <div class="cols">
    <div>
      <div class="section-title">Leaderboard (HUD)</div>
      <div class="table-wrap" style="padding-left:0;padding-right:0">
        <table>
          <thead><tr><th>#</th><th>entry</th><th>HUD s</th><th>vs WR</th></tr></thead>
          <tbody id="leaderboard"><tr><td colspan="4" style="color:var(--muted)">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>
    <div>
      <div class="section-title">Live runs</div>
      <div class="table-wrap" style="padding-left:0;padding-right:0">
        <table>
          <thead>
            <tr>
              <th>run_id</th><th>alive</th><th>src</th><th>steps</th>
              <th>success</th><th>best</th><th>last</th><th>split</th><th>fps</th>
            </tr>
          </thead>
          <tbody id="rows"><tr><td colspan="9" style="color:var(--muted)">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <footer>
    Auto-refresh every """ + str(REFRESH_MS // 1000) + """s ·
    <code>GET /api/status</code> · read-only ·
    orchestrator = Grok Bot · agents = code · spot VMs = train
  </footer>
<script>
function fmt(v, d=2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (typeof v === "number") return v.toFixed(d);
  return String(v);
}
function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return v.toFixed(1) + "%";
}
async function refresh() {
  try {
    const res = await fetch("/api/status", {cache: "no-store"});
    const data = await res.json();
    document.getElementById("note").textContent = data.note || "";
    const s = data.summary || {};
    document.getElementById("best-finish").textContent =
      s.best_finish_hud != null ? fmt(s.best_finish_hud, 3) + "s" : "—";
    const gap = s.gap_to_human_wr;
    document.getElementById("best-gap").textContent =
      gap == null ? "gap to WR —" :
      (gap <= 0 ? "AT OR UNDER WR" : ("+" + fmt(gap, 3) + "s vs WR"));

    const q = data.queue || {};
    document.getElementById("queue-depth").textContent =
      (q.pending || 0) + " / " + (q.running || 0);
    document.getElementById("queue-detail").textContent =
      "pending / running · done " + (q.done || 0) + " · failed " + (q.failed || 0);
    document.getElementById("fleet-size").textContent = String((data.fleet && data.fleet.size) || 0);
    document.getElementById("run-counts").textContent =
      (s.runs_alive || 0) + " alive / " + (s.runs_total || 0) + " runs · " + (data.updated_at || "");

    const pa = s.progress_to_ai_best_pct;
    const pw = s.progress_to_human_wr_pct;
    document.getElementById("pct-ai").textContent = fmtPct(pa);
    document.getElementById("pct-wr").textContent = fmtPct(pw);
    document.getElementById("bar-ai").style.width = (pa || 0) + "%";
    document.getElementById("bar-wr").style.width = (pw || 0) + "%";

    const WR = (data.targets && data.targets.human_wr_hud) || 45.53;
    const lbBody = document.getElementById("leaderboard");
    const lb = data.leaderboard || {};
    const refs = lb.references || [];
    const entries = lb.entries || [];
    const lbRows = refs.concat(entries);
    if (!lbRows.length) {
      lbBody.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">No leaderboard yet</td></tr>';
    } else {
      lbBody.innerHTML = lbRows.map(e => {
        const isRef = e.source === "ref";
        const hud = e.best_hud_time;
        const vs = (hud != null) ? (hud - WR) : null;
        const vsTxt = vs == null ? "—" : (vs <= 0 ? fmt(vs, 3) : ("+" + fmt(vs, 3)));
        return '<tr class="' + (isRef ? "ref" : "") + '">' +
          "<td>" + (e.rank != null ? e.rank : "—") + "</td>" +
          "<td>" + (e.label || "?") + "</td>" +
          "<td>" + fmt(hud, 3) + "</td>" +
          "<td>" + vsTxt + "</td></tr>";
      }).join("");
    }

    const tbody = document.getElementById("rows");
    const runs = data.runs || [];
    if (!runs.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="color:var(--muted)">No live runs. Train locally or connect GCS.</td></tr>';
      return;
    }
    runs.sort((a,b) => (b.alive|0) - (a.alive|0) || String(a.run_id).localeCompare(String(b.run_id)));
    tbody.innerHTML = runs.map(r => {
      const alive = r.alive ? '<span class="pill yes">yes</span>' : '<span class="pill no">no</span>';
      const src = r.source || "local";
      const srcPill = '<span class="pill ' + (src === "gcp" ? "gcp" : "local") + '">' + src + '</span>';
      const err = r.error ? (' <span class="err">' + r.error + '</span>') : '';
      const best = r.best_hud_time != null ? r.best_hud_time : r.best_split_100m_time;
      const last = r.last_hud_time != null ? r.last_hud_time : r.time;
      const split = r.split_100m_time != null ? r.split_100m_time : r.best_split_100m_time;
      return "<tr><td>" + (r.run_id || "?") + err + "</td><td>" + alive + "</td><td>" + srcPill +
        "</td><td>" + fmt(r.steps, 0) + "</td><td>" + fmt(r.success_rate, 3) +
        "</td><td>" + fmt(best, 2) + "</td><td>" + fmt(last, 2) +
        "</td><td>" + fmt(split, 2) + "</td><td>" + fmt(r.fps, 1) + "</td></tr>";
    }).join("");
  } catch (e) {
    document.getElementById("rows").innerHTML =
      '<tr><td colspan="9" class="err">Failed to load /api/status: ' + e + "</td></tr>";
  }
}
refresh();
setInterval(refresh, """ + str(REFRESH_MS) + """);
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    gcs_bucket: str | None = wr_gcs.DEFAULT_BUCKET
    data_root: Path | None = None
    fixture_dir: Path | None = None
    skip_gcs: bool = False

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._send(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/status":
            status = build_status(
                gcs_bucket=self.gcs_bucket,
                data_root=self.data_root,
                fixture_dir=self.fixture_dir,
                skip_gcs=self.skip_gcs,
            )
            body = json.dumps(status, indent=2, default=str).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        self._send(404, b'{"error":"not found"}\n', "application/json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only QWOP WR dashboard (local TB + GCS control plane)."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--gcs-bucket",
        default=wr_gcs.DEFAULT_BUCKET,
        help="Control-plane bucket (default gs://qwop-wr-training)",
    )
    parser.add_argument(
        "--gcs-prefix",
        default=None,
        help=argparse.SUPPRESS,  # back-compat alias → bucket root
    )
    parser.add_argument(
        "--fixture-dir",
        default=None,
        help="Local directory mirroring bucket layout (skips live GCS)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Do not read GCS (local TensorBoard only)",
    )
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--dump-status", action="store_true")
    args = parser.parse_args(argv)

    data_root = Path(args.data_root) if args.data_root else None
    if data_root and not data_root.is_absolute():
        data_root = ROOT / data_root

    fixture_dir = Path(args.fixture_dir) if args.fixture_dir else None
    if fixture_dir and not fixture_dir.is_absolute():
        fixture_dir = ROOT / fixture_dir

    bucket = args.gcs_bucket
    if args.gcs_prefix and args.gcs_prefix.startswith("gs://"):
        # Accept old flag: strip /metrics suffix to bucket root when possible
        b = args.gcs_prefix.rstrip("/")
        if b.endswith("/metrics"):
            b = b[: -len("/metrics")]
        bucket = b

    if args.dump_status:
        status = build_status(
            gcs_bucket=bucket,
            data_root=data_root,
            fixture_dir=fixture_dir,
            skip_gcs=args.local_only,
        )
        json.dump(status, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    DashboardHandler.gcs_bucket = None if args.local_only else bucket
    DashboardHandler.data_root = data_root
    DashboardHandler.fixture_dir = fixture_dir
    DashboardHandler.skip_gcs = args.local_only

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(
        "QWOP WR dashboard on http://%s:%d/  (read-only API: /api/status)"
        % (args.host, args.port),
        flush=True,
    )
    if fixture_dir:
        print("Fixture dir: %s" % fixture_dir, flush=True)
    elif args.local_only:
        print("Local TensorBoard only (GCS disabled)", flush=True)
    else:
        print("GCS bucket: %s" % bucket, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
