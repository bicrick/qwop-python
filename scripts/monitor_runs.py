#!/usr/bin/env python3
"""Monitor parallel QWOP training runs from TensorBoard event files.

Prints a table: run_id, alive?, last success_rate, last ep_rew, last user/time.

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

import yaml

ROOT = Path(__file__).resolve().parents[1]


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


def load_runs(sweep_dir: Path) -> list[dict]:
    manifest = sweep_dir / "manifest.yml"
    runs: list[dict] = []
    if manifest.exists():
        with open(manifest) as f:
            data = yaml.safe_load(f) or {}
        runs = list(data.get("runs") or [])
    else:
        for yml in sorted(sweep_dir.glob("*.yml")):
            if yml.name == "manifest.yml":
                continue
            with open(yml) as f:
                runs.append(yaml.safe_load(f) or {})

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


def _last_scalar(ea, tags: list[str]):
    """Return (tag, value) for the latest step among matching tags."""
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
        return None, None
    return best[1], best[2]


def read_tb_metrics(logdirs: list[Path]) -> dict:
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
        "step": None,
    }
    latest_step = -1
    for d in logdirs:
        # Event files may be in the dir itself (SB3 logger.configure folder)
        ea = EventAccumulator(str(d), size_guidance={"scalars": 0})
        try:
            ea.Reload()
        except Exception:
            continue

        _, success = _last_scalar(
            ea,
            [
                "user/is_success",
                "rollout/success_rate",
                "eval/success_rate",
            ],
        )
        _, ep_rew = _last_scalar(
            ea,
            [
                "rollout/ep_rew_mean",
                "train/ep_rew_mean",
            ],
        )
        _, user_time = _last_scalar(ea, ["user/time"])

        # Track global step from any available scalar
        step = None
        for tag in ea.Tags().get("scalars", []):
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
            if user_time is not None:
                metrics["time"] = user_time
            metrics["step"] = step

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
    headers = ("run_id", "alive", "success", "ep_rew", "time", "step", "pid")
    widths = {h: len(h) for h in headers}
    rendered = []
    for r in rows:
        row = {
            "run_id": r.get("run_id") or "?",
            "alive": "yes" if r.get("alive") else "no",
            "success": fmt(r.get("success_rate"), 3),
            "ep_rew": fmt(r.get("ep_rew"), 2),
            "time": fmt(r.get("time"), 2),
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
                "step": metrics.get("step"),
                "error": metrics.get("error"),
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
        "--watch",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Refresh every N seconds",
    )
    args = parser.parse_args(argv)

    if args.sweep_dir:
        sweep_dir = Path(args.sweep_dir)
        if not sweep_dir.is_absolute():
            sweep_dir = ROOT / sweep_dir
    else:
        sweep_dir = latest_sweep_dir()
        if sweep_dir is None:
            print("No sweeps found under data/sweeps/", file=sys.stderr)
            return 1
        args.latest = True

    if not sweep_dir.is_dir():
        print("Sweep dir not found: %s" % sweep_dir, file=sys.stderr)
        return 1

    while True:
        rows = collect_rows(sweep_dir)
        if args.watch:
            # Clear-ish refresh for terminals
            print("\033[H\033[J", end="")
        print("sweep: %s" % sweep_dir)
        if not rows:
            print("(no runs in manifest)")
        else:
            if any(r.get("error") for r in rows):
                print("note: %s" % rows[0]["error"])
            print_table(rows)
        if args.watch is None:
            break
        time.sleep(args.watch)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
