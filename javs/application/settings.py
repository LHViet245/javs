"""Shared application-layer use cases for reading and saving settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from javs.application.history import JobHistoryRepository, build_job_summary
from javs.application.models import SaveSettingsRequest, SaveSettingsResponse, SettingsResponse
from javs.config.loader import (
    apply_settings_changes,
    get_default_config_path,
    load_config,
    save_config,
)
from javs.config.models import JavsConfig
from javs.jobs.executor import JobExecutionContext, JobExecutionResult, JobExecutor

_TERMINAL_JOB_STATUSES = frozenset({"completed", "failed"})

ConfigLoader = Callable[[Path], JavsConfig]
ConfigSaver = Callable[[JavsConfig, Path], None]


class SettingsRunner(Protocol):
    """Runner surface for synchronous, short-running settings saves."""

    async def run_job(
        self,
        *,
        kind: str,
        origin: str,
        request: object | None,
        executor: JobExecutor[object | None],
    ) -> str:
        """Persist and execute a generic job, returning after terminal persistence."""


class SettingsAuditWriter(Protocol):
    """Persist settings audit entries for completed save jobs."""

    def create_entry(
        self,
        *,
        job_id: str,
        source_path: str,
        config_version: int,
        before_json: object | None = None,
        after_json: object | None = None,
        change_summary_json: object | None = None,
    ) -> int:
        """Insert a settings audit row and return its identifier."""


@dataclass(slots=True)
class SettingsUseCase:
    """Read and persist YAML-backed settings through shared application contracts."""

    jobs: JobHistoryRepository
    config_loader: ConfigLoader = load_config
    config_saver: ConfigSaver = save_config
    runner: SettingsRunner | None = None
    settings_audit: SettingsAuditWriter | None = None

    def get(self, source_path: Path | None = None) -> SettingsResponse:
        """Load the active config from YAML and expose it through the shared contract."""
        resolved_path = _resolve_settings_path(source_path)
        config = self.config_loader(resolved_path)
        return SettingsResponse(
            config=config,
            source_path=str(resolved_path),
            config_version=config.config_version,
        )

    async def save(
        self,
        request: SaveSettingsRequest,
        *,
        origin: str = "cli",
    ) -> SaveSettingsResponse:
        """Persist validated settings changes and record audit history in SQLite."""
        if self.runner is None or self.settings_audit is None:
            raise NotImplementedError(
                "SettingsUseCase.save requires a runner and settings_audit repository."
            )

        async def execute_save(
            context: JobExecutionContext[object | None],
        ) -> JobExecutionResult:
            active_request = request
            if isinstance(context.request, SaveSettingsRequest):
                active_request = context.request

            resolved_path = _resolve_settings_path(active_request.source_path)
            current_config = self.config_loader(resolved_path)
            before_json = current_config.model_dump(mode="json")
            updated_config = apply_settings_changes(current_config, active_request.changes)
            self.config_saver(updated_config, resolved_path)

            after_json = updated_config.model_dump(mode="json")
            self.settings_audit.create_entry(
                job_id=context.job_id,
                source_path=str(resolved_path),
                config_version=updated_config.config_version,
                before_json=before_json,
                after_json=after_json,
                change_summary_json=_build_change_summary(before_json, after_json),
            )
            return JobExecutionResult(
                result={
                    "source_path": str(resolved_path),
                    "config_version": updated_config.config_version,
                },
                summary={"saved": 1},
            )

        job_id = await self.runner.run_job(
            kind="save_settings",
            origin=origin,
            request=request,
            executor=execute_save,
        )
        job_record = self._require_completed_job(job_id)
        result_json = job_record.get("result_json") or {}
        source_path = result_json.get("source_path") or request.source_path

        return SaveSettingsResponse(
            job=build_job_summary(job_record),
            settings=self.get(_resolve_settings_path(source_path)),
        )

    def _require_completed_job(self, job_id: str) -> dict[str, Any]:
        job_record = self.jobs.get(job_id)
        if job_record is None:
            raise RuntimeError(
                "save_settings requires a terminal job row to be persisted before returning."
            )

        status = str(job_record.get("status", "unknown"))
        if status == "failed":
            error = job_record.get("error_json") or {"message": "Settings save failed."}
            raise RuntimeError(str(error.get("message", "Settings save failed.")))
        if status not in _TERMINAL_JOB_STATUSES:
            raise RuntimeError(
                "save_settings requires a terminal job row to be persisted before returning."
            )
        return job_record


def _resolve_settings_path(source_path: str | Path | None) -> Path:
    if source_path is None:
        return get_default_config_path()
    return Path(source_path)


def _build_change_summary(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, list[str]]:
    return {"changed": _collect_changed_paths(before, after)}


def _collect_changed_paths(
    before: object,
    after: object,
    prefix: str = "",
) -> list[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        paths: list[str] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.append(path)
                continue
            paths.extend(_collect_changed_paths(before[key], after[key], path))
        return paths

    if before != after and prefix:
        return [prefix]
    return []
