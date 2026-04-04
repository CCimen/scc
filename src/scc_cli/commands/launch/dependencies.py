"""Shared builders for live launch-path dependencies and plans."""

from __future__ import annotations

from rich.console import Console
from rich.status import Status

from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    StartSessionRequest,
    prepare_start_session,
)
from scc_cli.bootstrap import DefaultAdapters
from scc_cli.core.errors import InvalidLaunchPlanError, LaunchAuditUnavailableError
from scc_cli.marketplace.materialize import materialize_marketplace
from scc_cli.marketplace.resolve import resolve_effective_config
from scc_cli.ports.agent_provider import AgentProvider
from scc_cli.ports.audit_event_sink import AuditEventSink
from scc_cli.theme import Spinners

# Dict-based dispatch tables keyed by provider ID.
# Values are DefaultAdapters field names for each role.
_PROVIDER_DISPATCH: dict[str, dict[str, str]] = {
    "claude": {
        "agent_provider": "agent_provider",
        "safety_adapter": "claude_safety_adapter",
    },
    "codex": {
        "agent_provider": "codex_agent_provider",
        "safety_adapter": "codex_safety_adapter",
    },
}

_DEFAULT_PROVIDER_ID = "claude"


def build_start_session_dependencies(
    adapters: DefaultAdapters,
    provider_id: str = _DEFAULT_PROVIDER_ID,
) -> StartSessionDependencies:
    """Build the live start-session dependency bundle from wired adapters.

    Uses provider_id to dispatch the correct agent_provider and safety_adapter
    from the available adapters. Falls back to 'claude' if provider_id is not
    in the dispatch table.
    """
    dispatch = _PROVIDER_DISPATCH.get(provider_id, _PROVIDER_DISPATCH[_DEFAULT_PROVIDER_ID])

    raw_provider = getattr(adapters, dispatch["agent_provider"], None)
    provider = _require_agent_provider(raw_provider)

    sink = _require_audit_event_sink(adapters.audit_event_sink)
    return StartSessionDependencies(
        filesystem=adapters.filesystem,
        remote_fetcher=adapters.remote_fetcher,
        clock=adapters.clock,
        git_client=adapters.git_client,
        agent_runner=adapters.agent_runner,
        sandbox_runtime=adapters.sandbox_runtime,
        resolve_effective_config=resolve_effective_config,
        materialize_marketplace=materialize_marketplace,
        agent_provider=provider,
        audit_event_sink=sink,
    )


def prepare_live_start_plan(
    request: StartSessionRequest,
    *,
    adapters: DefaultAdapters,
    console: Console,
    provider_id: str = _DEFAULT_PROVIDER_ID,
) -> tuple[StartSessionDependencies, StartSessionPlan]:
    """Build dependencies and prepare a live start plan with shared sync behavior."""
    dependencies = build_start_session_dependencies(adapters, provider_id=provider_id)
    if _should_sync_marketplace(request):
        with Status(
            "[cyan]Syncing marketplace settings...[/cyan]",
            console=console,
            spinner=Spinners.NETWORK,
        ):
            plan = prepare_start_session(request, dependencies=dependencies)
    else:
        plan = prepare_start_session(request, dependencies=dependencies)
    return dependencies, plan


def _should_sync_marketplace(request: StartSessionRequest) -> bool:
    return (
        not request.dry_run
        and not request.offline
        and not request.standalone
        and request.team is not None
        and request.org_config is not None
    )


def _require_agent_provider(provider: AgentProvider | None) -> AgentProvider:
    if provider is None:
        raise InvalidLaunchPlanError(
            reason="Launch dependency builder is missing provider wiring.",
        )
    return provider


def _require_audit_event_sink(sink: AuditEventSink | None) -> AuditEventSink:
    if sink is None:
        raise LaunchAuditUnavailableError()
    return sink
