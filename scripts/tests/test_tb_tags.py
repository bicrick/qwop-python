#!/usr/bin/env python3
"""Self-check: monitor_runs reads typical SB3 scalar tag names.

Creates a temporary events file with:
  rollout/success_rate, rollout/ep_rew_mean, user/time,
  user/split_100m_time, time/fps
and asserts read_tb_metrics picks them up (including best HUD time).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _write_scalars(logdir: Path) -> None:
    # Prefer torch SummaryWriter (sb3 extra); fall back to tensorboard FAKE summaries via EventAccumulator-compatible writer
    try:
        from torch.utils.tensorboard import SummaryWriter

        w = SummaryWriter(log_dir=str(logdir))
        w.add_scalar("rollout/success_rate", 0.1, 1000)
        w.add_scalar("rollout/ep_rew_mean", 2.5, 1000)
        w.add_scalar("user/time", 70.0, 500)
        w.add_scalar("user/time", 58.25, 1000)  # last
        w.add_scalar("user/time", 55.6, 750)  # best finish in history
        w.add_scalar("user/split_100m_time", 55.6, 1000)
        w.add_scalar("time/fps", 400.0, 1000)
        w.flush()
        w.close()
        return
    except ImportError:
        pass

    from tensorboard.compat.proto import event_pb2, summary_pb2
    from tensorboard.summary.writer.event_file_writer import EventFileWriter

    writer = EventFileWriter(str(logdir))

    def scalar_event(tag: str, value: float, step: int):
        s = summary_pb2.Summary()
        s.value.add(tag=tag, simple_value=value)
        ev = event_pb2.Event(summary=s, step=step)
        ev.wall_time = float(step)
        writer.add_event(ev)

    scalar_event("rollout/success_rate", 0.1, 1000)
    scalar_event("rollout/ep_rew_mean", 2.5, 1000)
    scalar_event("user/time", 70.0, 500)
    scalar_event("user/time", 55.6, 750)
    scalar_event("user/time", 58.25, 1000)
    scalar_event("user/split_100m_time", 55.6, 1000)
    scalar_event("time/fps", 400.0, 1000)
    writer.flush()
    writer.close()


def main() -> int:
    import monitor_runs

    with tempfile.TemporaryDirectory(prefix="qwop-tb-") as tmp:
        logdir = Path(tmp) / "run_demo"
        logdir.mkdir()
        _write_scalars(logdir)
        metrics = monitor_runs.read_tb_metrics([logdir])

    def near(a, b, eps=1e-3):
        return a is not None and abs(float(a) - float(b)) <= eps

    errors = []
    if metrics.get("error"):
        errors.append(metrics["error"])
    if not near(metrics.get("success_rate"), 0.1):
        errors.append("success_rate=%r want 0.1" % metrics.get("success_rate"))
    if not near(metrics.get("ep_rew"), 2.5):
        errors.append("ep_rew=%r want 2.5" % metrics.get("ep_rew"))
    if not near(metrics.get("time"), 58.25):
        errors.append("time=%r want last 58.25" % metrics.get("time"))
    if not near(metrics.get("best_time"), 55.6):
        errors.append("best_time=%r want 55.6" % metrics.get("best_time"))
    if not near(metrics.get("split_100m_time"), 55.6):
        errors.append("split_100m_time=%r" % metrics.get("split_100m_time"))
    if not near(metrics.get("fps"), 400.0):
        errors.append("fps=%r" % metrics.get("fps"))
    if metrics.get("step") != 1000:
        errors.append("step=%r want 1000" % metrics.get("step"))

    # Tag allow-lists used by dashboard
    for tag in (
        "rollout/success_rate",
        "user/time",
        "user/split_100m_time",
    ):
        if tag not in metrics.get("tags_seen", []):
            errors.append("missing tag in tags_seen: %s" % tag)

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        print("metrics:", metrics)
        return 1

    print("OK - TB tags parsed:")
    for k in (
        "success_rate",
        "ep_rew",
        "time",
        "best_time",
        "split_100m_time",
        "fps",
        "step",
    ):
        print(f"  {k}: {metrics.get(k)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
