#!/bin/bash
# Stop hook: when Claude finishes a turn, commit any changes and push them,
# so work done on one device syncs to GitHub and can be pulled from another.
# Idempotent — a no-op when there is nothing to commit.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Only act inside a git repo.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Nothing changed → stay silent.
if [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

# Need a real branch to push to (skip detached HEAD).
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [ -z "$branch" ]; then
  echo '{"systemMessage": "auto-sync skipped: detached HEAD (no branch to push)"}'
  exit 0
fi

git add -A
# .gitignore already excludes .venv, caches and per-run research output.
git commit -q -m "chore: auto-sync $(date '+%Y-%m-%d %H:%M:%S %Z')" || exit 0

# Push, with a few retries for transient network hiccups.
for i in 1 2 3; do
  if git push -q origin "HEAD:$branch" 2>/dev/null; then
    echo "{\"systemMessage\": \"auto-synced to origin/$branch\"}"
    exit 0
  fi
  sleep $((i * 2))
done

echo "{\"systemMessage\": \"auto-sync: committed locally on $branch but push failed (will retry next turn)\"}"
exit 0
