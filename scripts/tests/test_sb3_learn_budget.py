#!/usr/bin/env python3
"""Guard: fine-tune learn budget is additional steps, not an absolute cap.

Reproduces the expert_dqnfd.zip failure mode where loaded num_timesteps
(46.5M) exceeded config total_timesteps (1M) and learn() exited immediately
under reset_num_timesteps=False.

Does not load SB3 or run training — pure budget arithmetic + log format.
Imports sb3_timesteps.py by path so this runs without gymnasium/SB3 installed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "qwop_python" / "tools" / "sb3_timesteps.py"


def _load_sb3_timesteps():
    spec = importlib.util.spec_from_file_location("sb3_timesteps", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_sb3_timesteps()
resolve_learn_total_timesteps = _mod.resolve_learn_total_timesteps
format_learn_budget_log = _mod.format_learn_budget_log


def test_from_scratch_passthrough() -> None:
    assert resolve_learn_total_timesteps(1_000_000, 0) == 1_000_000
    assert (
        resolve_learn_total_timesteps(1_000_000, 0, reset_num_timesteps=True)
        == 1_000_000
    )


def test_finetune_adds_to_loaded_counter() -> None:
    # expert_dqnfd.zip style: huge loaded counter, 1M fine-tune request
    loaded = 46_500_000
    requested = 1_000_000
    learn_total = resolve_learn_total_timesteps(requested, loaded)
    assert learn_total == loaded + requested
    assert learn_total > loaded
    # Old buggy call would pass requested alone and exit immediately:
    assert requested < loaded


def test_reset_num_timesteps_passthrough() -> None:
    assert (
        resolve_learn_total_timesteps(
            1_000_000, 46_500_000, reset_num_timesteps=True
        )
        == 1_000_000
    )


def test_budget_log_line() -> None:
    line = format_learn_budget_log(
        loaded_num_timesteps=46_500_000,
        requested_additional=1_000_000,
        reset_num_timesteps=False,
        learn_total_timesteps=47_500_000,
    )
    assert "loaded num_timesteps=46500000" in line
    assert "requested_additional=1000000" in line
    assert "reset_num_timesteps=False" in line
    assert "learn(total_timesteps=47500000)" in line


def test_rejects_negative() -> None:
    try:
        resolve_learn_total_timesteps(-1, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for negative requested")


def main() -> int:
    test_from_scratch_passthrough()
    test_finetune_adds_to_loaded_counter()
    test_reset_num_timesteps_passthrough()
    test_budget_log_line()
    test_rejects_negative()

    # Dry-run operator log (same line train_sb3 prints to train.log).
    loaded = 46_500_000
    requested = 1_000_000
    learn_total = resolve_learn_total_timesteps(requested, loaded)
    print(
        format_learn_budget_log(
            loaded_num_timesteps=loaded,
            requested_additional=requested,
            reset_num_timesteps=False,
            learn_total_timesteps=learn_total,
        )
    )
    print(
        "ok: effective learn budget %d > loaded num_timesteps %d"
        % (learn_total, loaded)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
