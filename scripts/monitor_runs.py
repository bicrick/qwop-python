#!/usr/bin/env python3
"""Monitor parallel QWOP training runs from TensorBoard event files.

Prints a table: run_id, alive?, last success_rate, last ep_rew, last user/time.

Also exports helpers reused by ``scripts/wr_dashboard.py`` for scanning
``data/scout/*``, ``data/sweeps/*``, and any tfevents under ``data/``.

Examples:
  python scripts/monitor_runs.py data/sweeps/20260101-120000
  python scripts/monitor_runs.py --latest
  python scripts/monitor_runs.py --watch 30 --latest
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# SB3 / LogCallback scalar tags (HUD seconds for user/time and split_*_time).
SUCCESS_TAGS = (
    "rollout/success_rate",
    "user/is_success",
    "eval/success_rate",
)
EP_REW_TAGS = (
    "rollout/ep_rew_mean",
    "train/ep_rew_mean",
)
TIME_TAGS = ("user/time",)
SPLIT_100M_TAGS = ("user/split_100m_time",)
FPS_TAGS = ("time/fps", "rollout/fps")


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def latest_sweep_dir() -> Path | None:
    sweeps = ROOT / "data" / "sweeps"
    if not sweeps.is_dir():
        return None
    dirs = [p for p in sweeps.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.name)


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_runs(sweep_dir: Path) -> list[dict]:
    manifest = sweep_dir / "manifest.yml"
    runs: list[dict] = []
    if manifest.exists():
        data = _load_yaml(manifest) or {}
        runs = list(data.get("runs") or [])
    else:
        for yml in sorted(sweep_dir.glob("*.yml")):
            if yml.name == "manifest.yml":
                continue
            data = _load_yaml(yml)
            if data:
                runs.append(data)

    # Refresh PID / alive from .pid files when present
    for run in runs:
        pid_path = run.get("pid_path") or str(sweep_dir / f"{run.get('run_id')}.pid")
        if pid_path and Path(pid_path).exists():
            try:
                run["pid"] = int(Path(pid_path).read_text().strip())
            except ValueError:
                pass
    return runs


def find_tb_logdirs(run: dict) -> list[Path]:
    """Locate TensorBoard event directories for a run."""
    candidates: list[Path] = []
    run_id = run.get("run_id")
    tmpl = run.get("out_dir_template")
    if tmpl and run_id:
        try:
            out = Path(tmpl.format(run_id=run_id, seed=0))
            if not out.is_absolute():
                out = ROOT / out
            candidates.append(out)
        except (KeyError, ValueError):
            pass

    # Fallback: search data/ for directories containing run_id
    if run_id:
        data = ROOT / "data"
        if data.is_dir():
            for p in data.iterdir():
                if p.is_dir() and run_id in p.name:
                    candidates.append(p)

    # Deduplicate existing dirs
    seen = set()
    out_dirs = []
    for c in candidates:
        key = str(c.resolve()) if c.exists() else str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.is_dir():
            out_dirs.append(c)
    return out_dirs


def find_tfevent_dirs(root: Path | None = None) -> list[Path]:
    """Find directories under data/ that contain TensorBoard event files."""
    root = root or (ROOT / "data")
    if not root.is_dir():
        return []

    found: set[Path] = set()
    for events in root.rglob("events.out.tfevents.*"):
        if events.is_file():
            found.add(events.parent)
    return sorted(found, key=lambda p: str(p))


def discover_local_run_dirs(root: Path | None = None) -> list[dict]:
    """Discover local training run log dirs from scout/, sweeps/, and data/.

    Returns dicts with run_id, logdirs, source, pid (optional), alive.
    """
    root = root or (ROOT / "data")
    runs_by_id: dict[str, dict] = {}

    def upsert(run_id: str, logdirs: list[Path], *, source: str, pid=None, meta=None):
        entry = runs_by_id.setdefault(
            run_id,
            {
                "run_id": run_id,
                "logdirs": [],
                "source": source,
                "pid": None,
                "alive": False,
                "meta": {},
            },
        )
        for d in logdirs:
            if d not in entry["logdirs"] and d.is_dir():
                entry["logdirs"].append(d)
        if pid:
            entry["pid"] = pid
            entry["alive"] = is_pid_alive(int(pid))
        if meta:
            entry["meta"].update(meta)
        # Prefer more specific source labels
        if source in ("scout", "sweep") and entry["source"] == "local":
            entry["source"] = source

    # Manifest-driven sweeps
    sweeps = root / "sweeps"
    if sweeps.is_dir():
        for sweep_dir in sorted(sweeps.iterdir()):
            if not sweep_dir.is_dir():
                continue
            for run in load_runs(sweep_dir):
                rid = run.get("run_id")
                if not rid:
                    continue
                pid = run.get("pid")
                upsert(
                    str(rid),
                    find_tb_logdirs(run),
                    source="sweep",
                    pid=pid,
                    meta={"sweep_dir": str(sweep_dir)},
                )

    # Scout dirs: data/scout/<run_id>/...
    scout = root / "scout"
    if scout.is_dir():
        for p in sorted(scout.iterdir()):
            if p.is_dir():
                upsert(p.name, [p], source="scout")

    # Any leftover tfevents under data/
    for logdir in find_tfevent_dirs(root):
        rel = logdir.relative_to(root) if logdir.is_relative_to(root) else logdir
        parts = rel.parts
        if parts and parts[0] == "sweeps":
            # data/sweeps/<ts>/... usually not the TB dir; TB is often data/<run_id>
            continue
        run_id = parts[0] if parts else logdir.name
        if parts and parts[0] == "scout" and len(parts) > 1:
            run_id = parts[1]
        upsert(str(run_id), [logdir], source="local")

    return list(runs_by_id.values())


def _last_scalar(ea, tags: list[str] | tuple[str, ...]):
    """Return (tag, value, step) for the latest step among matching tags."""
    best = None  # (step, tag, value)
    for tag in tags:
        if tag not in ea.Tags().get("scalars", []):
            continue
        events = ea.Scalars(tag)
        if not events:
            continue
        ev = events[-1]
        if best is None or ev.step >= best[0]:
            best = (ev.step, tag, float(ev.value))
    if best is None:
        return None, None, None
    return best[1], best[2], best[0]


def _best_scalar(ea, tags: list[str] | tuple[str, ...], *, minimize: bool = True):
    """Return best finite value across matching tags (min for finish times)."""
    best = None
    for tag in tags:
        if tag not in ea.Tags().get("scalars", []):
            continue
        for ev in ea.Scalars(tag):
            v = float(ev.value)
            if v != v or v < 0:  # NaN or sentinel
                continue
            if best is None:
                best = v
            elif minimize and v < best:
                best = v
            elif not minimize and v > best:
                best = v
    return best


def read_tb_metrics(logdirs: list[Path]) -> dict:
    """Read latest + best scalars from TensorBoard event dirs.

    Tag conventions (SB3 + LogCallback):
      rollout/success_rate, user/is_success
      rollout/ep_rew_mean
      user/time              — HUD seconds (not W&B protocol time)
      user/split_100m_time  — HUD seconds at 100m (-1 until crossed)
      time/fps
    """
    try:
        from tensorboard.backend.event_processing.event_accumulator import (
            EventAccumulator,
        )
    except ImportError:
        return {"error": "tensorboard not installed"}

    metrics = {
        "success_rate": None,
        "ep_rew": None,
        "time": None,
        "best_time": None,
        "split_100m_time": None,
        "best_split_100m_time": None,
        "fps": None,
        "step": None,
        "tags_seen": [],
    }
    latest_step = -1
    best_times: list[float] = []
    best_splits: list[float] = []

    for d in logdirs:
        ea = EventAccumulator(str(d), size_guidance={"scalars": 0})
        try:
            ea.Reload()
        except Exception:
            continue

        tags = ea.Tags().get("scalars", [])
        metrics["tags_seen"] = sorted(set(metrics["tags_seen"]) | set(tags))

        _, success, _ = _last_scalar(ea, SUCCESS_TAGS)
        _, ep_rew, _ = _last_scalar(ea, EP_REW_TAGS)
        _, user_time, _ = _last_scalar(ea, TIME_TAGS)
        _, split_100, _ = _last_scalar(ea, SPLIT_100M_TAGS)
        _, fps, _ = _last_scalar(ea, FPS_TAGS)

        bt = _best_scalar(ea, TIME_TAGS, minimize=True)
        if bt is not None:
            best_times.append(bt)
        bs = _best_scalar(ea, SPLIT_100M_TAGS, minimize=True)
        if bs is not None:
            best_splits.append(bs)

        step = None
        for tag in tags:
            evs = ea.Scalars(tag)
            if evs:
                step = evs[-1].step
                break

        if step is not None and step >= latest_step:
            latest_step = step
            if success is not None:
                metrics["success_rate"] = success
            if ep_rew is not None:
                metrics["ep_rew"] = ep_rew
            if user_time is not None and user_time == user_time and user_time >= 0:
                metrics["time"] = user_time
            if split_100 is not None and split_100 == split_100 and split_100 >= 0:
                metrics["split_100m_time"] = split_100
            if fps is not None:
                metrics["fps"] = fps
            metrics["step"] = step

    if best_times:
        metrics["best_time"] = min(best_times)
    if best_splits:
        metrics["best_split_100m_time"] = min(best_splits)

    return metrics


def fmt(val, digits=3):
    if val is None:
        return "-"
    if isinstance(val, float):
        if val != val:  # NaN
            return "-"
        return f"{val:.{digits}f}"
    return str(val)


def print_table(rows: list[dict]) -> None:
    headers = ("run_id", "alive", "success", "ep_rew", "time", "split100", "step", "pid")
    widths = {h: len(h) for h in headers}
    rendered = []
    for r in rows:
        row = {
            "run_id": r.get("run_id") or "?",
            "alive": "yes" if r.get("alive") else "no",
            "success": fmt(r.get("success_rate"), 3),
            "ep_rew": fmt(r.get("ep_rew"), 2),
            "time": fmt(r.get("time"), 2),
            "split100": fmt(r.get("split_100m_time"), 2),
            "step": fmt(r.get("step"), 0) if r.get("step") is not None else "-",
            "pid": str(r.get("pid") or "-"),
        }
        for h in headers:
            widths[h] = max(widths[h], len(row[h]))
        rendered.append(row)

    def line(vals):
        return "  ".join(str(vals[h]).ljust(widths[h]) for h in headers)

    print(line({h: h for h in headers}))
    print(line({h: "-" * widths[h] for h in headers}))
    for row in rendered:
        print(line(row))


def collect_rows(sweep_dir: Path) -> list[dict]:
    rows = []
    for run in load_runs(sweep_dir):
        pid = int(run.get("pid") or 0)
        alive = is_pid_alive(pid)
        metrics = read_tb_metrics(find_tb_logdirs(run))
        rows.append(
            {
                "run_id": run.get("run_id"),
                "alive": alive,
                "pid": pid or None,
                "success_rate": metrics.get("success_rate"),
                "ep_rew": metrics.get("ep_rew"),
                "time": metrics.get("time"),
                "split_100m_time": metrics.get("split_100m_time"),
                "best_time": metrics.get("best_time"),
                "fps": metrics.get("fps"),
                "step": metrics.get("step"),
                "error": metrics.get("error"),
            }
        )
    return rows


def collect_all_local_rows(data_root: Path | None = None) -> list[dict]:
    """Collect metrics for all discovered local runs under data/."""
    rows = []
    for run in discover_local_run_dirs(data_root):
        metrics = read_tb_metrics(run["logdirs"])
        rows.append(
            {
                "run_id": run["run_id"],
                "alive": run.get("alive", False),
                "pid": run.get("pid"),
                "source": "local",
                "local_kind": run.get("source"),
                "logdirs": [str(p) for p in run["logdirs"]],
                "success_rate": metrics.get("success_rate"),
                "ep_rew": metrics.get("ep_rew"),
                "time": metrics.get("time"),
                "best_hud_time": metrics.get("best_time"),
                "last_hud_time": metrics.get("time"),
                "split_100m_time": metrics.get("split_100m_time"),
                "best_split_100m_time": metrics.get("best_split_100m_time"),
                "fps": metrics.get("fps"),
                "steps": metrics.get("step"),
                "error": metrics.get("error"),
                "tags_seen": metrics.get("tags_seen"),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Monitor QWOP sweep runs from TensorBoard logs."
    )
    parser.add_argument(
        "sweep_dir",
        nargs="?",
        default=None,
        help="Path to data/sweeps/<timestamp> (default: --latest)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the most recent data/sweeps/* directory",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan data/scout/*, data/sweeps/*, and all tfevents under data/",
    )
    parser.add_argument(
        "--watch",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Refresh every N seconds",
    )
    args = parser.parse_args(argv)

    def once() -> int:
        if args.all:
            rows = collect_all_local_rows()
            print("scan: data/ (scout, sweeps, tfevents)")
            if not rows:
                print("(no runs found)")
            else:
                if any(r.get("error") for r in rows):
                    print("note: %s" % next(r["error"] for r in rows if r.get("error")))
                print_table(rows)
            return 0

        if args.sweep_dir:
            sweep_dir = Path(args.sweep_dir)
            if not sweep_dir.is_absolute():
                sweep_dir = ROOT / sweep_dir
        else:
            sweep_dir = latest_sweep_dir()
            if sweep_dir is None:
                print("No sweeps found under data/sweeps/", file=sys.stderr)
                print("Tip: use --all to scan any TensorBoard logs under data/", file=sys.stderr)
                return 1
            args.latest = True

        if not sweep_dir.is_dir():
            print("Sweep dir not found: %s" % sweep_dir, file=sys.stderr)
            return 1

        rows = collect_rows(sweep_dir)
        if args.watch:
            print("\033[H\033[J", end="")
        print("sweep: %s" % sweep_dir)
        if not rows:
            print("(no runs in manifest)")
        else:
            if any(r.get("error") for r in rows):
                print("note: %s" % rows[0]["error"])
            print_table(rows)
        return 0

    while True:
        code = once()
        if args.watch is None:
            return code
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
