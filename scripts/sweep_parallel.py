#!/usr/bin/env python3
"""Launch parallel QWOP training scouts safely on limited CPU/RAM machines.

Writes PIDs + log paths under data/sweeps/<timestamp>/.

Examples:
  # Built-in scout set (fps / phase-A / speed-safe / PPO vs QRDQN)
  python scripts/sweep_parallel.py --builtin

  # Custom configs, at most 2 concurrent processes, 100k steps each
  python scripts/sweep_parallel.py -c config/sweeps/scout_ppo_fps4.yml \\
      config/sweeps/scout_qrdqn.yml -n 2 --max-timesteps 100000
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

BUILTIN_CONFIGS = [
    "config/sweeps/scout_ppo_fps1.yml",
    "config/sweeps/scout_ppo_fps2.yml",
    "config/sweeps/scout_ppo_fps4.yml",
    "config/sweeps/scout_ppo_phase_a.yml",
    "config/sweeps/scout_ppo_speed_safe.yml",
    "config/sweeps/scout_qrdqn.yml",
]


def default_concurrency() -> int:
    cpus = os.cpu_count() or 1
    return max(1, cpus // 2)


def infer_action(config_path: Path, cfg: dict) -> str:
    """Infer qwop-python train_* action from config path / contents."""
    explicit = cfg.get("action") or cfg.get("train_action")
    if explicit:
        return str(explicit)

    name = config_path.name.lower()
    stem = config_path.stem.lower()
    haystack = f"{name} {stem}"
    if "qrdqn" in haystack:
        return "train_qrdqn"
    if "rppo" in haystack:
        return "train_rppo"
    if "dqn" in haystack:
        return "train_dqn"
    if "a2c" in haystack:
        return "train_a2c"
    if "ppo_5" in haystack or "ppo5" in haystack:
        return "train_ppo_5"
    if "ppo" in haystack:
        return "train_ppo"
    # Default to PPO for unnamed scout configs
    return "train_ppo"


def resolve_qwop_python() -> list[str]:
    """Prefer installed console script; fall back to repo launcher."""
    from shutil import which

    exe = which("qwop-python")
    if exe:
        return [exe]
    launcher = ROOT / "qwop-python.py"
    return [sys.executable, str(launcher)]


def slug_from_config(path: Path) -> str:
    return path.stem.replace(" ", "_")


def launch_one(
    *,
    config_path: Path,
    sweep_dir: Path,
    max_timesteps: int | None,
    run_id: str,
) -> dict:
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    action = infer_action(config_path, cfg)
    log_path = sweep_dir / f"{run_id}.log"
    meta = {
        "run_id": run_id,
        "config": str(config_path),
        "action": action,
        "log_path": str(log_path),
        "max_timesteps": max_timesteps,
        "out_dir_template": cfg.get("out_dir_template"),
    }

    cmd = resolve_qwop_python() + [
        "-c",
        str(config_path),
        action,
        "--run-id",
        run_id,
    ]
    if max_timesteps is not None:
        cmd.extend(["--max-timesteps", str(max_timesteps)])

    env = os.environ.copy()
    # Keep BLAS/OMP from oversubscribing when many train processes run.
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    # Ensure package importable when using qwop-python.py
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    log_f = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    log_f.close()

    meta["pid"] = proc.pid
    meta["cmd"] = cmd
    meta["started_at"] = datetime.now(timezone.utc).isoformat()

    pid_path = sweep_dir / f"{run_id}.pid"
    with open(pid_path, "w") as f:
        f.write(str(proc.pid) + "\n")
    meta["pid_path"] = str(pid_path)

    with open(sweep_dir / f"{run_id}.yml", "w") as f:
        yaml.safe_dump(meta, f)

    print(
        "launched %s pid=%s action=%s config=%s log=%s"
        % (run_id, proc.pid, action, config_path, log_path)
    )
    return {"proc": proc, "meta": meta}


def write_manifest(sweep_dir: Path, runs: list[dict], concurrency: int) -> None:
    manifest = {
        "sweep_dir": str(sweep_dir),
        "concurrency": concurrency,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runs": [r["meta"] for r in runs],
    }
    with open(sweep_dir / "manifest.yml", "w") as f:
        yaml.safe_dump(manifest, f)


def wait_with_limit(active: list[dict], limit: int) -> None:
    """Block until fewer than ``limit`` child processes are still running."""
    while True:
        still = []
        for item in active:
            rc = item["proc"].poll()
            if rc is None:
                still.append(item)
            else:
                mid = item["meta"]["run_id"]
                print("finished %s exit=%s" % (mid, rc))
                item["meta"]["exit_code"] = rc
                item["meta"]["finished_at"] = datetime.now(timezone.utc).isoformat()
                with open(Path(item["meta"]["pid_path"]).with_suffix(".yml"), "w") as f:
                    # refresh run yml without proc
                    yaml.safe_dump(item["meta"], f)
        active[:] = still
        if len(active) < limit:
            return
        time.sleep(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch parallel QWOP training experiments (CPU)."
    )
    parser.add_argument(
        "-c",
        "--configs",
        nargs="*",
        default=None,
        help="YAML train config paths (relative to repo root or absolute)",
    )
    parser.add_argument(
        "--builtin",
        action="store_true",
        help="Use built-in scout sweep (fps 1/2/4, phase-A, speed-safe, QRDQN)",
    )
    parser.add_argument(
        "-n",
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent training processes (default: max(1, cpu_count//2))",
    )
    parser.add_argument(
        "--max-timesteps",
        type=int,
        default=None,
        help="Override total_timesteps for all runs (e.g. 200000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned launches without starting processes",
    )
    args = parser.parse_args(argv)

    configs: list[str] = []
    if args.builtin:
        configs.extend(BUILTIN_CONFIGS)
    if args.configs:
        configs.extend(args.configs)
    if not configs:
        parser.error("Provide --builtin and/or -c CONFIG [CONFIG ...]")

    concurrency = args.concurrency if args.concurrency is not None else default_concurrency()
    concurrency = max(1, concurrency)

    resolved: list[Path] = []
    for c in configs:
        p = Path(c)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print("Config not found: %s" % p, file=sys.stderr)
            return 1
        resolved.append(p.resolve())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sweep_dir = ROOT / "data" / "sweeps" / stamp
    sweep_dir.mkdir(parents=True, exist_ok=True)

    print("sweep_dir=%s concurrency=%d runs=%d" % (sweep_dir, concurrency, len(resolved)))
    if args.max_timesteps is not None:
        print("max_timesteps override=%d" % args.max_timesteps)

    if args.dry_run:
        for p in resolved:
            with open(p) as f:
                cfg = yaml.safe_load(f) or {}
            print(
                "  would launch %s -> %s"
                % (p, infer_action(p, cfg))
            )
        print("dry-run only; wrote no PIDs (sweep_dir created: %s)" % sweep_dir)
        return 0

    runs: list[dict] = []
    active: list[dict] = []

    def _handle_sigint(signum, frame):
        print("\nInterrupted — leaving child trains running. PIDs in %s" % sweep_dir)
        write_manifest(sweep_dir, runs, concurrency)
        sys.exit(130)

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    for idx, config_path in enumerate(resolved):
        wait_with_limit(active, concurrency)
        run_id = "%s-%02d" % (slug_from_config(config_path), idx)
        item = launch_one(
            config_path=config_path,
            sweep_dir=sweep_dir,
            max_timesteps=args.max_timesteps,
            run_id=run_id,
        )
        runs.append(item)
        active.append(item)
        write_manifest(sweep_dir, runs, concurrency)

    # Drain remaining workers (wait until none left).
    wait_with_limit(active, 1)

    write_manifest(sweep_dir, runs, concurrency)
    print("All runs finished. Manifest: %s" % (sweep_dir / "manifest.yml"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
