"""Contract tests: standalone safety evaluator vs DefaultSafetyEngine.

Feeds identical command/policy pairs to both the host CLI's
DefaultSafetyEngine and the standalone scc_safety_eval engine,
asserting identical verdicts (allowed, matched_rule, command_family).
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Make the standalone package importable ─────────────────────────────────
_wrappers_dir = str(Path(__file__).resolve().parent.parent / "images" / "scc-base" / "wrappers")
if _wrappers_dir not in sys.path:
    sys.path.insert(0, _wrappers_dir)

from scc_safety_eval.contracts import SafetyPolicy as StandalonePolicy  # noqa: E402
from scc_safety_eval.engine import DefaultSafetyEngine as StandaloneEngine  # noqa: E402

from scc_cli.core.contracts import SafetyPolicy as HostPolicy  # noqa: E402
from scc_cli.core.safety_engine import DefaultSafetyEngine as HostEngine  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_policies(
    action: str = "block",
    rules: dict | None = None,
) -> tuple:
    """Build matching host and standalone policies from the same data."""
    r = rules or {}
    return HostPolicy(action=action, rules=r), StandalonePolicy(action=action, rules=r)


def _assert_verdicts_match(command: str, host_policy, standalone_policy) -> None:
    """Evaluate a command with both engines and assert field-level equality."""
    host_verdict = HostEngine().evaluate(command, host_policy)
    standalone_verdict = StandaloneEngine().evaluate(command, standalone_policy)

    assert host_verdict.allowed == standalone_verdict.allowed, (
        f"allowed mismatch for {command!r}: "
        f"host={host_verdict.allowed}, standalone={standalone_verdict.allowed}"
    )
    assert host_verdict.matched_rule == standalone_verdict.matched_rule, (
        f"matched_rule mismatch for {command!r}: "
        f"host={host_verdict.matched_rule}, standalone={standalone_verdict.matched_rule}"
    )
    assert host_verdict.command_family == standalone_verdict.command_family, (
        f"command_family mismatch for {command!r}: "
        f"host={host_verdict.command_family}, standalone={standalone_verdict.command_family}"
    )


# ── Contract tests ─────────────────────────────────────────────────────────

class TestSafetyEvalContract:
    """Verdict equivalence between host and standalone engines."""

    def test_force_push_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push --force origin main", hp, sp)

    def test_force_push_f_flag(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push -f", hp, sp)

    def test_force_refspec(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push origin +main", hp, sp)

    def test_push_mirror_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push --mirror", hp, sp)

    def test_network_tool_curl_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("curl https://example.com", hp, sp)

    def test_network_tool_wget_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("wget https://example.com/file.tar.gz", hp, sp)

    def test_network_tool_ssh_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("ssh user@host", hp, sp)

    def test_network_tool_rsync_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("rsync -avz src/ host:/dst/", hp, sp)

    def test_safe_command_allowed(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git status", hp, sp)

    def test_safe_git_push_allowed(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push origin main", hp, sp)

    def test_ls_allowed(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("ls -la", hp, sp)

    def test_warn_mode(self) -> None:
        hp, sp = _make_policies(action="warn")
        _assert_verdicts_match("git push --force origin main", hp, sp)

    def test_allow_policy_bypass(self) -> None:
        hp, sp = _make_policies(action="allow")
        _assert_verdicts_match("git push --force origin main", hp, sp)

    def test_disabled_rule(self) -> None:
        hp, sp = _make_policies(rules={"block_force_push": False})
        _assert_verdicts_match("git push --force origin main", hp, sp)

    def test_nested_bash_c(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("bash -c 'git push --force'", hp, sp)

    def test_empty_command(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("", hp, sp)

    def test_whitespace_command(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("   ", hp, sp)

    def test_reset_hard_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git reset --hard HEAD~1", hp, sp)

    def test_branch_force_delete_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git branch -D feature", hp, sp)

    def test_stash_drop_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git stash drop", hp, sp)

    def test_clean_force_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git clean -fd", hp, sp)

    def test_checkout_path_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git checkout -- file.txt", hp, sp)

    def test_restore_worktree_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git restore file.txt", hp, sp)

    def test_filter_branch_blocked(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git filter-branch --all", hp, sp)

    def test_force_with_lease_allowed(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("git push --force-with-lease origin main", hp, sp)

    def test_sudo_wrapped_force_push(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("sudo git push --force", hp, sp)

    def test_disabled_network_rule_still_blocks(self) -> None:
        """Network tool rules don't have per-tool policy keys, so disabling
        a git rule should not affect network tool blocking."""
        hp, sp = _make_policies(rules={"block_force_push": False})
        _assert_verdicts_match("curl https://example.com", hp, sp)

    def test_pipe_chain_with_blocked_command(self) -> None:
        hp, sp = _make_policies()
        _assert_verdicts_match("echo ok && git push --force", hp, sp)
