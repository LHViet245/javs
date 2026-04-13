"""Route helpers for the thin platform API adapter."""

from javs.api.routes.jobs import (
    handle_find_job,
    handle_get_job,
    handle_list_jobs,
    handle_sort_job,
    handle_update_job,
)
from javs.api.routes.settings import handle_get_settings, handle_save_settings

__all__ = [
    "handle_find_job",
    "handle_get_settings",
    "handle_get_job",
    "handle_list_jobs",
    "handle_save_settings",
    "handle_sort_job",
    "handle_update_job",
]
