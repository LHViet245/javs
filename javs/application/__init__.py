"""Shared application contracts for CLI and future API adapters."""

from javs.application.facade import PlatformFacade
from javs.application.history import (
    JobHistoryRepository,
    JobItemsHistoryRepository,
    build_job_detail,
    build_job_item_summary,
    build_job_summary,
)
from javs.application.models import (
    FindMovieRequest,
    FindMovieResponse,
    JobDetail,
    JobItemSummary,
    JobStartResponse,
    JobSummary,
    SaveSettingsRequest,
    SaveSettingsResponse,
    SettingsResponse,
    SortJobRequest,
    UpdateJobRequest,
)

__all__ = [
    "FindMovieRequest",
    "FindMovieResponse",
    "JobDetail",
    "JobHistoryRepository",
    "JobItemSummary",
    "JobItemsHistoryRepository",
    "JobStartResponse",
    "JobSummary",
    "PlatformFacade",
    "SaveSettingsRequest",
    "SaveSettingsResponse",
    "SettingsResponse",
    "SortJobRequest",
    "UpdateJobRequest",
    "build_job_detail",
    "build_job_item_summary",
    "build_job_summary",
]
