"""Tests for the shared support-bundle implementation."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import click

from scc_cli.adapters.local_audit_event_sink import serialize_audit_event
from scc_cli.adapters.zip_archive_writer import ZipArchiveWriter
from scc_cli.application.support_bundle import (
    SUPPORT_BUNDLE_AUDIT_LIMIT,
    SupportBundleDependencies,
    SupportBundleRequest,
    build_support_bundle_manifest,
    create_support_bundle,
    get_default_support_bundle_path,
    redact_paths,
    redact_secrets,
)
from scc_cli.core.contracts import AuditEvent
from scc_cli.core.enums import SeverityLevel
from scc_cli.doctor import CheckResult, DoctorResult


class _FakeFilesystem:
    def __init__(self, files: dict[Path, str] | None = None) -> None:
        self._files = files or {}

    def exists(self, path: Path) -> bool:
        return path in self._files

    def read_text(self, path: Path) -> str:
        return self._files[path]


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class _PassingDoctorRunner:
    def run(self, workspace: str | None = None) -> DoctorResult:
        return DoctorResult(checks=[CheckResult(name="Docker", passed=True, message="OK")])


class _FailingDoctorRunner:
    def __init__(self, message: str = "Doctor check failed") -> None:
        self._message = message

    def run(self, workspace: str | None = None) -> DoctorResult:
        raise RuntimeError(self._message)


def _make_dependencies(
    *,
    filesystem: _FakeFilesystem | None = None,
    doctor_runner: _PassingDoctorRunner | _FailingDoctorRunner | None = None,
    archive_writer: ZipArchiveWriter | None = None,
    launch_audit_path: Path | None = None,
) -> SupportBundleDependencies:
    return SupportBundleDependencies(
        filesystem=filesystem or _FakeFilesystem(),  # type: ignore[arg-type]
        clock=_FixedClock(),  # type: ignore[arg-type]
        doctor_runner=doctor_runner or _PassingDoctorRunner(),  # type: ignore[arg-type]
        archive_writer=archive_writer or ZipArchiveWriter(),  # type: ignore[arg-type]
        launch_audit_path=launch_audit_path or Path("/tmp/launch-events.jsonl"),
    )


class TestSecretRedaction:
    def test_redact_secrets_replaces_auth_values(self) -> None:
        result = redact_secrets({"auth": "secret-token-12345", "name": "test-config"})

        assert result["auth"] == "[REDACTED]"
        assert result["name"] == "test-config"

    def test_redact_secrets_replaces_nested_token_values(self) -> None:
        result = redact_secrets(
            {
                "headers": {"Authorization": "Bearer secret-jwt-token"},
                "plugins": [
                    {"name": "plugin1", "token": "secret1"},
                    {"name": "plugin2", "token": "secret2"},
                ],
            }
        )

        assert result["headers"]["Authorization"] == "[REDACTED]"
        assert result["plugins"][0]["token"] == "[REDACTED]"
        assert result["plugins"][1]["token"] == "[REDACTED]"


class TestPathRedaction:
    def test_redact_paths_replaces_home_directory(self) -> None:
        home = str(Path.home())
        result = redact_paths({"path": f"{home}/projects/my-repo"})

        assert home not in result["path"]
        assert result["path"].startswith("~/")

    def test_redact_paths_handles_nested_structures(self) -> None:
        home = str(Path.home())
        result = redact_paths(
            {
                "workspace": {"path": f"{home}/dev/secret-project"},
                "paths": [f"{home}/one", "./relative/path"],
            }
        )

        assert home not in str(result)
        assert result["paths"][1] == "./relative/path"

    def test_redact_paths_can_be_disabled(self) -> None:
        home = str(Path.home())
        data = {"path": f"{home}/projects/my-repo"}

        assert redact_paths(data, redact=False) == data


class TestSupportBundleManifest:
    def test_build_support_bundle_manifest_includes_expected_sections(self, tmp_path: Path) -> None:
        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=False,
            workspace_path=None,
        )

        manifest = build_support_bundle_manifest(request, dependencies=_make_dependencies())

        assert "generated_at" in manifest
        assert "cli_version" in manifest
        assert "system" in manifest
        assert "config" in manifest
        assert "org_config" in manifest
        assert "doctor" in manifest
        assert "launch_audit" in manifest

    def test_doctor_failure_produces_error_in_manifest(self, tmp_path: Path) -> None:
        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=False,
            workspace_path=None,
        )

        manifest = build_support_bundle_manifest(
            request,
            dependencies=_make_dependencies(doctor_runner=_FailingDoctorRunner()),
        )

        assert manifest["doctor"]["error"] == "Failed to run doctor: Doctor check failed"

    def test_manifest_keeps_launch_audit_summary_when_doctor_fails(self, tmp_path: Path) -> None:
        audit_path = tmp_path / "audit" / "launch-events.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            serialize_audit_event(
                AuditEvent(
                    event_type="launch.preflight.failed",
                    message="Launch preflight failed.",
                    severity=SeverityLevel.ERROR,
                    subject="claude",
                    metadata={
                        "provider_id": "claude",
                        "failure_reason": "Provider-core access blocked",
                    },
                )
            )
            + "\n",
            encoding="utf-8",
        )
        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=True,
            workspace_path=None,
        )

        manifest = build_support_bundle_manifest(
            request,
            dependencies=_make_dependencies(
                doctor_runner=_FailingDoctorRunner(),
                launch_audit_path=audit_path,
            ),
        )

        assert manifest["doctor"]["error"] == "Failed to run doctor: Doctor check failed"
        assert manifest["launch_audit"]["state"] == "available"
        assert (
            manifest["launch_audit"]["last_failure"]["failure_reason"]
            == "Provider-core access blocked"
        )

    def test_manifest_includes_bounded_launch_audit_summary(self, tmp_path: Path) -> None:
        audit_path = tmp_path / "audit" / "launch-events.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            serialize_audit_event(
                AuditEvent(
                    event_type="launch.started",
                    message=f"Launch started {index}",
                    subject="claude",
                    metadata={"provider_id": "claude"},
                )
            )
            for index in range(SUPPORT_BUNDLE_AUDIT_LIMIT + 2)
        ]
        audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=True,
            workspace_path=None,
        )

        manifest = build_support_bundle_manifest(
            request,
            dependencies=_make_dependencies(launch_audit_path=audit_path),
        )

        assert manifest["launch_audit"]["state"] == "available"
        assert len(manifest["launch_audit"]["recent_events"]) == SUPPORT_BUNDLE_AUDIT_LIMIT
        assert manifest["launch_audit"]["recent_events"][0]["message"] == (
            f"Launch started {SUPPORT_BUNDLE_AUDIT_LIMIT + 1}"
        )


class TestEffectiveEgressSection:
    """Tests for the effective_egress section in the support bundle manifest."""

    def test_manifest_includes_effective_egress_section(self, tmp_path: Path) -> None:
        """Should include effective_egress with runtime_backend, network_policy, sets."""
        from unittest.mock import MagicMock

        from scc_cli.core.contracts import RuntimeInfo

        mock_info = RuntimeInfo(
            runtime_id="docker",
            display_name="Docker Desktop",
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            version="27.0.1",
            daemon_reachable=True,
            sandbox_available=True,
            preferred_backend="docker-sandbox",
        )
        mock_adapters = MagicMock()
        mock_adapters.runtime_probe.probe.return_value = mock_info

        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=False,
            workspace_path=None,
        )

        with patch(
            "scc_cli.bootstrap.get_default_adapters",
            return_value=mock_adapters,
        ):
            manifest = build_support_bundle_manifest(request, dependencies=_make_dependencies())

        assert "effective_egress" in manifest
        egress = manifest["effective_egress"]
        assert egress["runtime_backend"] == "docker-sandbox"
        assert "anthropic-core" in egress["resolved_destination_sets"]
        assert "openai-core" in egress["resolved_destination_sets"]

    def test_effective_egress_survives_probe_failure(self, tmp_path: Path) -> None:
        """Should produce effective_egress even when probe raises."""
        request = SupportBundleRequest(
            output_path=tmp_path / "support-bundle.zip",
            redact_paths=False,
            workspace_path=None,
        )

        with patch(
            "scc_cli.bootstrap.get_default_adapters",
            side_effect=RuntimeError("no docker"),
        ):
            manifest = build_support_bundle_manifest(request, dependencies=_make_dependencies())

        assert "effective_egress" in manifest
        egress = manifest["effective_egress"]
        assert egress["runtime_backend"] == "unavailable"
        # Destination sets should still resolve even if probe fails
        assert isinstance(egress["resolved_destination_sets"], list)


class TestSupportBundleArchive:
    def test_create_support_bundle_creates_zip_file(self, tmp_path: Path) -> None:
        output_path = tmp_path / "support-bundle.zip"
        request = SupportBundleRequest(
            output_path=output_path,
            redact_paths=True,
            workspace_path=None,
        )

        result = create_support_bundle(request, dependencies=_make_dependencies())

        assert output_path.exists()
        assert zipfile.is_zipfile(output_path)
        assert "doctor" in result.manifest

    def test_create_support_bundle_contains_manifest(self, tmp_path: Path) -> None:
        output_path = tmp_path / "support-bundle.zip"
        request = SupportBundleRequest(
            output_path=output_path,
            redact_paths=True,
            workspace_path=None,
        )

        create_support_bundle(request, dependencies=_make_dependencies())

        with zipfile.ZipFile(output_path, "r") as archive:
            assert "manifest.json" in archive.namelist()
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

        assert manifest["launch_audit"]["requested_limit"] == SUPPORT_BUNDLE_AUDIT_LIMIT

    def test_get_default_support_bundle_path_returns_zip_path(self, tmp_path: Path) -> None:
        default_path = get_default_support_bundle_path(
            working_directory=tmp_path,
            current_time=datetime(2024, 1, 2, 3, 4, 5),
        )

        assert default_path == tmp_path / "scc-support-bundle-20240102-030405.zip"


class TestSupportBundleCommand:
    def test_json_output_does_not_create_file(self, tmp_path: Path, capsys) -> None:
        output_path = tmp_path / "support-bundle.zip"

        with (
            patch(
                "scc_cli.commands.support.build_default_support_bundle_dependencies",
                return_value=object(),
            ),
            patch(
                "scc_cli.commands.support.build_support_bundle_manifest",
                return_value={"test": "data"},
            ),
        ):
            try:
                from scc_cli.commands.support import support_bundle_cmd

                support_bundle_cmd(
                    output=str(output_path),
                    json_output=True,
                    pretty=False,
                    no_redact_paths=False,
                )
            except click.exceptions.Exit:
                pass

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["kind"] == "SupportBundle"
        assert not output_path.exists()

    def test_command_uses_shared_default_path_helper(self, tmp_path: Path) -> None:
        expected_path = tmp_path / "expected-bundle.zip"

        with (
            patch(
                "scc_cli.commands.support.get_default_support_bundle_path",
                return_value=expected_path,
            ),
            patch(
                "scc_cli.commands.support.build_default_support_bundle_dependencies",
                return_value=object(),
            ),
            patch("scc_cli.commands.support.create_support_bundle") as create_bundle,
        ):
            try:
                from scc_cli.commands.support import support_bundle_cmd

                support_bundle_cmd(
                    output=None,
                    json_output=False,
                    pretty=False,
                    no_redact_paths=False,
                )
            except click.exceptions.Exit:
                pass

        request = create_bundle.call_args.args[0]
        assert request.output_path == expected_path
        assert request.redact_paths is True

    def test_support_app_registers_bundle_command(self) -> None:
        from scc_cli.commands.support import support_app

        command_names = [cmd.name for cmd in support_app.registered_commands]
        assert "bundle" in command_names


class TestSupportBundleImportBoundaries:
    def test_ui_settings_uses_application_default_path_helper(self) -> None:
        source = Path("src/scc_cli/ui/settings.py").read_text(encoding="utf-8")

        assert (
            "from scc_cli.application.support_bundle import get_default_support_bundle_path"
            in source
        )
        assert "from scc_cli.support_bundle import get_default_bundle_path" not in source

    def test_production_code_does_not_import_removed_support_bundle_module(self) -> None:
        offending_files: list[str] = []
        for path in Path("src").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "scc_cli.support_bundle" in source:
                offending_files.append(str(path))

        assert offending_files == []
