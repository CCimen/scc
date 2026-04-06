"""Tests for git command analysis rules with typed SafetyVerdict returns."""

from __future__ import annotations

from scc_cli.core.enums import CommandFamily
from scc_cli.core.git_safety_rules import (
    analyze_branch,
    analyze_checkout,
    analyze_clean,
    analyze_filter_branch,
    analyze_gc,
    analyze_git,
    analyze_push,
    analyze_reflog,
    analyze_reset,
    analyze_restore,
    analyze_stash,
    has_force_flag,
    has_force_refspec,
    has_force_with_lease,
    normalize_git_tokens,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helper function tests (unchanged types — bool / tuple)
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeGitTokens:
    """Tests for normalize_git_tokens function."""

    def test_empty_tokens(self) -> None:
        assert normalize_git_tokens([]) == ("", [])

    def test_not_git_command(self) -> None:
        assert normalize_git_tokens(["python", "script.py"]) == ("", [])

    def test_simple_git_command(self) -> None:
        result = normalize_git_tokens(["git", "push", "origin"])
        assert result == ("push", ["origin"])

    def test_full_path_git(self) -> None:
        result = normalize_git_tokens(["/usr/bin/git", "push"])
        assert result == ("push", [])

    def test_git_with_c_dir_flag(self) -> None:
        result = normalize_git_tokens(["git", "-C", "/path", "push", "origin"])
        assert result == ("push", ["origin"])

    def test_git_with_c_flag(self) -> None:
        result = normalize_git_tokens(["git", "-c", "user.name=foo", "push"])
        assert result == ("push", [])

    def test_git_with_git_dir(self) -> None:
        result = normalize_git_tokens(["git", "--git-dir=/path/.git", "status"])
        assert result == ("status", [])

    def test_git_with_work_tree(self) -> None:
        result = normalize_git_tokens(["git", "--work-tree=/path", "diff"])
        assert result == ("diff", [])

    def test_git_with_multiple_global_options(self) -> None:
        result = normalize_git_tokens(["git", "-C", "/path", "--git-dir=.git", "push", "-f"])
        assert result == ("push", ["-f"])


class TestHasForceFlag:
    """Tests for has_force_flag function."""

    def test_empty_args(self) -> None:
        assert has_force_flag([]) is False

    def test_no_force(self) -> None:
        assert has_force_flag(["origin", "main"]) is False

    def test_short_force(self) -> None:
        assert has_force_flag(["-f"]) is True

    def test_long_force(self) -> None:
        assert has_force_flag(["--force"]) is True

    def test_combined_flags_with_f(self) -> None:
        assert has_force_flag(["-xfd"]) is True
        assert has_force_flag(["-fd"]) is True

    def test_long_flag_no_force(self) -> None:
        assert has_force_flag(["--follow"]) is False

    def test_force_in_middle(self) -> None:
        assert has_force_flag(["origin", "-f", "main"]) is True


class TestHasForceRefspec:
    """Tests for has_force_refspec function."""

    def test_empty_args(self) -> None:
        assert has_force_refspec([]) is False

    def test_no_plus(self) -> None:
        assert has_force_refspec(["origin", "main"]) is False

    def test_plus_at_start(self) -> None:
        assert has_force_refspec(["+main"]) is True
        assert has_force_refspec(["origin", "+main"]) is True

    def test_plus_in_refspec(self) -> None:
        assert has_force_refspec(["+main:main"]) is True

    def test_colon_plus_pattern(self) -> None:
        assert has_force_refspec(["HEAD:+main"]) is True

    def test_double_plus_not_force(self) -> None:
        assert has_force_refspec(["++something"]) is False

    def test_flags_skipped(self) -> None:
        assert has_force_refspec(["-u", "origin", "+main"]) is True


class TestHasForceWithLease:
    """Tests for has_force_with_lease function."""

    def test_empty_args(self) -> None:
        assert has_force_with_lease([]) is False

    def test_no_force_with_lease(self) -> None:
        assert has_force_with_lease(["--force"]) is False

    def test_force_with_lease(self) -> None:
        assert has_force_with_lease(["--force-with-lease"]) is True

    def test_force_with_lease_value(self) -> None:
        assert has_force_with_lease(["--force-with-lease=main"]) is True


# ─────────────────────────────────────────────────────────────────────────────
# Analyzer tests — now assert typed SafetyVerdict fields
# ─────────────────────────────────────────────────────────────────────────────


class TestAnalyzePush:
    """Tests for analyze_push function."""

    def test_normal_push(self) -> None:
        assert analyze_push(["origin", "main"]) is None

    def test_force_flag(self) -> None:
        result = analyze_push(["--force"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.force_push"
        assert result.command_family == CommandFamily.DESTRUCTIVE_GIT

        result2 = analyze_push(["-f"])
        assert result2 is not None
        assert result2.allowed is False

    def test_force_refspec(self) -> None:
        result = analyze_push(["+main"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.force_push"

        result2 = analyze_push(["origin", "+main:main"])
        assert result2 is not None
        assert result2.allowed is False

    def test_force_with_lease_allowed(self) -> None:
        assert analyze_push(["--force-with-lease"]) is None
        assert analyze_push(["--force-with-lease", "origin", "main"]) is None

    def test_combined_flags(self) -> None:
        result = analyze_push(["-fu"])
        assert result is not None
        assert result.allowed is False

    def test_mirror_blocked(self) -> None:
        result = analyze_push(["--mirror"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.push_mirror"
        assert "mirror" in result.reason.lower()


class TestAnalyzeReset:
    """Tests for analyze_reset function."""

    def test_soft_reset(self) -> None:
        assert analyze_reset(["--soft", "HEAD~1"]) is None

    def test_mixed_reset(self) -> None:
        assert analyze_reset(["--mixed", "HEAD~1"]) is None
        assert analyze_reset(["HEAD~1"]) is None  # Default is mixed

    def test_hard_reset(self) -> None:
        result = analyze_reset(["--hard"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.reset_hard"
        assert result.command_family == CommandFamily.DESTRUCTIVE_GIT

        result2 = analyze_reset(["--hard", "HEAD~1"])
        assert result2 is not None
        assert result2.allowed is False


class TestAnalyzeBranch:
    """Tests for analyze_branch function."""

    def test_list_branches(self) -> None:
        assert analyze_branch([]) is None
        assert analyze_branch(["-a"]) is None

    def test_safe_delete(self) -> None:
        assert analyze_branch(["-d", "feature"]) is None

    def test_force_delete_uppercase_d(self) -> None:
        result = analyze_branch(["-D", "feature"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.branch_force_delete"

    def test_delete_with_force(self) -> None:
        result = analyze_branch(["--delete", "--force", "feature"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.branch_force_delete"


class TestAnalyzeStash:
    """Tests for analyze_stash function."""

    def test_stash_push(self) -> None:
        assert analyze_stash([]) is None
        assert analyze_stash(["push"]) is None

    def test_stash_pop(self) -> None:
        assert analyze_stash(["pop"]) is None

    def test_stash_apply(self) -> None:
        assert analyze_stash(["apply"]) is None

    def test_stash_list(self) -> None:
        assert analyze_stash(["list"]) is None

    def test_stash_drop(self) -> None:
        result = analyze_stash(["drop"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.stash_drop"

        result2 = analyze_stash(["drop", "stash@{0}"])
        assert result2 is not None
        assert result2.allowed is False

    def test_stash_clear(self) -> None:
        result = analyze_stash(["clear"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.stash_clear"


class TestAnalyzeClean:
    """Tests for analyze_clean function."""

    def test_dry_run(self) -> None:
        assert analyze_clean(["-n"]) is None
        assert analyze_clean(["--dry-run"]) is None
        assert analyze_clean(["-n", "-f"]) is None  # Dry run takes precedence

    def test_force_clean(self) -> None:
        result = analyze_clean(["-f"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.clean_force"

        result2 = analyze_clean(["--force"])
        assert result2 is not None
        assert result2.allowed is False

    def test_force_directory(self) -> None:
        result = analyze_clean(["-fd"])
        assert result is not None
        assert result.allowed is False

        result2 = analyze_clean(["-df"])
        assert result2 is not None
        assert result2.allowed is False

    def test_force_ignored(self) -> None:
        result = analyze_clean(["-xfd"])
        assert result is not None
        assert result.allowed is False


class TestAnalyzeCheckout:
    """Tests for analyze_checkout function."""

    def test_switch_branch(self) -> None:
        assert analyze_checkout(["main"]) is None
        assert analyze_checkout(["-b", "feature"]) is None

    def test_checkout_path(self) -> None:
        result = analyze_checkout(["--", "file.py"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.checkout_path"

    def test_checkout_head_path(self) -> None:
        result = analyze_checkout(["HEAD", "--", "file.py"])
        assert result is not None
        assert result.allowed is False

    def test_checkout_branch_path(self) -> None:
        result = analyze_checkout(["main", "--", "file.py"])
        assert result is not None
        assert result.allowed is False

    def test_separator_without_path(self) -> None:
        assert analyze_checkout(["--"]) is None


class TestAnalyzeRestore:
    """Tests for analyze_restore function."""

    def test_empty_args(self) -> None:
        assert analyze_restore([]) is None

    def test_staged_only(self) -> None:
        assert analyze_restore(["--staged", "file.py"]) is None
        assert analyze_restore(["-S", "file.py"]) is None

    def test_worktree_restore(self) -> None:
        result = analyze_restore(["file.py"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.restore_worktree"

        result2 = analyze_restore(["--worktree", "file.py"])
        assert result2 is not None
        assert result2.allowed is False

        result3 = analyze_restore(["-W", "file.py"])
        assert result3 is not None
        assert result3.allowed is False

    def test_both_staged_and_worktree(self) -> None:
        result = analyze_restore(["--staged", "--worktree", "file.py"])
        assert result is not None
        assert result.allowed is False

        result2 = analyze_restore(["-S", "-W", "file.py"])
        assert result2 is not None
        assert result2.allowed is False


class TestAnalyzeReflog:
    """Tests for analyze_reflog function."""

    def test_reflog_show(self) -> None:
        assert analyze_reflog([]) is None
        assert analyze_reflog(["show"]) is None

    def test_reflog_expire_safe(self) -> None:
        assert analyze_reflog(["expire"]) is None
        assert analyze_reflog(["expire", "--all"]) is None

    def test_reflog_expire_unreachable_now_combined(self) -> None:
        result = analyze_reflog(["expire", "--expire-unreachable=now"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.reflog_expire"

        result2 = analyze_reflog(["expire", "--all", "--expire-unreachable=now"])
        assert result2 is not None
        assert result2.allowed is False

    def test_reflog_expire_unreachable_now_separate(self) -> None:
        result = analyze_reflog(["expire", "--expire-unreachable", "now"])
        assert result is not None
        assert result.allowed is False

        result2 = analyze_reflog(["expire", "--expire-unreachable", "now", "--all"])
        assert result2 is not None
        assert result2.allowed is False

    def test_reflog_expire_other_values(self) -> None:
        assert analyze_reflog(["expire", "--expire-unreachable=2.weeks.ago"]) is None
        assert analyze_reflog(["expire", "--expire-unreachable", "30.days.ago"]) is None


class TestAnalyzeGc:
    """Tests for analyze_gc function."""

    def test_gc_default(self) -> None:
        assert analyze_gc([]) is None

    def test_gc_aggressive(self) -> None:
        assert analyze_gc(["--aggressive"]) is None

    def test_gc_prune_now_combined(self) -> None:
        result = analyze_gc(["--prune=now"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.gc_prune"

        result2 = analyze_gc(["--aggressive", "--prune=now"])
        assert result2 is not None
        assert result2.allowed is False

    def test_gc_prune_now_separate(self) -> None:
        result = analyze_gc(["--prune", "now"])
        assert result is not None
        assert result.allowed is False

        result2 = analyze_gc(["--prune", "now", "--aggressive"])
        assert result2 is not None
        assert result2.allowed is False

    def test_gc_prune_other_values(self) -> None:
        assert analyze_gc(["--prune=2.weeks.ago"]) is None
        assert analyze_gc(["--prune", "30.days.ago"]) is None


class TestAnalyzeFilterBranch:
    """Tests for analyze_filter_branch function."""

    def test_filter_branch_always_blocked(self) -> None:
        result = analyze_filter_branch([])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "git.filter_branch"
        assert result.command_family == CommandFamily.DESTRUCTIVE_GIT

        result2 = analyze_filter_branch(["--tree-filter", "rm -f passwords.txt"])
        assert result2 is not None
        assert result2.allowed is False

        result3 = analyze_filter_branch(["--env-filter", "..."])
        assert result3 is not None
        assert result3.allowed is False

    def test_filter_branch_message_content(self) -> None:
        result = analyze_filter_branch([])
        assert result is not None
        assert "filter-branch" in result.reason.lower()
        assert "filter-repo" in result.reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — analyze_git entry point
# ─────────────────────────────────────────────────────────────────────────────


class TestAnalyzeGit:
    """Integration tests for analyze_git function."""

    def test_non_git_command(self) -> None:
        assert analyze_git(["python", "script.py"]) is None

    def test_git_without_subcommand(self) -> None:
        assert analyze_git(["git"]) is None

    def test_force_push(self) -> None:
        result = analyze_git(["git", "push", "--force"])
        assert result is not None
        assert result.allowed is False
        assert result.command_family == CommandFamily.DESTRUCTIVE_GIT

        assert analyze_git(["git", "push", "-f"]) is not None
        assert analyze_git(["git", "push", "origin", "+main"]) is not None

    def test_force_with_lease(self) -> None:
        assert analyze_git(["git", "push", "--force-with-lease"]) is None

    def test_reset_hard(self) -> None:
        assert analyze_git(["git", "reset", "--hard"]) is not None

    def test_reset_soft(self) -> None:
        assert analyze_git(["git", "reset", "--soft"]) is None

    def test_branch_force_delete(self) -> None:
        assert analyze_git(["git", "branch", "-D", "feature"]) is not None

    def test_branch_safe_delete(self) -> None:
        assert analyze_git(["git", "branch", "-d", "feature"]) is None

    def test_stash_drop(self) -> None:
        assert analyze_git(["git", "stash", "drop"]) is not None

    def test_stash_pop(self) -> None:
        assert analyze_git(["git", "stash", "pop"]) is None

    def test_clean_force(self) -> None:
        assert analyze_git(["git", "clean", "-f"]) is not None
        assert analyze_git(["git", "clean", "-xfd"]) is not None

    def test_clean_dry_run(self) -> None:
        assert analyze_git(["git", "clean", "-n"]) is None

    def test_checkout_path(self) -> None:
        assert analyze_git(["git", "checkout", "--", "file.py"]) is not None

    def test_checkout_branch(self) -> None:
        assert analyze_git(["git", "checkout", "main"]) is None

    def test_restore_worktree(self) -> None:
        assert analyze_git(["git", "restore", "file.py"]) is not None

    def test_restore_staged(self) -> None:
        assert analyze_git(["git", "restore", "--staged", "file.py"]) is None

    def test_full_path_git(self) -> None:
        assert analyze_git(["/usr/bin/git", "push", "--force"]) is not None

    def test_git_with_global_options(self) -> None:
        assert analyze_git(["git", "-C", "/path", "push", "-f"]) is not None

    def test_unknown_subcommand(self) -> None:
        assert analyze_git(["git", "status"]) is None
        assert analyze_git(["git", "log"]) is None
        assert analyze_git(["git", "diff"]) is None

    # Catastrophic commands (v0.2.0)

    def test_push_mirror(self) -> None:
        assert analyze_git(["git", "push", "--mirror"]) is not None

    def test_reflog_expire_now(self) -> None:
        assert analyze_git(["git", "reflog", "expire", "--expire-unreachable=now"]) is not None
        assert analyze_git(["git", "reflog", "expire", "--expire-unreachable", "now"]) is not None

    def test_reflog_show_allowed(self) -> None:
        assert analyze_git(["git", "reflog"]) is None
        assert analyze_git(["git", "reflog", "show"]) is None

    def test_gc_prune_now(self) -> None:
        assert analyze_git(["git", "gc", "--prune=now"]) is not None
        assert analyze_git(["git", "gc", "--prune", "now"]) is not None

    def test_gc_allowed(self) -> None:
        assert analyze_git(["git", "gc"]) is None
        assert analyze_git(["git", "gc", "--aggressive"]) is None

    def test_filter_branch_blocked(self) -> None:
        assert analyze_git(["git", "filter-branch"]) is not None
        assert analyze_git(["git", "filter-branch", "--tree-filter", "..."]) is not None

    # DX polish (v0.2.0) - help/version bypass

    def test_git_help_allowed(self) -> None:
        assert analyze_git(["git", "help"]) is None
        assert analyze_git(["git", "help", "push"]) is None
        assert analyze_git(["git", "help", "reset"]) is None

    def test_help_flag_bypasses_block(self) -> None:
        assert analyze_git(["git", "push", "--force", "--help"]) is None
        assert analyze_git(["git", "reset", "--hard", "--help"]) is None
        assert analyze_git(["git", "clean", "-f", "--help"]) is None
        assert analyze_git(["git", "filter-branch", "--help"]) is None

    def test_h_flag_bypasses_block(self) -> None:
        assert analyze_git(["git", "push", "-f", "-h"]) is None
        assert analyze_git(["git", "reset", "--hard", "-h"]) is None
        assert analyze_git(["git", "branch", "-D", "-h"]) is None

    def test_version_flag_bypasses_block(self) -> None:
        assert analyze_git(["git", "push", "--force", "--version"]) is None
        assert analyze_git(["git", "gc", "--prune=now", "--version"]) is None

    # ─── Negative / edge-case tests (from task plan) ────────────────────

    def test_bare_git_no_subcommand(self) -> None:
        """Bare `git` with no subcommand → allowed (None)."""
        assert analyze_git(["git"]) is None

    def test_unknown_git_subcommands_pass_through(self) -> None:
        """Unknown subcommands don't trigger blocks."""
        assert analyze_git(["git", "bisect"]) is None
        assert analyze_git(["git", "worktree", "add", "foo"]) is None

    def test_empty_token_list(self) -> None:
        """Empty token list → allowed."""
        assert analyze_git([]) is None

    def test_single_empty_string_token(self) -> None:
        """Single empty string → not git, allowed."""
        assert analyze_git([""]) is None

    def test_tokens_with_only_flags(self) -> None:
        """Tokens that are just flags (no git binary) → not git."""
        assert analyze_git(["--force", "-f"]) is None
