#!/usr/bin/env bash
#
# SCC CLI Smoke Test Script
# ==========================
# Pre-release validation script that tests critical flows.
#
# Usage:
#   ./scripts/smoke_test.sh        # Run all tests
#   make smoke                     # If Makefile target exists
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
SKIPPED=0

# Test helper functions
pass() {
    echo -e "${GREEN}PASS${NC}: $1"
    ((PASSED++)) || true
}

fail() {
    echo -e "${RED}FAIL${NC}: $1"
    ((FAILED++)) || true
}

skip() {
    echo -e "${YELLOW}SKIP${NC}: $1"
    ((SKIPPED++)) || true
}

info() {
    echo -e "${BLUE}INFO${NC}: $1"
}

# Create temp directory for tests
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "=================================================="
echo "  SCC CLI Smoke Tests"
echo "=================================================="
echo ""

# ------------------------------------------------------------------------------
# Test 1: worktree switch in non-git dir produces no stdout
# ------------------------------------------------------------------------------
info "Test 1: worktree switch stdout purity (non-git dir)"

# Capture stdout and exit code (stderr goes to /dev/null)
STDOUT=$(scc worktree switch -w "$TMPDIR" 2>/dev/null) || RESULT=$?
RESULT=${RESULT:-0}

if [[ -z "$STDOUT" ]]; then
    if [[ $RESULT -ne 0 ]]; then
        pass "worktree switch in non-git dir: stdout empty, exit $RESULT"
    else
        fail "worktree switch in non-git dir: stdout empty but exit was 0"
    fi
else
    fail "worktree switch in non-git dir: stdout should be empty, got: '$STDOUT'"
fi

# ------------------------------------------------------------------------------
# Test 2: worktree switch error goes to stderr
# ------------------------------------------------------------------------------
info "Test 2: worktree switch error goes to stderr"

STDERR=$(scc worktree switch -w "$TMPDIR" 2>&1 >/dev/null || true)

if [[ "$STDERR" == *"Not a git repository"* ]]; then
    pass "worktree switch error appears in stderr"
else
    fail "worktree switch error missing from stderr: '$STDERR'"
fi

# ------------------------------------------------------------------------------
# Test 3: worktree list -v works in git repo
# ------------------------------------------------------------------------------
info "Test 3: worktree list -v works in git repo"

# Create a git repo
TESTREPO="$TMPDIR/testrepo"
mkdir -p "$TESTREPO"
git -C "$TESTREPO" init --quiet
git -C "$TESTREPO" config user.email "test@test.com"
git -C "$TESTREPO" config user.name "Test"
git -C "$TESTREPO" commit --allow-empty -m "Initial" --quiet

if scc worktree list -v "$TESTREPO" >/dev/null 2>&1; then
    pass "worktree list -v works in git repo"
else
    fail "worktree list -v failed"
fi

# ------------------------------------------------------------------------------
# Test 4: worktree list shows correct output
# ------------------------------------------------------------------------------
info "Test 4: worktree list shows worktree"

OUTPUT=$(scc worktree list "$TESTREPO" 2>&1)

if [[ -n "$OUTPUT" ]]; then
    pass "worktree list produces output"
else
    fail "worktree list produced no output"
fi

# ------------------------------------------------------------------------------
# Test 5: Exit code is correct for non-git dir
# ------------------------------------------------------------------------------
info "Test 5: Exit code is 4 (ToolError) for non-git dir"

scc worktree switch -w "$TMPDIR" >/dev/null 2>&1 || EXIT_CODE=$?

if [[ "${EXIT_CODE:-0}" -eq 4 ]]; then
    pass "worktree switch exit code is 4 (ToolError)"
else
    fail "worktree switch exit code was ${EXIT_CODE:-0}, expected 4"
fi

# ------------------------------------------------------------------------------
# Test 6: scc doctor works
# ------------------------------------------------------------------------------
info "Test 6: scc doctor runs successfully"

if scc doctor >/dev/null 2>&1; then
    pass "scc doctor runs without error"
else
    fail "scc doctor failed"
fi

# ------------------------------------------------------------------------------
# Test 7 (SKELETON): worktree enter opens subshell
# ------------------------------------------------------------------------------
info "Test 7: worktree enter command (TODO: depends on Phase 5)"
skip "worktree enter not yet implemented"

# ------------------------------------------------------------------------------
# Test 8 (SKELETON): Non-interactive mode fails fast
# ------------------------------------------------------------------------------
info "Test 8: Non-interactive mode fails fast (TODO: verify)"
# This is partially tested by the subprocess tests
skip "Non-interactive mode test needs manual verification"

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo ""
echo "=================================================="
echo "  Summary"
echo "=================================================="
echo -e "  ${GREEN}PASSED${NC}: $PASSED"
echo -e "  ${RED}FAILED${NC}: $FAILED"
echo -e "  ${YELLOW}SKIPPED${NC}: $SKIPPED"
echo "=================================================="

if [[ $FAILED -gt 0 ]]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
