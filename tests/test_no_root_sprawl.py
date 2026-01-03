"""Prevent uncontrolled growth of top-level modules in src/scc_cli/.

This test ensures that new top-level modules aren't added to src/scc_cli/
without explicit approval. The codebase should have a defined set of allowed
top-level packages.

Target architecture:
    src/scc_cli/
        core/       - domain models, validation, pure transforms
        services/   - use-case orchestration
        commands/   - CLI wiring
        ui/         - presentation
        __init__.py, __main__.py - entry points
        cli.py or main.py - CLI app setup

Current state includes legacy modules that will be refactored into the target
structure. These are tracked in ALLOWED_LEGACY and should shrink over time.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SRC = REPO_ROOT / "src" / "scc_cli"


# Target architecture: these are the expected packages/modules
ALLOWED_CORE = {
    "__init__.py",
    "__main__.py",
    "__pycache__",
    "cli.py",
    "main.py",
    # Target packages
    "core",
    "services",
    "commands",
    "ui",
}

# Legacy modules that exist during refactoring
# Each should have a plan to migrate into core/, services/, commands/, or ui/
# Remove items from this set as they are refactored
ALLOWED_LEGACY = {
    # Domain packages (candidates for services/ or core/)
    "audit",
    "docker",
    "doctor",
    "evaluation",
    "marketplace",
    "models",
    "schemas",
    "stores",
    "templates",
    "utils",
    # Legacy standalone modules (candidates for refactoring)
    "auth.py",
    "claude_adapter.py",
    "cli_common.py",
    "cli_helpers.py",
    "config.py",
    "confirm.py",
    "console.py",
    "contexts.py",
    "deprecation.py",
    "deps.py",
    "git.py",
    "json_command.py",
    "json_output.py",
    "kinds.py",
    "org_templates.py",
    "output_mode.py",
    "panels.py",
    "platform.py",
    "profiles.py",
    "remote.py",
    "sessions.py",
    "setup.py",
    "source_resolver.py",
    "stats.py",
    "subprocess_utils.py",
    "teams.py",
    "theme.py",
    "update.py",
    "validate.py",
}

# System files to ignore
IGNORED = {
    ".DS_Store",
}

ALLOWED = ALLOWED_CORE | ALLOWED_LEGACY


class TestNoRootSprawl:
    """Prevent uncontrolled addition of top-level modules."""

    def test_no_unexpected_top_level_items(self) -> None:
        """All top-level items in src/scc_cli/ must be in the allowlist.

        If this test fails, you have added a new top-level module.
        Consider:
        1. Can this go inside core/, services/, commands/, or ui/?
        2. If it must be top-level, add it to ALLOWED_LEGACY with a comment
           explaining why and linking to a tracking issue for refactoring.
        """
        if not SRC.exists():
            # Skip if src/scc_cli doesn't exist yet
            return

        actual = {item.name for item in SRC.iterdir()}
        # Remove ignored items
        actual = actual - IGNORED

        unexpected = actual - ALLOWED

        if unexpected:
            msg_lines = [
                "Unexpected top-level items found in src/scc_cli/:",
                "",
            ]
            for item in sorted(unexpected):
                item_path = SRC / item
                item_type = "package" if item_path.is_dir() else "module"
                msg_lines.append(f"  - {item} ({item_type})")

            msg_lines.extend(
                [
                    "",
                    "To fix this:",
                    "  1. Move the module into core/, services/, commands/, or ui/",
                    "  2. If it must be top-level temporarily, add to ALLOWED_LEGACY",
                    "     in tests/test_no_root_sprawl.py with a comment explaining why",
                    "",
                    "Target architecture:",
                    "  core/     - domain models, validation, pure transforms",
                    "  services/ - use-case orchestration",
                    "  commands/ - CLI wiring",
                    "  ui/       - presentation",
                ]
            )

            raise AssertionError(chr(10).join(msg_lines))

    def test_allowed_items_still_exist(self) -> None:
        """Verify that items in ALLOWED actually exist.

        This ensures we clean up ALLOWED when modules are removed or refactored.
        Items in ALLOWED_CORE are optional (some may not exist yet).
        Items in ALLOWED_LEGACY must exist or be removed from the set.
        """
        if not SRC.exists():
            return

        actual = {item.name for item in SRC.iterdir()}

        # Legacy items should exist - if they don't, remove them from ALLOWED_LEGACY
        missing_legacy = ALLOWED_LEGACY - actual

        if missing_legacy:
            msg_lines = [
                "Items in ALLOWED_LEGACY no longer exist in src/scc_cli/:",
                "",
            ]
            for item in sorted(missing_legacy):
                msg_lines.append(f"  - {item}")

            msg_lines.extend(
                [
                    "",
                    "Please remove these from ALLOWED_LEGACY in tests/test_no_root_sprawl.py",
                    "This keeps the allowlist accurate and tracks refactoring progress.",
                ]
            )

            raise AssertionError(chr(10).join(msg_lines))

    def test_sprawl_metric(self) -> None:
        """Track the number of legacy top-level items.

        This test documents the current sprawl level and encourages reduction.
        It's informational - it will always pass but prints the metric.
        """
        if not SRC.exists():
            return

        actual = {item.name for item in SRC.iterdir()} - IGNORED
        legacy_count = len(actual & ALLOWED_LEGACY)
        core_count = len(actual & ALLOWED_CORE)
        total = len(actual)

        # This is informational - test always passes
        # The metric shows progress toward target architecture
        print("")
        print(f"  Root sprawl metric: {legacy_count} legacy items out of {total} total")
        print(f"  Core structure items: {core_count}")
        print("  Target: reduce legacy items to 0")
