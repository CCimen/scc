"""Fail-closed policy loader for the standalone safety evaluator.

Reads safety policy from the path given by the SCC_POLICY_PATH
environment variable. Returns a fail-closed default (action='block',
no rules) when:
  - SCC_POLICY_PATH is unset or empty
  - The file does not exist
  - The file contains malformed JSON
"""

from __future__ import annotations

import json
import os
import sys

from .contracts import SafetyPolicy

_FAIL_CLOSED = SafetyPolicy(action="block", rules={})


def load_policy() -> SafetyPolicy:
    """Load safety policy from SCC_POLICY_PATH, fail-closed on any error."""
    path = os.environ.get("SCC_POLICY_PATH", "")
    if not path:
        return _FAIL_CLOSED

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"scc_safety_eval: policy load error: {exc}", file=sys.stderr)
        return _FAIL_CLOSED

    if not isinstance(data, dict):
        print("scc_safety_eval: policy file is not a JSON object", file=sys.stderr)
        return _FAIL_CLOSED

    return SafetyPolicy(
        action=data.get("action", "block"),
        rules=data.get("rules", {}),
        source=data.get("source", "org.security.safety_net"),
    )
