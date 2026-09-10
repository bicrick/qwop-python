"""
QWOP Gymnasium Wrappers

Collection of environment wrappers for reward shaping and curriculum learning.
"""

from .reward_shaping_wrapper import (
    RewardShapingWrapper,
    VelocityIncentiveWrapper,
    ProgressiveVelocityIncentiveWrapper,
)
from .anti_scrape_wrapper import AntiScrapeCurriculumWrapper
from .verbose_wrapper import VerboseWrapper
from .record_wrapper import RecordWrapper
from .stuck_detection_wrapper import StuckDetectionWrapper
from .flex_gait_wrapper import FlexibleGaitImitationWrapper
from .early_survival_wrapper import EarlySurvivalWrapper
from .start_pace_wrapper import StartPaceWrapper

__all__ = [
    "RewardShapingWrapper",
    "VelocityIncentiveWrapper",
    "ProgressiveVelocityIncentiveWrapper",
    "AntiScrapeCurriculumWrapper",
    "VerboseWrapper",
    "RecordWrapper",
    "StuckDetectionWrapper",
    "FlexibleGaitImitationWrapper",
    "EarlySurvivalWrapper",
    "StartPaceWrapper",
]
