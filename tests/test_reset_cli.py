from __future__ import annotations

import json
from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from types import TracebackType

import pytest
import typer
from rich.console import Console

from scc_cli.commands import reset as reset_module
from scc_cli.core.exit_codes import EXIT_SUCCESS, EXIT_USAGE
from scc_cli.maintenance import MaintenancePreview, MaintenanceTaskContext, ResetResult, RiskTier


class NoopMaintenanceLock:
    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


@pytest.fixture
def reset_output(monkeypatch: pytest.MonkeyPatch) -> Iterator[StringIO]:
    output = StringIO()
    monkeypatch.setattr(
        reset_module,
        "console",
        Console(file=output, force_terminal=False, width=120),
    )
    yield output


def _success_result(action_id: str) -> ResetResult:
    return ResetResult(
        success=True,
        action_id=action_id,
        risk_tier=RiskTier.SAFE,
        message=f"{action_id} done",
    )


def test_reset_requires_an_action_in_non_interactive_mode(reset_output: StringIO) -> None:
    with pytest.raises(typer.Exit) as exc:
        reset_module.reset_cmd(non_interactive=True)

    assert exc.value.exit_code == EXIT_USAGE
    assert "No action specified" in reset_output.getvalue()


def test_reset_exceptions_scope_requires_exceptions_flag(reset_output: StringIO) -> None:
    with pytest.raises(typer.Exit) as exc:
        reset_module.reset_cmd(cache=True, exceptions_scope="repo", non_interactive=True)

    assert exc.value.exit_code == EXIT_USAGE
    assert "--exceptions-scope requires --exceptions" in reset_output.getvalue()


def test_reset_plan_previews_selected_tasks_without_running(
    monkeypatch: pytest.MonkeyPatch,
    reset_output: StringIO,
) -> None:
    previewed: list[str] = []

    def fake_preview_operation(action_id: str, **_: object) -> MaintenancePreview:
        previewed.append(action_id)
        return MaintenancePreview(
            action_id=action_id,
            risk_tier=RiskTier.SAFE,
            paths=[Path(f"/tmp/{action_id}")],
            description=f"Preview {action_id}",
            item_count=1,
        )

    def fake_run_task(action_id: str, context: MaintenanceTaskContext) -> ResetResult:
        raise AssertionError(f"{action_id} should not run in plan mode")

    monkeypatch.setattr(reset_module, "preview_operation", fake_preview_operation)
    monkeypatch.setattr(reset_module, "run_task", fake_run_task)

    reset_module.reset_cmd(cache=True, contexts=True, plan=True)

    assert previewed == ["clear_cache", "clear_contexts"]
    assert "Reset Preview" in reset_output.getvalue()
    assert "Preview clear_cache" in reset_output.getvalue()
    assert "Preview clear_contexts" in reset_output.getvalue()


def test_reset_executes_selected_tasks_in_cli_order(
    monkeypatch: pytest.MonkeyPatch,
    reset_output: StringIO,
) -> None:
    calls: list[str] = []

    def fake_run_task(action_id: str, context: MaintenanceTaskContext) -> ResetResult:
        calls.append(action_id)
        return _success_result(action_id)

    monkeypatch.setattr(reset_module, "MaintenanceLock", NoopMaintenanceLock)
    monkeypatch.setattr(reset_module, "run_task", fake_run_task)

    with pytest.raises(typer.Exit) as exc:
        reset_module.reset_cmd(cache=True, contexts=True, yes=True)

    assert exc.value.exit_code == EXIT_SUCCESS
    assert calls == ["clear_cache", "clear_contexts"]
    assert "clear_cache done" in reset_output.getvalue()
    assert "clear_contexts done" in reset_output.getvalue()


def test_reset_json_output_collects_results(
    monkeypatch: pytest.MonkeyPatch,
    reset_output: StringIO,
) -> None:
    def fake_run_task(action_id: str, context: MaintenanceTaskContext) -> ResetResult:
        return ResetResult(
            success=True,
            action_id=action_id,
            risk_tier=RiskTier.SAFE,
            bytes_freed=1024,
            message="cache cleared",
        )

    monkeypatch.setattr(reset_module, "MaintenanceLock", NoopMaintenanceLock)
    monkeypatch.setattr(reset_module, "run_task", fake_run_task)

    with pytest.raises(typer.Exit) as exc:
        reset_module.reset_cmd(cache=True, json_output=True)

    payload = json.loads(reset_output.getvalue())
    assert exc.value.exit_code == EXIT_SUCCESS
    assert payload["ok"] is True
    assert payload["total_bytes_freed"] == 1024
    assert payload["actions"] == [
        {
            "id": "clear_cache",
            "risk_tier": 0,
            "status": "success",
            "paths": [],
            "removed_count": 0,
            "bytes_freed": 1024,
            "backup_path": None,
            "message": "cache cleared",
            "error": None,
        }
    ]


def test_reset_continue_on_error_keeps_running_after_task_exception(
    monkeypatch: pytest.MonkeyPatch,
    reset_output: StringIO,
) -> None:
    calls: list[str] = []

    def fake_run_task(action_id: str, context: MaintenanceTaskContext) -> ResetResult:
        calls.append(action_id)
        if action_id == "clear_cache":
            raise RuntimeError("cache boom")
        return _success_result(action_id)

    monkeypatch.setattr(reset_module, "MaintenanceLock", NoopMaintenanceLock)
    monkeypatch.setattr(reset_module, "run_task", fake_run_task)

    with pytest.raises(typer.Exit) as exc:
        reset_module.reset_cmd(
            cache=True,
            contexts=True,
            yes=True,
            continue_on_error=True,
        )

    assert exc.value.exit_code == 1
    assert calls == ["clear_cache", "clear_contexts"]
    assert "Failed: cache boom" in reset_output.getvalue()
    assert "clear_contexts done" in reset_output.getvalue()
