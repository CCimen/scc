"""Enforce dependency direction rules at package boundaries.

Dependency Direction Rules:
    Commands/UI -> Core/Services -> Utils

    - Domain packages (doctor/, docker/, marketplace/, evaluation/) must NOT
      import CLI surface modules (cli_*.py)
    - Core packages (when created) must NOT import ui/
    - Services packages (when created) must NOT import commands/

This test file uses grep-based boundary tests (not just cycle detection) to catch
bad-direction imports that don't form a cycle.
"""

import ast
import importlib
import subprocess
from pathlib import Path

# Use absolute paths relative to this test file
REPO_ROOT = Path(__file__).parent.parent
SRC = REPO_ROOT / "src" / "scc_cli"
TESTS = REPO_ROOT / "tests"


class TestDeadScaffolding:
    """Keep no-op scaffolding out of source and tests."""

    def test_empty_type_checking_blocks_stay_deleted(self) -> None:
        """Delete empty TYPE_CHECKING blocks instead of preserving no-op imports."""
        offenders: list[str] = []
        for root in (SRC, TESTS):
            for path in root.rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.If)
                        and isinstance(node.test, ast.Name)
                        and node.test.id == "TYPE_CHECKING"
                        and len(node.body) == 1
                        and isinstance(node.body[0], ast.Pass)
                    ):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

        assert not offenders, (
            "Empty TYPE_CHECKING blocks are dead scaffolding. Delete the block and "
            "the unused import instead:\n" + "\n".join(offenders)
        )


class TestPickerControlFlowOwnership:
    """Picker UI should not own shared control-flow signals."""

    def test_team_switch_requested_is_owned_by_keys(self) -> None:
        """Import TeamSwitchRequested from ui.keys, not the picker module."""
        picker = importlib.import_module("scc_cli.ui.picker")
        problems: list[str] = []

        if hasattr(picker, "TeamSwitchRequested"):
            problems.append("scc_cli.ui.picker must not re-export TeamSwitchRequested.")

        result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude=test_import_boundaries.py",
                r"(from scc_cli\.ui\.picker import .*TeamSwitchRequested|from \.+ui\.picker import .*TeamSwitchRequested)",
                str(SRC),
                str(TESTS),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            problems.append(
                "TeamSwitchRequested is owned by scc_cli.ui.keys; import it from there.\n"
                f"Found imports:\n{result.stdout}"
            )
        elif result.returncode != 1:
            problems.append(f"TeamSwitchRequested grep failed:\n{result.stderr}")

        assert not problems, "\n\n".join(problems)


class TestDomainDoesNotImportCLI:
    """Domain/service packages must not depend on CLI surface modules."""

    def test_doctor_does_not_import_cli_modules(self) -> None:
        """doctor/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "doctor"),
            ],
            capture_output=True,
            text=True,
        )
        # grep returns 1 when no matches found (which is what we want)
        assert result.returncode == 1, f"doctor/ imports cli_* modules:\n{result.stdout}"

    def test_docker_does_not_import_cli_modules(self) -> None:
        """docker/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "docker"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"docker/ imports cli_* modules:\n{result.stdout}"

    def test_marketplace_does_not_import_cli_modules(self) -> None:
        """marketplace/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "marketplace"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"marketplace/ imports cli_* modules:\n{result.stdout}"

    def test_evaluation_does_not_import_cli_modules(self) -> None:
        """evaluation/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "evaluation"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"evaluation/ imports cli_* modules:\n{result.stdout}"

    def test_utils_does_not_import_cli_modules(self) -> None:
        """utils/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "utils"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"utils/ imports cli_* modules:\n{result.stdout}"


class TestFutureLayerBoundaries:
    """Tests for future package structure (core/, services/).

    These tests are skipped until the packages are created in Phase 4-5.
    They establish the expected boundaries for the target architecture.
    """

    def test_core_does_not_import_ui(self) -> None:
        """core/ must not depend on ui/."""
        core_path = SRC / "core"
        if not core_path.exists():
            # Package not yet created - test passes vacuously
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|import scc_cli\.ui)",
                str(core_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/ imports ui/:\n{result.stdout}"

    def test_services_does_not_import_commands(self) -> None:
        """services/ must not depend on commands/."""
        services_path = SRC / "services"
        if not services_path.exists():
            # Package not yet created - test passes vacuously
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|import scc_cli\.commands)",
                str(services_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/ imports commands/:\n{result.stdout}"

    def test_core_does_not_import_commands(self) -> None:
        """core/ must not depend on commands/."""
        core_path = SRC / "core"
        if not core_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|import scc_cli\.commands)",
                str(core_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/ imports commands/:\n{result.stdout}"


class TestApplicationLayerBoundaries:
    """Application layer must not depend on UI or commands."""

    def test_application_does_not_import_ui_or_commands(self) -> None:
        """application/ must not import from ui/ or commands/."""
        application_path = SRC / "application"
        if not application_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|import scc_cli\.ui|from scc_cli\.commands|import scc_cli\.commands)",
                str(application_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"application/ imports ui/ or commands/ modules:\n{result.stdout}"
        )


class TestMarketplaceSyncBoundary:
    """Marketplace sync workflow has one application owner."""

    def test_marketplace_sync_has_single_owner(self) -> None:
        """sync_marketplace_settings is owned by application/sync_marketplace.py."""
        result = subprocess.run(
            ["grep", "-rEn", r"^def sync_marketplace_settings\(", str(SRC)],
            capture_output=True,
            text=True,
        )
        expected_owner = SRC / "application" / "sync_marketplace.py"
        owners = [
            Path(line.split(":", 1)[0]).resolve() for line in result.stdout.splitlines() if line
        ]

        assert owners == [expected_owner.resolve()], (
            "sync_marketplace_settings must have one owner in "
            f"{expected_owner.relative_to(REPO_ROOT)}.\n"
            f"Found definitions:\n{result.stdout}"
        )


class TestProfilesCompatibilityBoundary:
    """Profile and effective-config callers should import canonical owners."""

    def test_top_level_profiles_facade_stays_deleted(self) -> None:
        """Do not reintroduce the no-behavior scc_cli.profiles compatibility facade."""
        facade = SRC / "profiles.py"
        problems: list[str] = []

        if facade.exists():
            problems.append(
                "Profile helpers are owned by scc_cli.application.profiles and "
                f"scc_cli.application.compute_effective_config; delete {facade.relative_to(REPO_ROOT)}."
            )

        result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude=test_import_boundaries.py",
                "--exclude-dir=__pycache__",
                (
                    r"(from scc_cli import profiles|from scc_cli\.profiles|"
                    r"import scc_cli\.profiles|from \.\. import .*profiles)"
                ),
                str(SRC),
                str(REPO_ROOT / "tests"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            problems.append(
                "Import profile helpers from their canonical owners instead of scc_cli.profiles.\n"
                f"Found imports:\n{result.stdout}"
            )
        elif result.returncode != 1:
            problems.append(f"profiles facade grep failed:\n{result.stderr}")

        assert not problems, "\n\n".join(problems)


class TestEffectiveConfigOwnershipBoundary:
    """EffectiveConfig is the application merge result, not a marketplace result."""

    def test_effective_config_class_has_single_application_owner(self) -> None:
        """Only application/effective_config_models.py should define EffectiveConfig."""
        expected_owner = SRC / "application" / "effective_config_models.py"
        result = subprocess.run(
            ["grep", "-rEn", r"^class EffectiveConfig(\(|:)", str(SRC)],
            capture_output=True,
            text=True,
        )
        owners = [
            Path(line.split(":", 1)[0]).resolve() for line in result.stdout.splitlines() if line
        ]

        assert owners == [expected_owner.resolve()], (
            "EffectiveConfig must name only the application-layer org/team/project "
            f"merge result in {expected_owner.relative_to(REPO_ROOT)}.\n"
            f"Found definitions:\n{result.stdout or '<none>'}"
        )

    def test_marketplace_resolution_imports_do_not_use_effective_config_name(self) -> None:
        """Import MarketplaceResolution from marketplace.resolve, not EffectiveConfig."""
        result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude=test_import_boundaries.py",
                (
                    r"(from scc_cli\.marketplace\.resolve import .*EffectiveConfig|"
                    r"from \.marketplace\.resolve import .*EffectiveConfig|"
                    r"from \.resolve import .*EffectiveConfig)"
                ),
                str(SRC),
                str(TESTS),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, (
            "Marketplace resolution should not reuse the application EffectiveConfig name.\n"
            f"Found imports:\n{result.stdout}"
        )


class TestConfigModelOwnershipBoundary:
    """Config model ports stay pure data; normalization lives in services."""

    def test_normalized_config_models_do_not_reintroduce_from_dict(self) -> None:
        """Raw-to-typed normalization belongs in services/config_normalizer.py."""
        tree = ast.parse((SRC / "ports" / "config_models.py").read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                    and item.name == "from_dict"
                ):
                    offenders.append(f"{node.name}.from_dict")

        assert not offenders, (
            "Config model ports must stay pure data; use "
            f"scc_cli.services.config_normalizer instead of {', '.join(offenders)}."
        )


class TestSetupSurfaceBoundary:
    """Setup keeps one live wizard path instead of legacy prompt twins."""

    DEAD_SETUP_PROMPTS = {
        "prompt_has_org_config",
        "prompt_auth_method",
        "prompt_profile_selection",
        "build_profile_table",
        "prompt_profile_choice",
        "prompt_hooks_enablement",
    }
    DEAD_SETUP_CONFIRMATION = {
        "_build_setup_summary",
        "_confirm_setup",
    }

    def test_legacy_setup_prompt_surface_stays_deleted(self) -> None:
        """The arrow-key setup wizard owns prompting; do not keep old prompt twins."""
        setup_tree = ast.parse((SRC / "setup.py").read_text(encoding="utf-8"))
        definitions = {
            node.name for node in ast.walk(setup_tree) if isinstance(node, ast.FunctionDef)
        }
        legacy_defs = sorted(self.DEAD_SETUP_PROMPTS.intersection(definitions))

        assert not legacy_defs, (
            "setup.py should keep one live setup prompt path. Delete legacy prompt "
            f"helpers instead of testing unreachable twins: {', '.join(legacy_defs)}"
        )

    def test_dead_setup_confirmation_helpers_stay_deleted(self) -> None:
        """Setup config should not keep unused confirmation helper twins."""
        setup_config_tree = ast.parse((SRC / "setup_config.py").read_text(encoding="utf-8"))
        definitions = {
            node.name for node in ast.walk(setup_config_tree) if isinstance(node, ast.FunctionDef)
        }
        legacy_defs = sorted(self.DEAD_SETUP_CONFIRMATION.intersection(definitions))

        assert not legacy_defs, (
            "setup_config.py should not keep unused confirmation helpers. "
            f"Found: {', '.join(legacy_defs)}"
        )

    def test_save_setup_config_reuses_proposed_config_builder(self) -> None:
        """Persisted config must use the same assembly owner as the preview."""
        setup_config_tree = ast.parse((SRC / "setup_config.py").read_text(encoding="utf-8"))
        save_function = next(
            node
            for node in ast.walk(setup_config_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "save_setup_config"
        )

        calls_builder = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_build_proposed_config"
            for node in ast.walk(save_function)
        )
        assigns_inline_user_config = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "user_config"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
            for node in ast.walk(save_function)
        )

        assert calls_builder and not assigns_inline_user_config, (
            "save_setup_config should delegate config assembly to _build_proposed_config "
            "so preview and persistence cannot drift."
        )


class TestGovernancePatternOwnership:
    """Governance pattern matching has one implementation owner."""

    def test_plugin_pattern_matching_has_single_implementation_owner(self) -> None:
        """Plugin-specific pattern matching is owned by marketplace.normalize.matches_pattern."""
        result = subprocess.run(
            ["grep", "-rEn", r"^def matches_plugin_pattern\(", str(SRC)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            "Plugin pattern matching should be implemented by "
            "marketplace.normalize.matches_pattern, not a duplicate helper.\n"
            f"Found duplicate definitions:\n{result.stdout}"
        )

    def test_optional_plugin_allowlist_semantics_have_single_owner(self) -> None:
        """Optional plugin allowlist semantics are owned by marketplace.normalize."""
        expected_owner = SRC / "marketplace" / "normalize.py"
        owner_result = subprocess.run(
            ["grep", "-rEn", r"def is_plugin_allowed_by_patterns\(", str(SRC)],
            capture_output=True,
            text=True,
        )
        owners = [
            Path(line.split(":", 1)[0]).resolve()
            for line in owner_result.stdout.splitlines()
            if line
        ]

        problems: list[str] = []
        if owners != [expected_owner.resolve()]:
            problems.append(
                "is_plugin_allowed_by_patterns must have one owner in "
                f"{expected_owner.relative_to(REPO_ROOT)}.\n"
                f"Found definitions:\n{owner_result.stdout or '<none>'}"
            )

        duplicate_patterns = {
            "_is_plugin_allowed": r"def _is_plugin_allowed\(",
            "is_allowed_by_patterns": r"def is_allowed_by_patterns\(",
        }
        for name, pattern in duplicate_patterns.items():
            duplicate_result = subprocess.run(
                ["grep", "-rEn", pattern, str(SRC)],
                capture_output=True,
                text=True,
            )
            if duplicate_result.returncode == 0:
                problems.append(
                    f"{name} duplicates plugin allowlist semantics:\n{duplicate_result.stdout}"
                )

        assert not problems, "\n\n".join(problems)

    def test_mcp_policy_matching_has_single_core_owner(self) -> None:
        """MCP policy matching is owned by core.governance_patterns."""
        expected_owner = SRC / "core" / "governance_patterns.py"
        problems: list[str] = []

        for name in (
            "matches_blocked",
            "mcp_candidates",
            "is_mcp_allowed",
            "match_blocked_mcp",
        ):
            result = subprocess.run(
                ["grep", "-rEn", rf"^def {name}\(", str(SRC)],
                capture_output=True,
                text=True,
            )
            owners = [
                Path(line.split(":", 1)[0]).resolve() for line in result.stdout.splitlines() if line
            ]
            if owners != [expected_owner.resolve()]:
                problems.append(
                    f"{name} must have one owner in {expected_owner.relative_to(REPO_ROOT)}.\n"
                    f"Found definitions:\n{result.stdout or '<none>'}"
                )

        validate_source = (SRC / "validate.py").read_text(encoding="utf-8")
        for nested_name in ("any_allowed", "mcp_candidates"):
            if f"def {nested_name}(" in validate_source:
                problems.append(f"validate.py must not define nested MCP matcher {nested_name}().")

        assert not problems, "\n\n".join(problems)


class TestAuditReaderBoundaries:
    """Audit readers share neutral JSONL primitives."""

    def test_audit_readers_share_jsonl_primitives(self) -> None:
        """Launch and safety audit readers must not own duplicate JSONL primitives."""
        application_path = SRC / "application"
        expected_owner = application_path / "audit_jsonl.py"
        safety_audit = application_path / "safety_audit.py"

        problems: list[str] = []
        safety_source = safety_audit.read_text(encoding="utf-8")
        if "from scc_cli.application.launch.audit_log import" in safety_source:
            problems.append("safety_audit.py must not import private launch audit helpers")

        for name in ("scan_line_limit", "tail_lines", "redact_value", "redact_string"):
            result = subprocess.run(
                ["grep", "-rEn", rf"^def {name}\(", str(application_path)],
                capture_output=True,
                text=True,
            )
            owners = [
                Path(line.split(":", 1)[0]).resolve() for line in result.stdout.splitlines() if line
            ]
            if owners != [expected_owner.resolve()]:
                problems.append(
                    f"{name} must have one owner in {expected_owner.relative_to(REPO_ROOT)}.\n"
                    f"Found definitions:\n{result.stdout or '<none>'}"
                )

        for name in ("DEFAULT_SCAN_LINE_FLOOR", "BINARY_CHUNK_SIZE"):
            result = subprocess.run(
                ["grep", "-rEn", rf"^{name}\s*=", str(application_path)],
                capture_output=True,
                text=True,
            )
            owners = [
                Path(line.split(":", 1)[0]).resolve() for line in result.stdout.splitlines() if line
            ]
            if owners != [expected_owner.resolve()]:
                problems.append(
                    f"{name} must have one owner in {expected_owner.relative_to(REPO_ROOT)}.\n"
                    f"Found definitions:\n{result.stdout or '<none>'}"
                )

        for name in ("_scan_line_limit", "_tail_lines", "_redact_value", "_redact_string"):
            result = subprocess.run(
                ["grep", "-rEn", rf"^def {name}\(", str(application_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                problems.append(f"{name} duplicates audit JSONL primitives:\n{result.stdout}")

        assert not problems, "\n\n".join(problems)


class TestMaintenanceOwnershipBoundary:
    """Maintenance operations are owned by the maintenance package."""

    def test_core_maintenance_facade_stays_deleted(self) -> None:
        """Do not reintroduce the no-behavior core.maintenance compatibility facade."""
        facade = SRC / "core" / "maintenance.py"
        problems: list[str] = []

        if facade.exists():
            problems.append(
                "Maintenance operations are owned by scc_cli.maintenance; "
                f"delete {facade.relative_to(REPO_ROOT)}."
            )

        result = subprocess.run(
            [
                "grep",
                "-rEn",
                r"(from scc_cli\.core\.maintenance|import scc_cli\.core\.maintenance)",
                str(SRC),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            problems.append(
                "Import scc_cli.maintenance directly instead of the deleted core facade.\n"
                f"Found imports:\n{result.stdout}"
            )

        assert not problems, "\n\n".join(problems)


class TestDashboardLegacyBoundary:
    """Dashboard flow outcomes should use structured results directly."""

    def test_start_flow_result_has_no_legacy_bool_adapter(self) -> None:
        """Do not reintroduce StartFlowResult bool/None adapter conversions."""
        problems: list[str] = []

        result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude-dir=__pycache__",
                r"from_legacy",
                str(SRC / "application"),
                str(SRC / "ui"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            problems.append(
                "Dashboard start-flow handlers should return explicit StartFlowResult values.\n"
                f"Found legacy adapter references:\n{result.stdout}"
            )
        elif result.returncode != 1:
            problems.append(f"Legacy adapter grep failed:\n{result.stderr}")

        models_file = SRC / "application" / "dashboard_models.py"
        models_tree = ast.parse(models_file.read_text(encoding="utf-8"))
        for node in ast.walk(models_tree):
            if not isinstance(node, ast.ClassDef) or node.name != "StartFlowResult":
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                is_classmethod = any(
                    isinstance(decorator, ast.Name) and decorator.id == "classmethod"
                    for decorator in item.decorator_list
                )
                if not is_classmethod:
                    continue
                boolish_args: list[str] = []
                for arg in item.args.args[1:]:
                    if arg.annotation is None:
                        continue
                    annotation = ast.unparse(arg.annotation)
                    if annotation == "bool" or ("bool" in annotation and "None" in annotation):
                        boolish_args.append(arg.arg)
                if boolish_args:
                    problems.append(
                        "StartFlowResult should not regain a bool/None classmethod adapter. "
                        f"Found {item.name}({', '.join(boolish_args)}) in "
                        f"{models_file.relative_to(REPO_ROOT)}."
                    )

        assert not problems, "\n\n".join(problems)

    def test_container_actions_use_named_result_contract(self) -> None:
        """Container action effects should not cross layers as raw bool/message tuples."""
        models_file = SRC / "application" / "dashboard_models.py"
        reducer_file = SRC / "application" / "dashboard.py"
        actions_file = SRC / "ui" / "dashboard" / "orchestrator_container_actions.py"

        models_source = models_file.read_text(encoding="utf-8")
        reducer_source = reducer_file.read_text(encoding="utf-8")
        actions_source = actions_file.read_text(encoding="utf-8")

        problems: list[str] = []
        if "class ContainerActionResult" not in models_source:
            problems.append("dashboard_models.py must own ContainerActionResult.")
        if "tuple[bool, str | None]" in actions_source:
            problems.append(
                "orchestrator_container_actions.py should return ContainerActionResult, "
                "not tuple[bool, str | None]."
            )
        if (
            "Container effect requires tuple" in reducer_source
            or "isinstance(result, tuple)" in reducer_source
        ):
            problems.append(
                "apply_dashboard_effect_result() should require ContainerActionResult, "
                "not validate tuple internals."
            )

        assert not problems, "\n".join(problems)


class TestDashboardHandlerOwnership:
    """Dashboard handler implementation modules should own their private handlers."""

    def test_container_action_handlers_have_single_owner(self) -> None:
        """Container action handlers are owned by orchestrator_container_actions.py."""
        handler_names = {
            "_handle_container_stop",
            "_handle_container_resume",
            "_handle_container_remove",
        }
        dashboard_path = SRC / "ui" / "dashboard"
        owner_file = dashboard_path / "orchestrator_container_actions.py"
        consumer_files = (
            dashboard_path / "orchestrator.py",
            dashboard_path / "orchestrator_handlers.py",
        )

        problems: list[str] = []
        definitions: dict[str, list[Path]] = {name: [] for name in handler_names}
        for path in dashboard_path.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in handler_names:
                    definitions[node.name].append(path.resolve())

        for name, owners in sorted(definitions.items()):
            if owners != [owner_file.resolve()]:
                formatted = ", ".join(str(path.relative_to(REPO_ROOT)) for path in owners)
                problems.append(
                    f"{name} must be defined only in {owner_file.relative_to(REPO_ROOT)}; "
                    f"found {formatted or '<none>'}."
                )

        for path in consumer_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module in {
                    "orchestrator_container_actions",
                    "orchestrator_handlers",
                }:
                    imported = sorted(
                        handler_names.intersection(alias.name for alias in node.names)
                    )
                    if imported:
                        problems.append(
                            f"{path.relative_to(REPO_ROOT)} should call "
                            "orchestrator_container_actions.<handler>() instead of importing "
                            f"{', '.join(imported)}."
                        )
                if path.name == "orchestrator.py" and isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, ast.List):
                                exported = sorted(
                                    handler_names.intersection(
                                        item.value
                                        for item in node.value.elts
                                        if isinstance(item, ast.Constant)
                                        and isinstance(item.value, str)
                                    )
                                )
                                if exported:
                                    problems.append(
                                        "orchestrator.py should not export private container "
                                        f"action handlers: {', '.join(exported)}."
                                    )

        assert not problems, "\n".join(problems)

    def test_menu_handlers_have_single_owner(self) -> None:
        """Menu handlers are owned by orchestrator_menus.py."""
        handler_names = {
            "_handle_settings",
            "_handle_profile_menu",
            "_handle_sandbox_import",
            "_show_onboarding_banner",
        }
        dashboard_path = SRC / "ui" / "dashboard"
        owner_file = dashboard_path / "orchestrator_menus.py"
        consumer_files = (
            dashboard_path / "orchestrator.py",
            dashboard_path / "orchestrator_handlers.py",
        )

        problems: list[str] = []
        definitions: dict[str, list[Path]] = {name: [] for name in handler_names}
        for path in dashboard_path.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in handler_names:
                    definitions[node.name].append(path.resolve())

        for name, owners in sorted(definitions.items()):
            if owners != [owner_file.resolve()]:
                formatted = ", ".join(str(path.relative_to(REPO_ROOT)) for path in owners)
                problems.append(
                    f"{name} must be defined only in {owner_file.relative_to(REPO_ROOT)}; "
                    f"found {formatted or '<none>'}."
                )

        for path in consumer_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module in {
                    "orchestrator_handlers",
                    "orchestrator_menus",
                }:
                    imported = sorted(
                        handler_names.intersection(alias.name for alias in node.names)
                    )
                    if imported:
                        problems.append(
                            f"{path.relative_to(REPO_ROOT)} should call "
                            "orchestrator_menus.<handler>() instead of importing "
                            f"{', '.join(imported)}."
                        )
                if path.name == "orchestrator.py" and isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, ast.List):
                                exported = sorted(
                                    handler_names.intersection(
                                        item.value
                                        for item in node.value.elts
                                        if isinstance(item, ast.Constant)
                                        and isinstance(item.value, str)
                                    )
                                )
                                if exported:
                                    problems.append(
                                        "orchestrator.py should not export private menu "
                                        f"handlers: {', '.join(exported)}."
                                    )

        assert not problems, "\n".join(problems)


class TestDashboardLaunchRoutingBoundary:
    """Dashboard UI routes launch effects through the launch command owner."""

    BANNED_DASHBOARD_LAUNCH_IMPORTS = {
        "StartSessionRequest",
        "NormalizedOrgConfig",
        "get_default_adapters",
        "prepare_live_start_plan",
        "resolve_launch_conflict",
        "collect_launch_readiness",
        "ensure_launch_ready",
        "resolve_launch_provider",
        "show_auth_bootstrap_panel",
        "show_launch_panel",
        "finalize_launch",
        "_configure_team_settings",
        "set_workspace_last_used_provider",
    }

    def test_dashboard_handlers_do_not_import_launch_internals(self) -> None:
        """Dashboard handlers should call one launch entrypoint, not launch internals."""
        handlers_file = SRC / "ui" / "dashboard" / "orchestrator_handlers.py"
        tree = ast.parse(handlers_file.read_text(encoding="utf-8"))
        problems: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported = sorted(
                self.BANNED_DASHBOARD_LAUNCH_IMPORTS.intersection(
                    alias.name for alias in node.names
                )
            )
            if imported:
                problems.append(
                    f"{handlers_file.relative_to(REPO_ROOT)}:{node.lineno}: {', '.join(imported)}"
                )

        assert not problems, (
            "Dashboard UI should route direct start/resume through the commands.launch "
            "resolved-workspace launch helper instead of importing launch internals:\n"
            + "\n".join(problems)
        )

    def test_dashboard_launch_helper_does_not_record_sessions_yet(self) -> None:
        """Dashboard launch extraction preserves existing session-history behavior."""
        helper_file = SRC / "commands" / "launch" / "resolved_workspace.py"
        source = helper_file.read_text(encoding="utf-8")

        assert "_record_session_and_context" not in source, (
            "Dashboard direct start/resume did not record session history before S04. "
            "Route CLI/wizard/worktree convergence separately before changing this behavior."
        )


class TestPreparedLaunchCompletionBoundary:
    """Migrated launch paths route prepared-plan completion through one owner."""

    MIGRATED_FILES = (
        SRC / "commands" / "launch" / "flow.py",
        SRC / "commands" / "launch" / "flow_interactive.py",
        SRC / "commands" / "launch" / "resolved_workspace.py",
    )
    BANNED_COMPLETION_IMPORTS = {
        "resolve_launch_conflict",
        "show_launch_panel",
        "finalize_launch",
        "set_workspace_last_used_provider",
    }
    BANNED_COMPLETION_CALLS = {
        ("app_launch", "finalize_launch"),
        ("conflict_resolution", "resolve_launch_conflict"),
        ("flow_session", "_record_session_and_context"),
        ("render", "show_launch_panel"),
        ("workspace_local_config", "set_workspace_last_used_provider"),
    }

    def test_migrated_paths_do_not_own_prepared_launch_completion(self) -> None:
        """Prepared-plan conflict/show/finalize/persist behavior has one command owner."""
        problems: list[str] = []

        for path in self.MIGRATED_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = sorted(
                        self.BANNED_COMPLETION_IMPORTS.intersection(
                            alias.name for alias in node.names
                        )
                    )
                    if imported:
                        problems.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}: imports "
                            f"{', '.join(imported)}"
                        )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and (node.func.value.id, node.func.attr) in self.BANNED_COMPLETION_CALLS
                ):
                    problems.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno}: calls "
                        f"{node.func.value.id}.{node.func.attr}"
                    )

        assert not problems, (
            "Migrated launch paths should delegate prepared-plan completion to "
            "commands.launch.completion instead of owning conflict/show/finalize/persist "
            "logic:\n" + "\n".join(problems)
        )


class TestWorktreeLaunchRoutingBoundary:
    """Worktree commands delegate auto-start launch orchestration to launch owners."""

    BANNED_WORKTREE_LAUNCH_IMPORTS = {
        "StartSessionRequest",
        "NormalizedOrgConfig",
        "finalize_launch",
        "prepare_live_start_plan",
        "resolve_launch_provider",
        "collect_launch_readiness",
        "ensure_launch_ready",
    }

    def test_worktree_commands_do_not_import_launch_internals(self) -> None:
        """Worktree command UI should not build live launch plans inline."""
        worktree_file = SRC / "commands" / "worktree" / "worktree_commands.py"
        tree = ast.parse(worktree_file.read_text(encoding="utf-8"))
        problems: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported = sorted(
                self.BANNED_WORKTREE_LAUNCH_IMPORTS.intersection(alias.name for alias in node.names)
            )
            if imported:
                problems.append(
                    f"{worktree_file.relative_to(REPO_ROOT)}:{node.lineno}: {', '.join(imported)}"
                )

        assert not problems, (
            "Worktree commands should delegate created-worktree auto-start to "
            "commands.launch instead of importing launch internals:\n" + "\n".join(problems)
        )


class TestLaunchOwnershipBoundary:
    """Launch preparation has one canonical application owner."""

    def test_launch_package_has_no_private_workspace_compat_aliases(self) -> None:
        """Do not reintroduce private package aliases for launch workspace helpers."""
        init_file = SRC / "commands" / "launch" / "__init__.py"
        tree = ast.parse(init_file.read_text())
        aliases = (
            "_validate_and_resolve_workspace",
            "_prepare_workspace",
            "_resolve_workspace_team",
            "_resolve_mount_and_branch",
            "_warn_if_non_worktree",
        )

        bound_names: list[str] = []
        exported_names: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                bound_names.extend(alias.asname or alias.name for alias in node.names)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bound_names.append(target.id)
                        if target.id == "__all__" and isinstance(node.value, ast.List):
                            exported_names.extend(
                                item.value
                                for item in node.value.elts
                                if isinstance(item, ast.Constant) and isinstance(item.value, str)
                            )

        bound_aliases = sorted(set(aliases).intersection(bound_names))
        exported_aliases = sorted(set(aliases).intersection(exported_names))
        problems = []
        if bound_aliases:
            problems.append(f"private bindings: {', '.join(bound_aliases)}")
        if exported_aliases:
            problems.append(f"private __all__ entries: {', '.join(exported_aliases)}")

        assert not problems, (
            "commands.launch should expose canonical public exports only. "
            "Import workspace/render owners directly instead of private compat aliases.\n"
            f"Found aliases: {'; '.join(problems)}"
        )

    def test_flow_session_helpers_are_owned_by_flow_session(self) -> None:
        """Do not re-export launch session private helpers from flow.py."""
        flow_file = SRC / "commands" / "launch" / "flow.py"
        tree = ast.parse(flow_file.read_text())
        private_helpers = {
            "_resolve_session_selection",
            "_apply_personal_profile",
            "_record_session_and_context",
        }

        imported_helpers: list[str] = []
        exported_helpers: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in {
                "flow_session",
                "scc_cli.commands.launch.flow_session",
            }:
                imported_helpers.extend(alias.name for alias in node.names)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            exported_helpers.extend(
                                item.value
                                for item in node.value.elts
                                if isinstance(item, ast.Constant) and isinstance(item.value, str)
                            )

        imported = sorted(private_helpers.intersection(imported_helpers))
        exported = sorted(private_helpers.intersection(exported_helpers))
        assert not imported and not exported, (
            "commands.launch.flow_session owns launch session helpers; flow.py should call "
            "the owner module and only export start entrypoints.\n"
            f"Imported from flow_session: {', '.join(imported) or '<none>'}\n"
            f"Exported in __all__: {', '.join(exported) or '<none>'}"
        )

    def test_start_session_preparation_has_single_owner(self) -> None:
        """Start-session preparation must not have a launch-plan facade twin."""
        expected_owner = SRC / "application" / "start_session.py"

        owner_result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude-dir=__pycache__",
                r"^def prepare_start_session\(",
                str(SRC),
            ],
            capture_output=True,
            text=True,
        )
        owners = [
            Path(line.split(":", 1)[0]).resolve()
            for line in owner_result.stdout.splitlines()
            if line
        ]

        problems: list[str] = []
        if owners != [expected_owner.resolve()]:
            problems.append(
                "prepare_start_session must have one owner in "
                f"{expected_owner.relative_to(REPO_ROOT)}.\n"
                f"Found definitions:\n{owner_result.stdout or '<none>'}"
            )

        twin_result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude-dir=__pycache__",
                r"prepare_launch_plan|PrepareLaunchPlan",
                str(SRC),
            ],
            capture_output=True,
            text=True,
        )
        if twin_result.returncode == 0:
            problems.append(
                "Launch plan preparation is owned by prepare_start_session; "
                "do not reintroduce prepare_launch_plan aliases.\n"
                f"Found twins:\n{twin_result.stdout}"
            )

        assert not problems, "\n\n".join(problems)

    def test_auth_bootstrap_redirect_stays_deleted(self) -> None:
        """Auth bootstrap behavior is owned by commands.launch.preflight."""
        redirect = SRC / "commands" / "launch" / "auth_bootstrap.py"
        problems: list[str] = []

        if redirect.exists():
            problems.append(
                "Auth bootstrap is owned by commands/launch/preflight.py; "
                f"delete {redirect.relative_to(REPO_ROOT)}."
            )

        result = subprocess.run(
            [
                "grep",
                "-rEn",
                r"(from scc_cli\.commands\.launch\.auth_bootstrap|import scc_cli\.commands\.launch\.auth_bootstrap)",
                str(SRC),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            problems.append(
                "Import commands.launch.preflight instead of the deleted auth bootstrap redirect.\n"
                f"Found imports:\n{result.stdout}"
            )

        assert not problems, "\n\n".join(problems)


class TestExitCodeBoundary:
    """Exit-code source should expose one semantic name per numeric behavior."""

    def test_deprecated_exit_code_aliases_stay_deleted(self) -> None:
        """Use primary semantic exit-code constants instead of deprecated aliases."""
        result = subprocess.run(
            [
                "grep",
                "-rEn",
                "--exclude-dir=__pycache__",
                r"EXIT_(ERROR|VALIDATION|INTERNAL)",
                str(SRC),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, (
            "Use EXIT_NOT_FOUND, EXIT_TOOL, or EXIT_PREREQ directly instead of "
            "deprecated exit-code aliases.\n"
            f"Found aliases:\n{result.stdout}"
        )

    def test_dead_exception_exit_code_map_stays_deleted(self) -> None:
        """Programmatic error mapping is owned by core.error_mapping.to_exit_code."""
        banned_tokens = ("EXIT_CODE_MAP", "get_exit_code_for_exception")
        checked_files = [
            SRC / "core" / "exit_codes.py",
            SRC / "core" / "__init__.py",
        ]
        problems: list[str] = []

        for path in checked_files:
            content = path.read_text()
            found = [token for token in banned_tokens if token in content]
            if found:
                problems.append(
                    f"{path.relative_to(REPO_ROOT)} still exports dead mapper tokens: "
                    f"{', '.join(found)}"
                )

        assert not problems, "\n".join(problems)


class TestWorktreeExportBoundary:
    """Worktree package exports should not keep unused private aliases."""

    def test_worktree_package_has_no_private_container_status_alias(self) -> None:
        """Import is_container_stopped directly instead of a package-level private alias."""
        init_file = SRC / "commands" / "worktree" / "__init__.py"
        content = init_file.read_text()

        assert "_is_container_stopped" not in content, (
            "commands.worktree should expose is_container_stopped directly; "
            "do not reintroduce the private _is_container_stopped alias."
        )


class TestAdapterBoundaries:
    """Adapter layer must not depend on UI and only bootstrap composes adapters."""

    def test_adapters_do_not_import_ui(self) -> None:
        """adapters/ must not import from ui/."""
        adapters_path = SRC / "adapters"
        if not adapters_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|import scc_cli\.ui|from \.\.ui)",
                str(adapters_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"adapters/ imports ui/:\n{result.stdout}"

    def test_only_bootstrap_imports_adapters(self) -> None:
        """Only bootstrap.py may import adapters for composition."""
        result = subprocess.run(
            [
                "grep",
                "-rIE",
                r"(scc_cli\.adapters|from \.+adapters)",
                str(SRC),
                "--exclude-dir=adapters",
                "--exclude-dir=__pycache__",
                "--exclude=bootstrap.py",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 1), result.stderr

        violations = result.stdout.splitlines()
        assert not violations, "Unexpected non-bootstrap adapter imports:\n" + "\n".join(violations)


class TestGitFacadeDeletionBoundary:
    """Git behavior is owned by services/git, not a top-level facade."""

    def test_top_level_git_facade_stays_deleted(self) -> None:
        """Do not reintroduce the no-behavior scc_cli.git compatibility facade."""
        facade = SRC / "git.py"
        assert not facade.exists(), (
            "Git operations are owned by scc_cli.services.git; "
            f"delete {facade.relative_to(REPO_ROOT)}."
        )

    def test_top_level_git_imports_stay_deleted(self) -> None:
        """Import git operations from scc_cli.services.git."""
        problems: list[str] = []
        paths = list(SRC.rglob("*.py")) + list(TESTS.rglob("*.py"))

        for path in paths:
            if path == Path(__file__):
                continue

            source = path.read_text(encoding="utf-8")
            relative = path.relative_to(REPO_ROOT)
            if "scc_cli.git" in source:
                problems.append(f"{relative}: contains scc_cli.git")

            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "scc_cli.git" or alias.name.startswith("scc_cli.git."):
                            problems.append(f"{relative}:{node.lineno}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imported_names = {alias.name for alias in node.names}
                    if module == "scc_cli" and "git" in imported_names:
                        problems.append(f"{relative}:{node.lineno}: from scc_cli import git")
                    if module == "scc_cli.git" or module.startswith("scc_cli.git."):
                        problems.append(f"{relative}:{node.lineno}: from {module} import ...")
                    if node.level and not module and "git" in imported_names:
                        problems.append(f"{relative}:{node.lineno}: relative import git")
                    if node.level and (module == "git" or module.startswith("git.")):
                        problems.append(f"{relative}:{node.lineno}: relative import from {module}")

        assert not problems, "\n".join(problems)


class TestStartWizardModelOwnershipBoundary:
    """Wizard view models are owned by application.launch.wizard_models."""

    MODEL_NAMES = {
        "CwdContext",
        "QuickResumeOption",
        "QuickResumeViewModel",
        "StartWizardOutcome",
        "StartWizardProgress",
        "StartWizardPrompt",
        "StartWizardViewModel",
        "TeamOption",
        "TeamRepoOption",
        "TeamRepoPickerViewModel",
        "TeamSelectionViewModel",
        "WorkspacePickerViewModel",
        "WorkspaceSourceOption",
        "WorkspaceSourceViewModel",
        "WorkspaceSummary",
    }
    START_WIZARD_RUNTIME_MODELS = {"QuickResumeOption", "StartWizardPrompt"}

    def test_start_wizard_runtime_model_imports_stay_narrow(self) -> None:
        """start_wizard may construct prompts, but must not re-export all UI models."""
        module_path = SRC / "application" / "launch" / "start_wizard.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))

        imported: set[str] = set()
        for node in tree.body:
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "scc_cli.application.launch.wizard_models"
            ):
                imported.update(alias.name for alias in node.names)

        assert imported == self.START_WIZARD_RUNTIME_MODELS, (
            "start_wizard.py owns the state machine and prompt builders only. "
            "Import UI view models from application.launch.wizard_models.\n"
            f"Found runtime imports: {', '.join(sorted(imported)) or '<none>'}"
        )

    def test_consumers_import_wizard_models_from_owner(self) -> None:
        """Consumers should not import UI model dataclasses through start_wizard."""
        start_wizard = SRC / "application" / "launch" / "start_wizard.py"
        wizard_models = SRC / "application" / "launch" / "wizard_models.py"
        problems: list[str] = []

        for path in list(SRC.rglob("*.py")) + list(TESTS.rglob("*.py")):
            if path in {start_wizard, wizard_models, Path(__file__)}:
                continue

            tree = ast.parse(path.read_text(encoding="utf-8"))
            relative = path.relative_to(REPO_ROOT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = node.module or ""
                if node.level:
                    imports_start_wizard = module == "start_wizard" or module.endswith(
                        ".start_wizard"
                    )
                else:
                    imports_start_wizard = module == "scc_cli.application.launch.start_wizard"
                if not imports_start_wizard:
                    continue

                imported_models = sorted(
                    {alias.name for alias in node.names}.intersection(self.MODEL_NAMES)
                )
                if imported_models:
                    problems.append(
                        f"{relative}:{node.lineno}: import "
                        f"{', '.join(imported_models)} from wizard_models"
                    )

        assert not problems, "\n".join(problems)


class TestServicesGitBoundary:
    """services/git/ must be pure data layer with no UI dependencies."""

    def test_services_git_has_no_rich_imports(self) -> None:
        """services/git/ modules must NOT import from rich library.

        The services layer should be purely data-focused. Rich imports
        belong in the ui/ layer.
        """
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            ["grep", "-rE", r"(from rich|import rich)", str(services_git_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/git/ imports rich library:\n{result.stdout}\n"
            f"Move Rich usage to ui/git_render.py or ui/git_interactive.py"
        )

    def test_services_git_has_no_console_params(self) -> None:
        """services/git/ functions should not accept Console parameters.

        Functions that need Console belong in the ui/ layer, not services/.
        """
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            ["grep", "-rE", r"console:\s*Console", str(services_git_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/git/ has Console parameters:\n{result.stdout}\n"
            f"Functions with Console belong in ui/ layer"
        )

    def test_services_git_does_not_import_ui(self) -> None:
        """services/git/ must not import from ui/."""
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(services_git_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/git/ imports ui/:\n{result.stdout}"

    def test_services_git_does_not_import_cli_modules(self) -> None:
        """services/git/ must not import cli_* modules."""
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.\.cli_|import scc_cli\.cli_)",
                str(services_git_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/git/ imports cli_* modules:\n{result.stdout}"


class TestUICanImportServices:
    """Verify UI can properly import from services (positive test)."""

    def test_ui_git_interactive_imports_services(self) -> None:
        """ui/git_interactive.py should import from services/git/."""
        ui_file = SRC / "ui" / "git_interactive.py"
        if not ui_file.exists():
            return

        content = ui_file.read_text()

        # Should import from services/git/
        assert "from ..services.git" in content or "from scc_cli.services.git" in content, (
            "ui/git_interactive.py should import from services/git/"
        )


class TestCoreWorkspaceBoundary:
    """core/workspace.py must be a pure domain module with no external dependencies."""

    def test_core_workspace_no_services_imports(self) -> None:
        """core/workspace.py must not import from services/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.services|from \.\.services|import scc_cli\.services)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports services/:\n{result.stdout}"

    def test_core_workspace_no_ui_imports(self) -> None:
        """core/workspace.py must not import from ui/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports ui/:\n{result.stdout}"

    def test_core_workspace_no_commands_imports(self) -> None:
        """core/workspace.py must not import from commands/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.commands|from \.\.commands|import scc_cli\.commands)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports commands/:\n{result.stdout}"


class TestServicesWorkspaceBoundary:
    """services/workspace/ must not depend on ui/ or commands/."""

    def test_services_workspace_no_ui_imports(self) -> None:
        """services/workspace/ must not import from ui/."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|from \.\.\.ui|import scc_cli\.ui)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/workspace/ imports ui/:\n{result.stdout}"

    def test_services_workspace_no_commands_imports(self) -> None:
        """services/workspace/ must not import from commands/."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|from \.\.commands|from \.\.\.commands|import scc_cli\.commands)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/workspace/ imports commands/:\n{result.stdout}"

    def test_services_workspace_no_cli_modules_imports(self) -> None:
        """services/workspace/ must not import cli_* modules."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.\.cli_|from \.\.\.cli_|import scc_cli\.cli_)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/workspace/ imports cli_* modules:\n{result.stdout}"
        )


class TestNoTestFileDuplicates:
    """Prevent test file duplication patterns that lead to clutter.

    Rule: No deprecated/legacy test files. If a test is obsolete, remove it
    in the same PR that replaces it.

    Naming patterns that indicate duplication:
    - *_new.py: Suggests an old version exists
    - *_legacy.py: Explicitly deprecated
    - *_characterization.py: Safety nets that should be temporary

    Exception: Files can be explicitly allowlisted with a tracking issue link.
    """

    # Allowlist: files with explicit justification and tracking issue
    # M005/S01/T02: characterization tests for top-4 split targets (pre-S02 surgery safety net)
    # M005/S01/T03: characterization tests for remaining high-priority split targets
    ALLOWED_FILES: set[str] = {
        "test_launch_flow_characterization.py",
        "test_dashboard_orchestrator_characterization.py",
        "test_docker_launch_characterization.py",
        "test_personal_profiles_characterization.py",
        "test_compute_effective_config_characterization.py",
        "test_setup_characterization.py",
        "test_worktree_use_cases_characterization.py",
        "test_marketplace_materialize_characterization.py",
        "test_team_commands_characterization.py",
        "test_config_commands_characterization.py",
        "test_wizard_characterization.py",
        "test_app_dashboard_characterization.py",
        "test_launch_preflight_characterization.py",  # M008/S01 — preflight refactor safety net
    }

    def test_no_new_suffix_test_files(self) -> None:
        """Test files should not have _new suffix (implies duplicate exists)."""
        new_files = list(TESTS.glob("test_*_new.py"))
        # Filter out allowlisted files
        unexpected = [f for f in new_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found test files with _new suffix (suggests duplication):\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"If replacing a test file, delete the old one in the same PR.\n"
            f"If this is intentional, add to ALLOWED_FILES with issue link."
        )

    def test_no_legacy_suffix_test_files(self) -> None:
        """Test files should not have _legacy suffix."""
        legacy_files = list(TESTS.glob("test_*_legacy.py"))
        unexpected = [f for f in legacy_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found test files with _legacy suffix:\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"Legacy test files should be deleted, not kept indefinitely."
        )

    def test_no_characterization_suffix_test_files(self) -> None:
        """Characterization tests should be temporary safety nets."""
        char_files = list(TESTS.glob("test_*_characterization.py"))
        unexpected = [f for f in char_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found characterization test files:\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"Characterization tests are temporary refactoring safety nets.\n"
            f"Convert to proper tests and delete when refactoring is complete."
        )


class TestPortsBoundary:
    """ports/ must not depend on UI or command layers."""

    def test_ports_no_ui_imports(self) -> None:
        """ports/ must not import from ui/."""
        ports_path = SRC / "ports"
        if not ports_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(ports_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"ports/ imports ui/:\n{result.stdout}"

    def test_ports_no_commands_imports(self) -> None:
        """ports/ must not import from commands/."""
        ports_path = SRC / "ports"
        if not ports_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|from \.\.commands|import scc_cli\.commands)",
                str(ports_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"ports/ imports commands/:\n{result.stdout}"


class TestAdaptersBoundary:
    """adapters/ must not depend on UI or command layers."""

    def test_adapters_no_ui_imports(self) -> None:
        """adapters/ must not import from ui/."""
        adapters_path = SRC / "adapters"
        if not adapters_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(adapters_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"adapters/ imports ui/:\n{result.stdout}"

    def test_adapters_no_commands_imports(self) -> None:
        """adapters/ must not import from commands/."""
        adapters_path = SRC / "adapters"
        if not adapters_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|from \.\.commands|import scc_cli\.commands)",
                str(adapters_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"adapters/ imports commands/:\n{result.stdout}"
