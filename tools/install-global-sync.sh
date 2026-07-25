#!/bin/bash
# install-global-sync.sh — 이 기기에 "전역" 동기화 훅을 설치한다.
# 한 번만 실행하면 이 기기의 모든 git 프로젝트가 자동으로:
#   - 세션 시작 시 최신 pull (fast-forward·클린 트리 한정)
#   - 턴 종료 시 변경사항 커밋·푸시
# → 프로젝트마다 따로 세팅할 필요 없음. 그냥 "알아서" 된다.
#
# 사용법(각 PC에서 딱 한 번):
#   bash tools/install-global-sync.sh
#
# 되돌리기: ~/.claude/settings.json 에서 두 훅 항목을 지우면 됨.
set -euo pipefail

GLOBAL_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOOKS_DIR="$GLOBAL_DIR/hooks"
SETTINGS="$GLOBAL_DIR/settings.json"
mkdir -p "$HOOKS_DIR"

echo "▶ 전역 설치 위치: $GLOBAL_DIR"

# ── 1) Stop 훅: 자동 커밋·푸시 ─────────────────────────────────────────────
cat > "$HOOKS_DIR/auto-commit-push.sh" << 'HOOK'
#!/bin/bash
# 전역 Stop 훅: 어느 프로젝트든 턴이 끝나면 변경사항을 커밋·푸시.
# git repo가 아니거나 origin remote가 없으면 조용히 넘어감(멱등, 무해).
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0
[ -z "$(git status --porcelain)" ] && exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
[ -z "$branch" ] && { echo '{"systemMessage": "auto-sync skipped: detached HEAD"}'; exit 0; }
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
# 전역 SessionStart 훅: 어느 프로젝트든 세션 시작 시 최신 pull.
# fast-forward 전용 + 클린 트리 한정이라 미커밋 작업을 절대 덮어쓰지 않음.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
[ -z "$branch" ] && exit 0
[ -n "$(git status --porcelain)" ] && { echo '{"systemMessage": "sync-pull skipped: uncommitted local changes"}'; exit 0; }
if git pull --ff-only -q origin "$branch" 2>/dev/null; then
  echo "{\"systemMessage\": \"pulled latest from origin/$branch\"}"
fi
exit 0
HOOK
chmod +x "$HOOKS_DIR/session-sync-pull.sh"

# ── 3) 전역 settings.json 에 등록(있으면 병합, 없으면 생성) ──────────────────
PULL_CMD="$HOOKS_DIR/session-sync-pull.sh"
PUSH_CMD="$HOOKS_DIR/auto-commit-push.sh"

if [ ! -f "$SETTINGS" ]; then
  cat > "$SETTINGS" << JSON
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
  echo "▶ 전역 settings.json 새로 생성"
elif command -v jq >/dev/null 2>&1; then
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
  echo "▶ 전역 settings.json 병합(기존 설정 보존)"
else
  echo "⚠ jq 가 없어 기존 전역 settings.json 을 자동 병합하지 못했습니다. 수동으로 두 훅을 추가하세요."
  echo "   SessionStart → $PULL_CMD"
  echo "   Stop         → $PUSH_CMD"
fi

echo
echo "✅ 설치 완료. 이제 이 기기의 모든 git 프로젝트는 세팅 없이 자동 동기화됩니다."
echo "   (조건: 그 프로젝트가 git repo이고 GitHub origin remote가 연결돼 있을 것)"
