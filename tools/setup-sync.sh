#!/bin/bash
# setup-sync.sh — 어느 프로젝트에서든 실행하면 "기기 간 자동 동기화" 훅을
# 그 프로젝트의 .claude/ 에 설치한다. repo에 커밋되므로 PC·웹·아이패드 모두 적용.
#
# 설치되는 것:
#   - SessionStart 훅(session-sync-pull.sh): 세션 시작 시 최신 pull(fast-forward, 클린 트리 한정)
#   - Stop 훅(auto-commit-push.sh): 턴이 끝나면 변경사항 자동 커밋·푸시
#
# 사용법:
#   cd <내-프로젝트>
#   bash /경로/setup-sync.sh        # 현재 폴더에 설치
#   bash /경로/setup-sync.sh <경로>  # 특정 폴더에 설치
#
# 재실행해도 안전(멱등). 기존 .claude/settings.json 이 있으면 병합한다.
set -euo pipefail

PROJECT_DIR="${1:-$PWD}"
cd "$PROJECT_DIR"
PROJECT_DIR="$PWD"   # 절대경로로 정규화

HOOKS_DIR=".claude/hooks"
SETTINGS=".claude/settings.json"
mkdir -p "$HOOKS_DIR"

echo "▶ 설치 위치: $PROJECT_DIR/.claude"

# ── 1) Stop 훅: 자동 커밋·푸시 ─────────────────────────────────────────────
cat > "$HOOKS_DIR/auto-commit-push.sh" << 'HOOK'
#!/bin/bash
# Stop 훅: 턴이 끝나면 변경사항을 커밋·푸시해 GitHub로 동기화한다.
# 변경 없으면 조용히 아무것도 안 함(멱등).
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
[ -z "$(git status --porcelain)" ] && exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [ -z "$branch" ]; then
  echo '{"systemMessage": "auto-sync skipped: detached HEAD (no branch to push)"}'; exit 0
fi
git add -A
git commit -q -m "chore: auto-sync $(date '+%Y-%m-%d %H:%M:%S %Z')" || exit 0
for i in 1 2 3; do
  if git push -q origin "HEAD:$branch" 2>/dev/null; then
    echo "{\"systemMessage\": \"auto-synced to origin/$branch\"}"; exit 0
  fi
  sleep $((i * 2))
done
echo "{\"systemMessage\": \"auto-sync: committed locally on $branch but push failed (will retry next turn)\"}"
exit 0
HOOK
chmod +x "$HOOKS_DIR/auto-commit-push.sh"

# ── 2) SessionStart 훅: 자동 pull ─────────────────────────────────────────
cat > "$HOOKS_DIR/session-sync-pull.sh" << 'HOOK'
#!/bin/bash
# SessionStart 훅: 세션 시작 시 최신을 pull 한다.
# fast-forward 전용 + 클린 트리 한정이라 로컬 미커밋 작업을 절대 덮어쓰지 않음.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
[ -z "$branch" ] && exit 0
if [ -n "$(git status --porcelain)" ]; then
  echo '{"systemMessage": "sync-pull skipped: uncommitted local changes present"}'; exit 0
fi
if git pull --ff-only -q origin "$branch" 2>/dev/null; then
  echo "{\"systemMessage\": \"pulled latest from origin/$branch\"}"
else
  echo "{\"systemMessage\": \"sync-pull: could not fast-forward origin/$branch (nothing new, or needs a manual merge)\"}"
fi
exit 0
HOOK
chmod +x "$HOOKS_DIR/session-sync-pull.sh"

# ── 3) settings.json 에 훅 등록(있으면 병합, 없으면 생성) ────────────────────
PULL_CMD='$CLAUDE_PROJECT_DIR/.claude/hooks/session-sync-pull.sh'
PUSH_CMD='$CLAUDE_PROJECT_DIR/.claude/hooks/auto-commit-push.sh'

fresh_settings() {
  cat << JSON
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "$PULL_CMD" } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "$PUSH_CMD" } ] }
    ]
  }
}
JSON
}

if [ ! -f "$SETTINGS" ]; then
  fresh_settings > "$SETTINGS"
  echo "▶ settings.json 새로 생성"
elif command -v jq >/dev/null 2>&1; then
  # 기존 설정 보존 + 우리 훅이 없을 때만 추가(멱등)
  tmp="$(mktemp)"
  jq --arg pull "$PULL_CMD" --arg push "$PUSH_CMD" '
    def ensure($event; $cmd):
      ( [ .hooks[$event][]?.hooks[]?.command ] ) as $existing
      | if ($existing | index($cmd)) then .
        else .hooks[$event] = ((.hooks[$event] // []) + [ { "hooks": [ { "type": "command", "command": $cmd } ] } ])
        end;
    .hooks = (.hooks // {})
    | ensure("SessionStart"; $pull)
    | ensure("Stop"; $push)
  ' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
  echo "▶ settings.json 병합(기존 설정 보존)"
else
  echo "⚠ jq 가 없어 기존 settings.json 을 자동 병합하지 못했습니다."
  echo "  아래 두 훅을 hooks 에 직접 추가하세요:"
  echo "   SessionStart → $PULL_CMD"
  echo "   Stop         → $PUSH_CMD"
fi

# ── 4) 사전 조건 점검(git repo + remote) ──────────────────────────────────
echo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❗ 이 폴더는 git 저장소가 아닙니다. 공유하려면:"
  echo "   git init && git add -A && git commit -m 'init'"
  echo "   그리고 GitHub에 repo를 만들고: git remote add origin <URL>"
elif ! git remote get-url origin >/dev/null 2>&1; then
  echo "❗ git remote(origin)가 없습니다. 공유하려면 GitHub repo를 연결하세요:"
  echo "   git remote add origin <URL>"
else
  echo "✅ git repo + origin 확인됨 → 커밋만 하면 동기화 준비 완료:"
  echo "   git add .claude && git commit -m 'chore: add cross-device sync hooks' && git push"
fi
echo
echo "완료. 로컬(앱/CLI)에서는 처음 열 때 '훅 신뢰?' 를 한 번 승인하면 됩니다."
