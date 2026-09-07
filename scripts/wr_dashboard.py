#!/usr/bin/env python3
"""Live QWOP World Record progress dashboard.

Serves:
  GET /           — dark single-page UI (auto-refresh ~8s)
  GET /api/status — JSON snapshot of local TB runs + optional GCS heartbeats

Times shown are **HUD seconds** (game score clock, 1/30 s per update),
not W&B / qwop-gym protocol time (~HUD/10).

Examples:
  python scripts/wr_dashboard.py --port 8787
  python scripts/wr_dashboard.py --port 8787 --gcs-prefix gs://qwop-wr-training/metrics/
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

# ---------------------------------------------------------------------------
# WR targets (HUD seconds)
# ---------------------------------------------------------------------------
HUMAN_WR_HUD = 45.530  # kurodo1916
AI_BEST_HUD = 47.34  # Liao (published AI)
EXPERT_BASELINE_HUD = 55.6  # expert baseline ~HUD

REFRESH_MS = 8000


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _progress_pct(best: float | None, target: float) -> float | None:
    """How close best finish is to target. 100% = at/under target.

    Uses expert baseline as the 'far' end so early runs aren't 0 forever.
    """
    if best is None or best != best or best <= 0:
        return None
    if best <= target:
        return 100.0
    # Map [target, expert*1.5] → [100, 0] roughly; clamp
    far = max(EXPERT_BASELINE_HUD * 1.5, target + 30.0)
    if best >= far:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (far - best) / (far - target)))


# ---------------------------------------------------------------------------
# GCS heartbeats (optional)
# ---------------------------------------------------------------------------
def _parse_gs_uri(uri: str) -> tuple[str, str]:
    """gs://bucket/prefix/ → (bucket, prefix)."""
    if not uri.startswith("gs://"):
        raise ValueError("GCS prefix must start with gs://")
    rest = uri[5:]
    bucket, _, prefix = rest.partition("/")
    if not bucket:
        raise ValueError("missing bucket in %s" % uri)
    return bucket, prefix.lstrip("/")


def read_gcs_heartbeats(gcs_prefix: str | None) -> list[dict]:
    """Read heartbeat *.json under gs://.../metrics/ (runs/*/heartbeat.json).

    Tries google.cloud.storage, then gsutil. Returns [] if unavailable.
    """
    if not gcs_prefix:
        return []

    try:
        bucket_name, prefix = _parse_gs_uri(gcs_prefix.rstrip("/") + "/")
    except ValueError as e:
        return [{"run_id": "_gcs_error", "error": str(e), "source": "gcp"}]

    heartbeats: list[dict] = []

    # Prefer google-cloud-storage if installed
    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        for blob in client.list_blobs(bucket_name, prefix=prefix):
            name = blob.name
            if not name.endswith(".json"):
                continue
            if "heartbeat" not in Path(name).name and not name.endswith(".json"):
                continue
            try:
                raw = blob.download_as_text()
                data = json.loads(raw)
                if isinstance(data, dict):
                    data.setdefault("source", "gcp")
                    data.setdefault("gcs_path", "gs://%s/%s" % (bucket_name, name))
                    heartbeats.append(data)
            except Exception as ex:
                heartbeats.append(
                    {
                        "run_id": Path(name).stem,
                        "source": "gcp",
                        "error": "parse failed: %s" % ex,
                        "gcs_path": "gs://%s/%s" % (bucket_name, name),
                    }
                )
        return heartbeats
    except ImportError:
        pass
    except Exception as ex:
        return [{"run_id": "_gcs_error", "error": "gcs client: %s" % ex, "source": "gcp"}]

    # Fallback: gsutil
    import subprocess

    list_uri = "gs://%s/%s" % (bucket_name, prefix)
    try:
        proc = subprocess.run(
            ["gsutil", "ls", "-r", list_uri],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return [
            {
                "run_id": "_gcs_error",
                "error": "Install google-cloud-storage or gsutil to read GCS heartbeats",
                "source": "gcp",
            }
        ]
    except Exception as ex:
        return [{"run_id": "_gcs_error", "error": str(ex), "source": "gcp"}]

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "gsutil ls failed").strip()
        # Empty prefix / no objects is fine
        if "One or more URLs matched no objects" in err or "matched no objects" in err:
            return []
        return [{"run_id": "_gcs_error", "error": err, "source": "gcp"}]

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".json"):
            continue
        if "heartbeat" not in Path(line).name and "/metrics/" not in line:
            continue
        try:
            cat = subprocess.run(
                ["gsutil", "cat", line],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if cat.returncode != 0:
                continue
            data = json.loads(cat.stdout)
            if isinstance(data, dict):
                data.setdefault("source", "gcp")
                data.setdefault("gcs_path", line)
                heartbeats.append(data)
        except Exception:
            continue

    return heartbeats


def _normalize_gcp_row(hb: dict) -> dict:
    """Map heartbeat JSON → dashboard row schema."""
    status = (hb.get("status") or "").lower()
    updated = hb.get("updated_at")
    alive = status in ("running", "alive", "training")
    # Stale if updated_at older than 3 minutes
    if updated and alive:
        try:
            # Accept Z or offset
            ts = updated.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds()
            if age > 180:
                alive = False
        except ValueError:
            pass

    return {
        "run_id": hb.get("run_id") or hb.get("hostname") or "unknown",
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


def build_status(gcs_prefix: str | None = None, data_root: Path | None = None) -> dict:
    local_rows = monitor_runs.collect_all_local_rows(data_root)
    gcp_raw = read_gcs_heartbeats(gcs_prefix)
    gcp_rows = [_normalize_gcp_row(h) for h in gcp_raw]

    runs = local_rows + gcp_rows

    def _finite_min(vals):
        good = [v for v in vals if isinstance(v, (int, float)) and v == v and v > 0]
        return min(good) if good else None

    best_finish = _finite_min(
        [r.get("best_hud_time") for r in runs]
        + [r.get("last_hud_time") for r in runs]
        + [r.get("best_split_100m_time") for r in runs]
        + [r.get("split_100m_time") for r in runs]
    )
    best_split = _finite_min(
        [r.get("best_split_100m_time") for r in runs]
        + [r.get("split_100m_time") for r in runs]
    )

    alive_count = sum(1 for r in runs if r.get("alive"))

    return {
        "updated_at": _utc_now_iso(),
        "note": (
            "All finish / split times are HUD seconds (game score clock), "
            "not W&B protocol time. Human WR 45.530s is HUD time (kurodo1916)."
        ),
        "targets": {
            "human_wr_hud": HUMAN_WR_HUD,
            "human_wr_holder": "kurodo1916",
            "ai_best_hud": AI_BEST_HUD,
            "ai_best_holder": "Liao",
            "expert_baseline_hud": EXPERT_BASELINE_HUD,
        },
        "summary": {
            "runs_total": len(runs),
            "runs_alive": alive_count,
            "best_finish_hud": best_finish,
            "best_split_100m_hud": best_split,
            "gap_to_human_wr": (
                None if best_finish is None else best_finish - HUMAN_WR_HUD
            ),
            "gap_to_ai_best": (
                None if best_finish is None else best_finish - AI_BEST_HUD
            ),
            "progress_to_human_wr_pct": _progress_pct(best_finish, HUMAN_WR_HUD),
            "progress_to_ai_best_pct": _progress_pct(best_finish, AI_BEST_HUD),
        },
        "runs": runs,
        "gcs_prefix": gcs_prefix,
    }


# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------
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
    margin: 0;
    min-height: 100vh;
    font-family: var(--sans);
    color: var(--text);
    background:
      radial-gradient(1200px 600px at 10% -10%, #1a2838 0%, transparent 55%),
      radial-gradient(900px 500px at 90% 0%, #1a3028 0%, transparent 50%),
      linear-gradient(180deg, var(--bg0), #0a0d12 80%);
  }
  header {
    padding: 1.5rem 1.75rem 0.75rem;
    border-bottom: 1px solid var(--line);
  }
  header h1 {
    margin: 0;
    font-size: 1.45rem;
    font-weight: 650;
    letter-spacing: 0.02em;
  }
  header .sub {
    margin-top: 0.35rem;
    color: var(--muted);
    font-size: 0.9rem;
  }
  .note {
    margin: 0.75rem 1.75rem;
    padding: 0.65rem 0.9rem;
    background: rgba(94, 179, 232, 0.08);
    border: 1px solid rgba(94, 179, 232, 0.25);
    border-radius: 6px;
    color: var(--human);
    font-size: 0.85rem;
  }
  .targets {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    padding: 0.5rem 1.75rem 1rem;
  }
  .card {
    background: var(--bg1);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.9rem 1rem;
  }
  .card .label {
    color: var(--muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .card .value {
    margin-top: 0.25rem;
    font-family: var(--mono);
    font-size: 1.35rem;
    font-weight: 600;
  }
  .card .hint { color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }
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
    padding: 0.5rem 1.75rem;
    font-size: 0.85rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .table-wrap {
    padding: 0 1.75rem 2rem;
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    font-family: var(--mono);
  }
  th, td {
    text-align: left;
    padding: 0.55rem 0.6rem;
    border-bottom: 1px solid var(--line);
    white-space: nowrap;
  }
  th { color: var(--muted); font-weight: 500; font-family: var(--sans); }
  tr:hover td { background: rgba(255,255,255,0.02); }
  .pill {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.75rem;
    border: 1px solid var(--line);
  }
  .pill.yes { color: var(--accent); border-color: rgba(61,190,140,0.4); background: rgba(61,190,140,0.1); }
  .pill.no { color: var(--muted); }
  .pill.gcp { color: var(--ai); border-color: rgba(224,163,92,0.4); }
  .pill.local { color: var(--human); border-color: rgba(94,179,232,0.4); }
  footer {
    padding: 0.75rem 1.75rem 1.5rem;
    color: var(--muted);
    font-size: 0.78rem;
  }
  .err { color: var(--danger); }
</style>
</head>
<body>
  <header>
    <h1>QWOP WR Chase</h1>
    <div class="sub">Live training progress — local TensorBoard + optional GCS farm heartbeats</div>
  </header>
  <div class="note" id="note">Times are HUD seconds (not W&amp;B protocol time).</div>

  <div class="targets">
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
      <div class="label">Runs</div>
      <div class="value" id="run-counts">0</div>
      <div class="hint" id="updated">updated —</div>
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

  <div class="section-title">Runs / instances</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>run_id</th>
          <th>alive</th>
          <th>source</th>
          <th>steps</th>
          <th>success</th>
          <th>ep_rew</th>
          <th>best HUD</th>
          <th>last HUD</th>
          <th>split 100m</th>
          <th>fps</th>
        </tr>
      </thead>
      <tbody id="rows">
        <tr><td colspan="10" style="color:var(--muted)">Loading…</td></tr>
      </tbody>
    </table>
  </div>
  <footer>
    Auto-refresh every """ + str(REFRESH_MS // 1000) + """s ·
    <code>GET /api/status</code> ·
    HUD clock = score_time (1/30s per update), not protocol time
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
    document.getElementById("run-counts").textContent =
      (s.runs_alive || 0) + " alive / " + (s.runs_total || 0);
    document.getElementById("updated").textContent = "updated " + (data.updated_at || "—");

    const pa = s.progress_to_ai_best_pct;
    const pw = s.progress_to_human_wr_pct;
    document.getElementById("pct-ai").textContent = fmtPct(pa);
    document.getElementById("pct-wr").textContent = fmtPct(pw);
    document.getElementById("bar-ai").style.width = (pa || 0) + "%";
    document.getElementById("bar-wr").style.width = (pw || 0) + "%";

    const tbody = document.getElementById("rows");
    const runs = data.runs || [];
    if (!runs.length) {
      tbody.innerHTML = '<tr><td colspan="10" style="color:var(--muted)">No runs found. Train locally or pass --gcs-prefix for farm heartbeats.</td></tr>';
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
      const rew = r.ep_rew_mean != null ? r.ep_rew_mean : r.ep_rew;
      return '<tr>' +
        '<td>' + (r.run_id || "?") + err + '</td>' +
        '<td>' + alive + '</td>' +
        '<td>' + srcPill + '</td>' +
        '<td>' + fmt(r.steps, 0) + '</td>' +
        '<td>' + fmt(r.success_rate, 3) + '</td>' +
        '<td>' + fmt(rew, 2) + '</td>' +
        '<td>' + fmt(best, 2) + '</td>' +
        '<td>' + fmt(last, 2) + '</td>' +
        '<td>' + fmt(split, 2) + '</td>' +
        '<td>' + fmt(r.fps, 1) + '</td>' +
        '</tr>';
    }).join("");
  } catch (e) {
    document.getElementById("rows").innerHTML =
      '<tr><td colspan="10" class="err">Failed to load /api/status: ' + e + '</td></tr>';
  }
}
refresh();
setInterval(refresh, """ + str(REFRESH_MS) + """);
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    gcs_prefix: str | None = None
    data_root: Path | None = None

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
            body = DASHBOARD_HTML.encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return

        if path == "/api/status":
            status = build_status(
                gcs_prefix=self.gcs_prefix,
                data_root=self.data_root,
            )
            body = json.dumps(status, indent=2, default=str).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        self._send(404, b'{"error":"not found"}\n', "application/json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Live QWOP WR progress dashboard (local TB + optional GCS)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="Bind port (default 8787)")
    parser.add_argument(
        "--gcs-prefix",
        default=None,
        help="Optional gs://bucket/prefix for heartbeat JSON "
        "(e.g. gs://qwop-wr-training/metrics/)",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="Override data/ root for local TensorBoard scan",
    )
    parser.add_argument(
        "--dump-status",
        action="store_true",
        help="Print /api/status JSON to stdout and exit (no server)",
    )
    args = parser.parse_args(argv)

    data_root = Path(args.data_root) if args.data_root else None
    if data_root and not data_root.is_absolute():
        data_root = ROOT / data_root

    if args.dump_status:
        status = build_status(gcs_prefix=args.gcs_prefix, data_root=data_root)
        json.dump(status, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    DashboardHandler.gcs_prefix = args.gcs_prefix
    DashboardHandler.data_root = data_root

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(
        "QWOP WR dashboard on http://%s:%d/  (API: /api/status)"
        % (args.host, args.port),
        flush=True,
    )
    if args.gcs_prefix:
        print("GCS prefix: %s" % args.gcs_prefix, flush=True)
    print("Times are HUD seconds (not W&B protocol time).", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
