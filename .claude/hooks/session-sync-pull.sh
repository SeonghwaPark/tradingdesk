#!/bin/bash
# SessionStart hook: pull the latest so a session opened on one device picks up
# work pushed from another. Fast-forward only, and only when the tree is clean,
# so it never clobbers uncommitted local work.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
[ -z "$branch" ] && exit 0

# Never touch a dirty tree — let the user resolve uncommitted work first.
if [ -n "$(git status --porcelain)" ]; then
  echo '{"systemMessage": "sync-pull skipped: uncommitted local changes present"}'
  exit 0
fi

if git pull --ff-only -q origin "$branch" 2>/dev/null; then
  echo "{\"systemMessage\": \"pulled latest from origin/$branch\"}"
else
  echo "{\"systemMessage\": \"sync-pull: could not fast-forward origin/$branch (nothing new, or needs a manual merge)\"}"
fi
exit 0
