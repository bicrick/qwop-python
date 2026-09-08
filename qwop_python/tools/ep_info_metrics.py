# =============================================================================
# Pure helpers for LogCallback episode-info averaging (no SB3 import).
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable


def mean_optional_key(
    episodes: Sequence[Mapping[str, Any]],
    key: str,
    safe_mean_fn: Callable[[list], float],
) -> float:
    """Average ``key`` over episodes that contain it (skip missing keys)."""
    present = [ep[key] for ep in episodes if key in ep]
    return safe_mean_fn(present)


def mean_is_success(
    episodes: Sequence[Mapping[str, Any]],
    safe_mean_fn: Callable[[list], float],
    *,
    key: str = "is_success",
) -> float:
    """Mean of is_success; missing treated as 0 (same as success filter)."""
    return safe_mean_fn([ep.get(key, 0) for ep in episodes])


def mean_crossed_splits(
    episodes: Sequence[Mapping[str, Any]],
    key: str,
    safe_mean_fn: Callable[[list], float],
) -> float:
    """Average split times that were reached (>= 0); missing == not reached."""
    crossed = [ep[key] for ep in episodes if ep.get(key, -1.0) >= 0.0]
    return safe_mean_fn(crossed) if crossed else float("nan")
