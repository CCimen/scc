"""Default safety engine orchestrating shell tokenization, git rules, and network tool rules.

Implements the SafetyEngine protocol from ports/safety_engine.py.
All evaluation is provider-neutral: both Claude and Codex adapters
consume this engine downstream.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from scc_cli.core.contracts import SafetyPolicy, SafetyVerdict
from scc_cli.core.git_safety_rules import analyze_git
from scc_cli.core.network_tool_rules import analyze_network_tool
from scc_cli.core.shell_tokenizer import extract_all_commands

# Maps matched_rule identifiers to SafetyPolicy.rules keys.
# fail-closed: if the key is missing from policy.rules, the rule is enabled.
_MATCHED_RULE_TO_POLICY_KEY: dict[str, str] = {
    "git.force_push": "block_force_push",
    "git.push_mirror": "block_push_mirror",
    "git.reset_hard": "block_reset_hard",
    "git.branch_force_delete": "block_branch_force_delete",
    "git.stash_drop": "block_stash_drop",
    "git.stash_clear": "block_stash_clear",
    "git.clean_force": "block_clean_force",
    "git.checkout_path": "block_checkout_path",
    "git.restore_worktree": "block_restore_worktree",
    "git.reflog_expire": "block_reflog_expire",
    "git.gc_prune": "block_gc_prune",
    "git.filter_branch": "block_filter_branch",
}


def _matched_rule_to_policy_key(matched_rule: str) -> str | None:
    """Map a matched_rule identifier to its policy key.

    Args:
        matched_rule: Rule identifier like 'git.force_push' or 'network.curl'.

    Returns:
        Policy key like 'block_force_push', or None if no mapping exists.
    """
    return _MATCHED_RULE_TO_POLICY_KEY.get(matched_rule)


class DefaultSafetyEngine:
    """Provider-neutral command safety evaluator.

    Orchestrates shell tokenization, git rules, and network tool rules
    into a single evaluate() call that satisfies the SafetyEngine protocol.
    """

    def evaluate(self, command: str, policy: SafetyPolicy) -> SafetyVerdict:
        """Evaluate a command string against the given safety policy.

        Args:
            command: Shell command string to evaluate.
            policy: Safety policy containing rules and baseline action.

        Returns:
            A typed verdict indicating whether the command is allowed.
        """
        # Empty/whitespace commands are always safe
        if not command or not command.strip():
            return SafetyVerdict(allowed=True, reason="Empty command")

        # Policy action "allow" bypasses all rules
        if policy.action == "allow":
            return SafetyVerdict(allowed=True, reason="Policy action is allow")

        # Tokenize and check all sub-commands (handles pipes, &&, bash -c nesting)
        for tokens in extract_all_commands(command):
            if not tokens:
                continue

            # Check git rules: is the first token (path-stripped) 'git'?
            first_bare = PurePosixPath(tokens[0]).name
            if first_bare == "git":
                verdict = analyze_git(tokens)
                if verdict is not None and not verdict.allowed:
                    return self._apply_policy(verdict, policy)

            # Check network tool rules
            net_verdict = analyze_network_tool(tokens)
            if net_verdict is not None and not net_verdict.allowed:
                return self._apply_policy(net_verdict, policy)

        return SafetyVerdict(allowed=True, reason="No safety rules matched")

    def _apply_policy(
        self, verdict: SafetyVerdict, policy: SafetyPolicy
    ) -> SafetyVerdict:
        """Apply policy overrides to a block verdict.

        Checks if the rule is disabled in policy.rules. If the policy
        action is 'warn', converts block to allowed with WARNING prefix.
        Missing keys default to True (fail-closed: rule enabled).
        """
        # Check if this specific rule is disabled in the policy
        if verdict.matched_rule is not None:
            policy_key = _matched_rule_to_policy_key(verdict.matched_rule)
            if policy_key is not None:
                rule_enabled = policy.rules.get(policy_key, True)
                if not rule_enabled:
                    return SafetyVerdict(
                        allowed=True,
                        reason=f"Rule {verdict.matched_rule} disabled by policy",
                        matched_rule=verdict.matched_rule,
                        command_family=verdict.command_family,
                    )

        # Warn mode: allow but prefix reason
        if policy.action == "warn":
            return SafetyVerdict(
                allowed=True,
                reason=f"WARNING: {verdict.reason}",
                matched_rule=verdict.matched_rule,
                command_family=verdict.command_family,
            )

        # Default: return the block verdict as-is
        return verdict
