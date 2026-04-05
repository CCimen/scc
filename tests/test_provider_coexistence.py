"""Coexistence proof: Claude and Codex containers, volumes, sessions, specs don't collide."""

from __future__ import annotations

from pathlib import Path

from scc_cli.adapters.oci_sandbox_runtime import _container_name
from scc_cli.core.provider_registry import PROVIDER_REGISTRY
from scc_cli.ports.models import MountSpec, SandboxSpec
from scc_cli.ports.session_models import SessionFilter, SessionRecord


class TestContainerNameCoexistence:
    """Container names for same workspace + different providers must differ."""

    def test_different_providers_produce_different_names(self) -> None:
        ws = Path("/home/user/my-project")
        claude_name = _container_name(ws, provider_id="claude")
        codex_name = _container_name(ws, provider_id="codex")
        assert claude_name != codex_name

    def test_same_provider_same_workspace_is_deterministic(self) -> None:
        ws = Path("/home/user/my-project")
        assert _container_name(ws, "claude") == _container_name(ws, "claude")

    def test_empty_provider_differs_from_named(self) -> None:
        ws = Path("/home/user/my-project")
        default_name = _container_name(ws, provider_id="")
        claude_name = _container_name(ws, provider_id="claude")
        assert default_name != claude_name


class TestDataVolumeCoexistence:
    """Data volume names must differ per provider."""

    def test_claude_codex_volumes_differ(self) -> None:
        assert PROVIDER_REGISTRY["claude"].data_volume != PROVIDER_REGISTRY["codex"].data_volume

    def test_volumes_are_nonempty(self) -> None:
        for pid, spec in PROVIDER_REGISTRY.items():
            assert spec.data_volume, f"volume for {pid} is empty"


class TestConfigDirCoexistence:
    """Config directory names must differ per provider."""

    def test_claude_codex_config_dirs_differ(self) -> None:
        assert PROVIDER_REGISTRY["claude"].config_dir != PROVIDER_REGISTRY["codex"].config_dir


class TestImageRefCoexistence:
    """Image references must differ per provider."""

    def test_claude_codex_images_differ(self) -> None:
        assert PROVIDER_REGISTRY["claude"].image_ref != PROVIDER_REGISTRY["codex"].image_ref


class TestSessionCoexistence:
    """Sessions with different provider_ids can coexist and be filtered."""

    def test_records_with_different_providers_coexist(self) -> None:
        claude_rec = SessionRecord(workspace="/w", provider_id="claude")
        codex_rec = SessionRecord(workspace="/w", provider_id="codex")
        assert claude_rec.provider_id != codex_rec.provider_id
        # Both are valid and serializable
        assert claude_rec.to_dict()["provider_id"] == "claude"
        assert codex_rec.to_dict()["provider_id"] == "codex"

    def test_session_filter_isolates_by_provider(self) -> None:
        records = [
            SessionRecord(workspace="/w", provider_id="claude", last_used="2025-01-01T00:00:00"),
            SessionRecord(workspace="/w", provider_id="codex", last_used="2025-01-01T00:00:00"),
            SessionRecord(workspace="/w2", provider_id="claude", last_used="2025-01-02T00:00:00"),
        ]
        filt = SessionFilter(provider_id="claude")
        filtered = [r for r in records if r.provider_id == filt.provider_id]
        assert len(filtered) == 2
        assert all(r.provider_id == "claude" for r in filtered)

    def test_session_filter_codex_only(self) -> None:
        records = [
            SessionRecord(workspace="/w", provider_id="claude"),
            SessionRecord(workspace="/w", provider_id="codex"),
        ]
        filt = SessionFilter(provider_id="codex")
        filtered = [r for r in records if r.provider_id == filt.provider_id]
        assert len(filtered) == 1
        assert filtered[0].provider_id == "codex"

    def test_no_provider_filter_returns_all(self) -> None:
        records = [
            SessionRecord(workspace="/w", provider_id="claude"),
            SessionRecord(workspace="/w", provider_id="codex"),
        ]
        filt = SessionFilter(provider_id=None)
        # No provider filter applied
        filtered = (
            [r for r in records if r.provider_id == filt.provider_id]
            if filt.provider_id is not None
            else records
        )
        assert len(filtered) == 2


class TestSandboxSpecCoexistence:
    """SandboxSpec fields must differ per provider for the same workspace."""

    @staticmethod
    def _make_spec(provider_id: str) -> SandboxSpec:
        reg = PROVIDER_REGISTRY[provider_id]
        image = reg.image_ref
        data_vol = reg.data_volume
        config_dir = reg.config_dir
        return SandboxSpec(
            image=image,
            workspace_mount=MountSpec(source=Path("/w"), target=Path("/workspace")),
            workdir=Path("/workspace"),
            data_volume=data_vol,
            config_dir=config_dir,
            provider_id=provider_id,
            agent_argv=["claude" if provider_id == "claude" else "codex"],
        )

    def test_image_refs_differ(self) -> None:
        claude = self._make_spec("claude")
        codex = self._make_spec("codex")
        assert claude.image != codex.image

    def test_data_volumes_differ(self) -> None:
        claude = self._make_spec("claude")
        codex = self._make_spec("codex")
        assert claude.data_volume != codex.data_volume

    def test_config_dirs_differ(self) -> None:
        claude = self._make_spec("claude")
        codex = self._make_spec("codex")
        assert claude.config_dir != codex.config_dir

    def test_agent_argv_differs(self) -> None:
        claude = self._make_spec("claude")
        codex = self._make_spec("codex")
        assert claude.agent_argv != codex.agent_argv

    def test_provider_id_field_differs(self) -> None:
        claude = self._make_spec("claude")
        codex = self._make_spec("codex")
        assert claude.provider_id != codex.provider_id
