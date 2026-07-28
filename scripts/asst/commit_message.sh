#!/bin/bash
# commit_message.sh - Wrapper for commit_message.py
# Generates AI commit messages using GitHub Models (free tier)
#
# Usage:
#   ./commit_message.sh -f diff_file.tmp
#   ./commit_message.sh -p "diff content"
#   cat diff.txt | ./commit_message.sh
#
# Environment:
#   GITHUB_TOKEN - Required (GitHub PAT or Actions token)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/commit_message.py" "$@"
