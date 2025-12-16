#!/bin/bash
# SCC Status Line for Claude Code
# Shows: Model | Git branch/worktree | Lines changed
#
# Install: scc statusline --install
# This script receives JSON from Claude Code via stdin

# Read JSON input from stdin
input=$(cat)

# Extract values using jq
MODEL=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
CURRENT_DIR=$(echo "$input" | jq -r '.workspace.current_dir // "."')
PROJECT_DIR=$(echo "$input" | jq -r '.workspace.project_dir // "."')
LINES_ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
LINES_REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')

# Colors
CYAN="\033[36m"
GREEN="\033[32m"
RED="\033[31m"
MAGENTA="\033[35m"
YELLOW="\033[33m"
WHITE="\033[1;37m"
DIM="\033[2m"
RESET="\033[0m"

# Git information
GIT_INFO=""
cd "$CURRENT_DIR" 2>/dev/null || cd "$PROJECT_DIR" 2>/dev/null

if git rev-parse --git-dir > /dev/null 2>&1; then
    # Get branch name
    BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -z "$BRANCH" ]; then
        # Detached HEAD - show short SHA
        BRANCH=$(git rev-parse --short HEAD 2>/dev/null || echo "detached")
    fi

    # Check if we're in a worktree
    GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)

    if [[ "$GIT_DIR" == *".git/worktrees/"* ]]; then
        # In a worktree - show ⎇ icon
        WORKTREE_NAME=$(basename "$(dirname "$GIT_DIR")" 2>/dev/null)
        GIT_INFO="${MAGENTA}⎇ ${WORKTREE_NAME}${RESET}:${CYAN}${BRANCH}${RESET}"
    else
        # Regular repo - show 🌿 icon
        GIT_INFO="${CYAN}🌿 ${BRANCH}${RESET}"
    fi

    # Check for uncommitted changes
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        GIT_INFO="${GIT_INFO}${YELLOW}*${RESET}"
    fi
fi

# Lines changed (only show if any changes made)
LINES_INFO=""
if [ "$LINES_ADDED" -gt 0 ] || [ "$LINES_REMOVED" -gt 0 ]; then
    LINES_INFO=" ${DIM}|${RESET} ${GREEN}+${LINES_ADDED}${RESET} ${RED}-${LINES_REMOVED}${RESET}"
fi

# Build the status line
# Format: [Model] 🌿 branch* | +156 -23
OUTPUT="${WHITE}[${MODEL}]${RESET}"

if [ -n "$GIT_INFO" ]; then
    OUTPUT="${OUTPUT} ${GIT_INFO}"
fi

OUTPUT="${OUTPUT}${LINES_INFO}"

# Output (printf handles escape codes)
printf "%b\n" "$OUTPUT"
