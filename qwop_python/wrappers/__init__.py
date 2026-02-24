"""
QWOP Gymnasium Wrappers

Collection of environment wrappers for reward shaping and curriculum learning.
"""

from .reward_shaping_wrapper import (
    RewardShapingWrapper,
    VelocityIncentiveWrapper,
    ProgressiveVelocityIncentiveWrapper,
)
from .verbose_wrapper import VerboseWrapper
from .record_wrapper import RecordWrapper

__all__ = [
    "RewardShapingWrapper",
    "VelocityIncentiveWrapper",
    "ProgressiveVelocityIncentiveWrapper",
    "VerboseWrapper",
    "RecordWrapper",
]
