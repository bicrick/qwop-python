#!/usr/bin/env python3
"""Guard: LogCallback must not KeyError on missing optional ep-info keys.

Reproduces the from-expert QRDQN fine-tune crash where successful episode
infos lacked speed_mps. Imports ep_info_metrics by path (no SB3 required).
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "qwop_python" / "tools" / "ep_info_metrics.py"


def _load_ep_info_metrics():
    spec = importlib.util.spec_from_file_location("ep_info_metrics", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_ep_info_metrics()
mean_optional_key = _mod.mean_optional_key
mean_is_success = _mod.mean_is_success
mean_crossed_splits = _mod.mean_crossed_splits


def _safe_mean(vals: list) -> float:
    return float("nan") if not vals else fmean(vals)


def test_missing_speed_mps_does_not_raise() -> None:
    # Like expert-demo / transfer episode infos: success without speed_mps
    successful = [
        {"is_success": 1, "distance": 100.0, "time": 12.0},
        {"is_success": 1, "distance": 100.0, "time": 11.0, "speed_mps": 9.1},
    ]
    v = mean_optional_key(successful, "speed_mps", _safe_mean)
    assert v == 9.1


def test_all_missing_metric_is_nan() -> None:
    successful = [
        {"is_success": 1, "distance": 100.0},
        {"is_success": 1, "distance": 50.0},
    ]
    v = mean_optional_key(successful, "speed_mps", _safe_mean)
    assert math.isnan(v)


def test_empty_successful_is_nan() -> None:
    assert math.isnan(mean_optional_key([], "speed_mps", _safe_mean))


def test_present_keys_averaged() -> None:
    successful = [
        {"speed_mps": 8.0, "is_success": 1},
        {"speed_mps": 10.0, "is_success": 1},
    ]
    assert mean_optional_key(successful, "speed_mps", _safe_mean) == 9.0


def test_is_success_missing_treated_as_zero() -> None:
    ep_buffer = [
        {"is_success": 1},
        {"distance": 10.0},  # no is_success
        {"is_success": 0},
    ]
    assert mean_is_success(ep_buffer, _safe_mean) == fmean([1, 0, 0])


def test_missing_split_key_not_crossed() -> None:
    ep_buffer = [
        {"split_10m_time": 2.5},
        {"distance": 5.0},  # missing split key
        {"split_10m_time": -1.0},  # not reached
    ]
    assert mean_crossed_splits(ep_buffer, "split_10m_time", _safe_mean) == 2.5


def test_hard_index_would_have_crashed() -> None:
    """Document the old failure mode this guard prevents."""
    successful = [{"is_success": 1, "distance": 100.0}]
    raised = False
    try:
        _ = [ep["speed_mps"] for ep in successful]
    except KeyError:
        raised = True
    assert raised
    assert math.isnan(mean_optional_key(successful, "speed_mps", _safe_mean))


if __name__ == "__main__":
    test_missing_speed_mps_does_not_raise()
    test_all_missing_metric_is_nan()
    test_empty_successful_is_nan()
    test_present_keys_averaged()
    test_is_success_missing_treated_as_zero()
    test_missing_split_key_not_crossed()
    test_hard_index_would_have_crashed()
    print("ok")
