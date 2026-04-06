from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scc_cli.application.launch.finalize_launch import finalize_launch
from scc_cli.application.launch.preflight import evaluate_launch_preflight
from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.core.contracts import AgentLaunchSpec, AuditEvent
from scc_cli.core.errors import (
    InvalidLaunchPlanError,
    LaunchAuditUnavailableError,
    LaunchAuditWriteError,
    LaunchPolicyBlockedError,
    ProviderNotReadyError,
)
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import MountSpec, SandboxHandle, SandboxSpec
from tests.fakes.fake_agent_provider import FakeAgentProvider
from tests.fakes.fake_agent_runner import FakeAgentRunner
from tests.test_application_start_session import FakeGitClient


@dataclass
class RecordingAuditSink:
    events: list[AuditEvent] = field(default_factory=list)

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def describe_destination(self) -> str:
        return "memory://audit"


class FailingAuditSink:
    def append(self, event: AuditEvent) -> None:
        raise OSError("disk full")

    def describe_destination(self) -> str:
        return "/tmp/launch-events.jsonl"


class RecordingSandboxRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def ensure_available(self) -> None:
        return None

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        self.calls += 1
        return SandboxHandle(sandbox_id=f"sandbox-{self.calls}", name="sandbox-name")

    def resume(self, handle: SandboxHandle) -> None:
        return None

    def stop(self, handle: SandboxHandle) -> None:
        return None

    def remove(self, handle: SandboxHandle) -> None:
        return None

    def list_running(self) -> list[SandboxHandle]:
        return []

    def status(self, handle: SandboxHandle):  # pragma: no cover - not used here
        raise NotImplementedError


def _build_plan(
    tmp_path: Path,
    *,
    network_policy: str | None = "open",
    provider_id: str = "claude",
    required_destination_sets: tuple[str, ...] = ("anthropic-core",),
    include_agent_launch_spec: bool = True,
) -> StartSessionPlan:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    resolver_result = ResolverResult(
        workspace_root=workspace_path,
        entry_dir=workspace_path,
        mount_root=workspace_path,
        container_workdir=str(workspace_path),
        is_auto_detected=False,
        is_suspicious=False,
        reason="test",
    )
    sandbox_spec = SandboxSpec(
        image="test-image",
        workspace_mount=MountSpec(source=workspace_path, target=workspace_path),
        workdir=workspace_path,
        network_policy=network_policy,
    )
    agent_launch_spec = None
    if include_agent_launch_spec:
        agent_launch_spec = AgentLaunchSpec(
            provider_id=provider_id,
            argv=("claude",),
            workdir=workspace_path,
            required_destination_sets=required_destination_sets,
        )
    return StartSessionPlan(
        resolver_result=resolver_result,
        workspace_path=workspace_path,
        team=None,
        session_name="session-1",
        resume=False,
        fresh=False,
        current_branch=None,
        effective_config=None,
        sync_result=None,
        sync_error_message=None,
        agent_settings=None,
        sandbox_spec=sandbox_spec,
        agent_launch_spec=agent_launch_spec,
    )


def _build_dependencies(
    *,
    sandbox_runtime: RecordingSandboxRuntime | None = None,
    audit_event_sink: RecordingAuditSink | FailingAuditSink | None = None,
) -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=FakeGitClient(),
        agent_runner=FakeAgentRunner(),
        sandbox_runtime=sandbox_runtime or RecordingSandboxRuntime(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
        agent_provider=FakeAgentProvider(),
        audit_event_sink=audit_event_sink,
    )


def test_evaluate_launch_preflight_rejects_missing_agent_launch_spec(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, include_agent_launch_spec=False)

    with pytest.raises(InvalidLaunchPlanError, match="missing provider launch metadata"):
        evaluate_launch_preflight(plan)


def test_evaluate_launch_preflight_rejects_blank_provider_identity(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, provider_id="   ")

    with pytest.raises(InvalidLaunchPlanError, match="missing provider identity"):
        evaluate_launch_preflight(plan)


def test_evaluate_launch_preflight_rejects_blank_required_destination_name(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, required_destination_sets=("anthropic-core", "   "))

    with pytest.raises(InvalidLaunchPlanError, match="blank required destination set"):
        evaluate_launch_preflight(plan)


def test_finalize_launch_emits_preflight_and_launch_started_events_for_allowed_launch(
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    runtime = RecordingSandboxRuntime()
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(sandbox_runtime=runtime, audit_event_sink=sink)

    handle = finalize_launch(plan, dependencies=dependencies)

    assert handle.sandbox_id == "sandbox-1"
    assert runtime.calls == 1
    assert [event.event_type for event in sink.events] == [
        "launch.preflight.passed",
        "launch.started",
    ]
    assert sink.events[0].metadata["provider_id"] == "claude"
    assert sink.events[0].metadata["required_destination_sets"] == "anthropic-core"
    assert sink.events[1].metadata["sandbox_id"] == "sandbox-1"


def test_finalize_launch_blocks_locked_down_provider_launch_before_runtime_start(
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path, network_policy="locked-down-web")
    runtime = RecordingSandboxRuntime()
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(sandbox_runtime=runtime, audit_event_sink=sink)

    with pytest.raises(LaunchPolicyBlockedError, match="locked-down-web"):
        finalize_launch(plan, dependencies=dependencies)

    assert runtime.calls == 0
    assert [event.event_type for event in sink.events] == ["launch.preflight.failed"]
    assert sink.events[0].metadata["failure_reason"].startswith("Launch blocked before startup")


def test_finalize_launch_allows_standalone_launch_without_required_destination_sets(
    tmp_path: Path,
) -> None:
    plan = _build_plan(
        tmp_path,
        network_policy=None,
        provider_id="codex",
        required_destination_sets=(),
    )
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(audit_event_sink=sink)

    handle = finalize_launch(plan, dependencies=dependencies)

    assert handle.sandbox_id == "sandbox-1"
    assert sink.events[0].metadata["network_policy"] == "open"
    assert sink.events[0].metadata["required_destination_sets"] == ""
    assert sink.events[0].subject == "codex"


def test_finalize_launch_fails_closed_when_audit_write_fails(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    runtime = RecordingSandboxRuntime()
    dependencies = _build_dependencies(
        sandbox_runtime=runtime,
        audit_event_sink=FailingAuditSink(),
    )

    with pytest.raises(LaunchAuditWriteError, match="launch-events.jsonl"):
        finalize_launch(plan, dependencies=dependencies)

    assert runtime.calls == 0


def test_finalize_launch_requires_audit_sink_once_preflight_seam_is_in_use(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    dependencies = _build_dependencies(audit_event_sink=None)

    with pytest.raises(LaunchAuditUnavailableError):
        finalize_launch(plan, dependencies=dependencies)


# ═══════════════════════════════════════════════════════════════════════════════
# Enforced-mode destination resolution validation
# ═══════════════════════════════════════════════════════════════════════════════


def test_evaluate_launch_preflight_blocks_unresolvable_enforced_destinations(
    tmp_path: Path,
) -> None:
    """Enforced mode with an unknown destination set name should raise."""
    plan = _build_plan(
        tmp_path,
        network_policy="web-egress-enforced",
        required_destination_sets=("totally-unknown-set",),
    )

    with pytest.raises(LaunchPolicyBlockedError, match="resolution failed"):
        evaluate_launch_preflight(plan)


def test_evaluate_launch_preflight_allows_resolvable_enforced_destinations(
    tmp_path: Path,
) -> None:
    """Enforced mode with known destination set names should pass preflight."""
    plan = _build_plan(
        tmp_path,
        network_policy="web-egress-enforced",
        required_destination_sets=("anthropic-core",),
    )

    decision = evaluate_launch_preflight(plan)
    assert decision.provider_id == "claude"
    assert decision.network_policy == "web-egress-enforced"
    assert decision.required_destination_sets == ("anthropic-core",)


def test_evaluate_launch_preflight_enforced_empty_destinations_passes(
    tmp_path: Path,
) -> None:
    """Enforced mode with no required destination sets should pass preflight."""
    plan = _build_plan(
        tmp_path,
        network_policy="web-egress-enforced",
        required_destination_sets=(),
    )

    decision = evaluate_launch_preflight(plan)
    assert decision.network_policy == "web-egress-enforced"


def test_evaluate_launch_preflight_enforced_mixed_known_unknown_blocks(
    tmp_path: Path,
) -> None:
    """Enforced mode with a mix of known and unknown sets should raise."""
    plan = _build_plan(
        tmp_path,
        network_policy="web-egress-enforced",
        required_destination_sets=("anthropic-core", "nonexistent-set"),
    )

    with pytest.raises(LaunchPolicyBlockedError, match="resolution failed"):
        evaluate_launch_preflight(plan)


# ═══════════════════════════════════════════════════════════════════════════════
# Commands-layer preflight: typed readiness model and pure/side-effect split
# ═══════════════════════════════════════════════════════════════════════════════

from unittest.mock import patch

from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
    _auth_readiness_to_status,
    _infer_resolution_source,
    allowed_provider_ids,
    collect_launch_readiness,
    ensure_launch_ready,
    resolve_launch_provider,
)
from scc_cli.core.contracts import AuthReadiness as AuthReadinessContract


# ─────────────────────────────────────────────────────────────────────────────
# Enum and model tests
# ─────────────────────────────────────────────────────────────────────────────


class TestImageStatus:
    def test_values(self) -> None:
        assert ImageStatus.AVAILABLE.value == "available"
        assert ImageStatus.MISSING.value == "missing"
        assert ImageStatus.UNKNOWN.value == "unknown"


class TestAuthStatus:
    def test_values(self) -> None:
        assert AuthStatus.PRESENT.value == "present"
        assert AuthStatus.MISSING.value == "missing"
        assert AuthStatus.EXPIRED.value == "expired"
        assert AuthStatus.UNKNOWN.value == "unknown"


class TestProviderResolutionSource:
    def test_values(self) -> None:
        assert ProviderResolutionSource.EXPLICIT.value == "explicit"
        assert ProviderResolutionSource.RESUME.value == "resume"
        assert ProviderResolutionSource.WORKSPACE_LAST_USED.value == "workspace_last_used"
        assert ProviderResolutionSource.GLOBAL_PREFERRED.value == "global_preferred"
        assert ProviderResolutionSource.AUTO_SINGLE.value == "auto_single"
        assert ProviderResolutionSource.PROMPTED.value == "prompted"


class TestLaunchReadiness:
    def test_launch_ready_when_all_present(self) -> None:
        r = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=False,
            launch_ready=True,
        )
        assert r.launch_ready is True
        assert r.requires_image_bootstrap is False
        assert r.requires_auth_bootstrap is False

    def test_not_ready_when_image_missing(self) -> None:
        r = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.MISSING,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=True,
            requires_auth_bootstrap=False,
            launch_ready=False,
        )
        assert r.launch_ready is False
        assert r.requires_image_bootstrap is True

    def test_not_ready_when_auth_missing(self) -> None:
        r = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.RESUME,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        assert r.launch_ready is False
        assert r.requires_auth_bootstrap is True

    def test_frozen(self) -> None:
        r = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=False,
            launch_ready=True,
        )
        with pytest.raises(AttributeError):
            r.provider_id = "codex"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# allowed_provider_ids
# ─────────────────────────────────────────────────────────────────────────────


class TestAllowedProviderIds:
    def test_returns_empty_without_org(self) -> None:
        assert allowed_provider_ids(None, None) == ()

    def test_returns_empty_without_team(self) -> None:
        org = MagicMock()
        assert allowed_provider_ids(org, None) == ()

    def test_returns_empty_with_empty_team(self) -> None:
        org = MagicMock()
        assert allowed_provider_ids(org, "") == ()

    def test_returns_empty_when_profile_not_found(self) -> None:
        org = MagicMock()
        org.get_profile.return_value = None
        assert allowed_provider_ids(org, "my-team") == ()

    def test_returns_team_allowed_providers(self) -> None:
        org = MagicMock()
        profile = MagicMock()
        profile.allowed_providers = ("claude", "codex")
        org.get_profile.return_value = profile
        assert allowed_provider_ids(org, "my-team") == ("claude", "codex")


# ─────────────────────────────────────────────────────────────────────────────
# _auth_readiness_to_status
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthReadinessToStatus:
    def test_none_returns_unknown(self) -> None:
        assert _auth_readiness_to_status(None) == AuthStatus.UNKNOWN

    def test_present(self) -> None:
        ar = AuthReadinessContract(status="present", mechanism="oauth_file", guidance="")
        assert _auth_readiness_to_status(ar) == AuthStatus.PRESENT

    def test_missing(self) -> None:
        ar = AuthReadinessContract(status="missing", mechanism="oauth_file", guidance="sign in")
        assert _auth_readiness_to_status(ar) == AuthStatus.MISSING

    def test_expired(self) -> None:
        ar = AuthReadinessContract(status="expired", mechanism="oauth_file", guidance="re-auth")
        assert _auth_readiness_to_status(ar) == AuthStatus.EXPIRED

    def test_unexpected_string(self) -> None:
        ar = AuthReadinessContract(status="weird", mechanism="oauth_file", guidance="")
        assert _auth_readiness_to_status(ar) == AuthStatus.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# _infer_resolution_source
# ─────────────────────────────────────────────────────────────────────────────


class TestInferResolutionSource:
    def test_none_provider_returns_explicit(self) -> None:
        result = _infer_resolution_source(
            provider_id=None,
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.EXPLICIT

    def test_cli_flag_match(self) -> None:
        result = _infer_resolution_source(
            provider_id="claude",
            cli_flag="claude",
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.EXPLICIT

    def test_resume_match(self) -> None:
        result = _infer_resolution_source(
            provider_id="codex",
            cli_flag=None,
            resume_provider="codex",
            workspace_last_used=None,
            config_provider=None,
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.RESUME

    def test_workspace_last_used_match(self) -> None:
        result = _infer_resolution_source(
            provider_id="claude",
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="claude",
            config_provider=None,
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.WORKSPACE_LAST_USED

    def test_global_preferred_match(self) -> None:
        result = _infer_resolution_source(
            provider_id="codex",
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="codex",
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.GLOBAL_PREFERRED

    def test_auto_single_connected(self) -> None:
        result = _infer_resolution_source(
            provider_id="claude",
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected=("claude",),
            allowed=(),
        )
        assert result == ProviderResolutionSource.AUTO_SINGLE

    def test_auto_single_one_allowed(self) -> None:
        result = _infer_resolution_source(
            provider_id="codex",
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected=(),
            allowed=("codex",),
        )
        assert result == ProviderResolutionSource.AUTO_SINGLE

    def test_precedence_cli_over_resume(self) -> None:
        """cli_flag takes precedence over resume_provider."""
        result = _infer_resolution_source(
            provider_id="claude",
            cli_flag="claude",
            resume_provider="claude",
            workspace_last_used=None,
            config_provider=None,
            connected=(),
            allowed=(),
        )
        assert result == ProviderResolutionSource.EXPLICIT


# ─────────────────────────────────────────────────────────────────────────────
# collect_launch_readiness
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectLaunchReadiness:
    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_ready_when_both_present(self, mock_image: MagicMock) -> None:
        mock_image.return_value = ImageStatus.AVAILABLE

        adapters = MagicMock()
        provider = MagicMock()
        provider.auth_check.return_value = AuthReadinessContract(
            status="present", mechanism="oauth_file", guidance=""
        )
        adapters.agent_provider = provider

        readiness = collect_launch_readiness(
            "claude", ProviderResolutionSource.EXPLICIT, adapters
        )
        assert readiness.launch_ready is True
        assert readiness.image_status == ImageStatus.AVAILABLE
        assert readiness.auth_status == AuthStatus.PRESENT

    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_not_ready_when_image_missing(self, mock_image: MagicMock) -> None:
        mock_image.return_value = ImageStatus.MISSING

        adapters = MagicMock()
        provider = MagicMock()
        provider.auth_check.return_value = AuthReadinessContract(
            status="present", mechanism="oauth_file", guidance=""
        )
        adapters.agent_provider = provider

        readiness = collect_launch_readiness(
            "claude", ProviderResolutionSource.EXPLICIT, adapters
        )
        assert readiness.launch_ready is False
        assert readiness.requires_image_bootstrap is True
        assert readiness.requires_auth_bootstrap is False

    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_not_ready_when_auth_missing(self, mock_image: MagicMock) -> None:
        mock_image.return_value = ImageStatus.AVAILABLE

        adapters = MagicMock()
        provider = MagicMock()
        provider.auth_check.return_value = AuthReadinessContract(
            status="missing", mechanism="oauth_file", guidance="sign in"
        )
        adapters.agent_provider = provider

        readiness = collect_launch_readiness(
            "claude", ProviderResolutionSource.EXPLICIT, adapters
        )
        assert readiness.launch_ready is False
        assert readiness.requires_auth_bootstrap is True

    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_auth_expired_requires_bootstrap(self, mock_image: MagicMock) -> None:
        mock_image.return_value = ImageStatus.AVAILABLE

        adapters = MagicMock()
        provider = MagicMock()
        provider.auth_check.return_value = AuthReadinessContract(
            status="expired", mechanism="oauth_file", guidance="re-auth"
        )
        adapters.agent_provider = provider

        readiness = collect_launch_readiness(
            "claude", ProviderResolutionSource.EXPLICIT, adapters
        )
        assert readiness.requires_auth_bootstrap is True
        assert readiness.auth_status == AuthStatus.EXPIRED


# ─────────────────────────────────────────────────────────────────────────────
# ensure_launch_ready
# ─────────────────────────────────────────────────────────────────────────────


class TestEnsureLaunchReady:
    def test_noop_when_ready(self) -> None:
        readiness = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=False,
            launch_ready=True,
        )
        ensure_launch_ready(
            readiness, console=MagicMock(), non_interactive=False, show_notice=MagicMock()
        )

    @patch("scc_cli.commands.launch.provider_image.ensure_provider_image")
    def test_calls_ensure_image_when_missing(self, mock_ensure: MagicMock) -> None:
        readiness = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.MISSING,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=True,
            requires_auth_bootstrap=False,
            launch_ready=False,
        )
        console = MagicMock()
        notice = MagicMock()
        ensure_launch_ready(
            readiness, console=console, non_interactive=False, show_notice=notice
        )
        mock_ensure.assert_called_once_with(
            "claude", console=console, non_interactive=False, show_notice=notice
        )

    def test_non_interactive_auth_missing_raises(self) -> None:
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        with pytest.raises(ProviderNotReadyError, match="auth cache is missing"):
            ensure_launch_ready(
                readiness, console=MagicMock(), non_interactive=True, show_notice=MagicMock()
            )

    def test_non_interactive_auth_expired_raises(self) -> None:
        readiness = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.EXPIRED,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        with pytest.raises(ProviderNotReadyError, match="auth cache is expired"):
            ensure_launch_ready(
                readiness, console=MagicMock(), non_interactive=True, show_notice=MagicMock()
            )

    def test_interactive_auth_missing_calls_show_notice(self) -> None:
        readiness = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        notice = MagicMock()
        ensure_launch_ready(
            readiness, console=MagicMock(), non_interactive=False, show_notice=notice
        )
        notice.assert_called_once()
        call_args = notice.call_args[0]
        assert "Authenticating" in call_args[0]

    @patch("scc_cli.commands.launch.provider_image.ensure_provider_image")
    def test_both_missing_fixes_image_then_auth(self, mock_ensure_image: MagicMock) -> None:
        readiness = LaunchReadiness(
            provider_id="claude",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.MISSING,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=True,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        notice = MagicMock()
        ensure_launch_ready(
            readiness, console=MagicMock(), non_interactive=False, show_notice=notice
        )
        # Image should be ensured
        mock_ensure_image.assert_called_once()
        # Auth notice should also fire
        assert notice.call_count >= 1


# ─────────────────────────────────────────────────────────────────────────────
# resolve_launch_provider
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveLaunchProvider:
    def test_explicit_flag(self) -> None:
        adapters = MagicMock()
        provider_id, source = resolve_launch_provider(
            cli_flag="claude",
            resume_provider=None,
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=True,
        )
        assert provider_id == "claude"
        assert source == ProviderResolutionSource.EXPLICIT

    def test_resume_provider(self) -> None:
        adapters = MagicMock()
        provider_id, source = resolve_launch_provider(
            cli_flag=None,
            resume_provider="codex",
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=True,
        )
        assert provider_id == "codex"
        assert source == ProviderResolutionSource.RESUME

    def test_non_interactive_multiple_providers_raises(self) -> None:
        adapters = MagicMock()
        # No flags, no connected → multiple providers, non-interactive
        with pytest.raises(ProviderNotReadyError, match="Multiple providers"):
            resolve_launch_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_path=None,
                config_provider=None,
                normalized_org=None,
                team=None,
                adapters=adapters,
                non_interactive=True,
            )

    def test_global_preferred(self) -> None:
        adapters = MagicMock()
        provider_id, source = resolve_launch_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_path=None,
            config_provider="codex",
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=True,
        )
        assert provider_id == "codex"
        assert source == ProviderResolutionSource.GLOBAL_PREFERRED
