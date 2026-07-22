# -*- coding: utf-8 -*-
"""진단용(임시): 토큰 유효성 + chat_id 일치 여부만 안전하게 출력.
전체 토큰/chat_id는 로그에 찍지 않는다(저장소 public이므로)."""
import os
import requests

tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
cid = os.environ.get("TELEGRAM_CHAT_ID", "")

print("== Secrets 존재 여부 ==")
print("BOT_TOKEN set:", bool(tok), "| 길이:", len(tok))
print("CHAT_ID set:", bool(cid), "| 값(마스킹):",
      (cid[:2] + "***" + cid[-3:]) if len(cid) > 5 else f"'{cid}' (너무짧음/빔?)")

print("\n== 토큰 유효성 (getMe) ==")
try:
    j = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=15).json()
    print("ok:", j.get("ok"), "| 봇:", j.get("result", {}).get("username"),
          "" if j.get("ok") else f"| 오류: {j.get('description')}")
except Exception as e:
    print("ERR:", e)

print("\n== 받은 메시지 엿보기 (offset 안 건드림) ==")
try:
    j = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=15).json()
    ups = j.get("result", [])
    print("ok:", j.get("ok"), "| 대기 메시지 수:", len(ups))
    for u in ups[-6:]:
        m = u.get("message") or u.get("edited_message") or {}
        ch = str(m.get("chat", {}).get("id", ""))
        print(f"  update {u.get('update_id')}: 보낸chat 끝4자리={ch[-4:]} "
              f"| CHAT_ID와 일치? {ch == cid} | text={m.get('text')!r}")
    if not ups:
        print("  (대기 메시지 없음 — 방금 보낸 게 이미 소비됐거나, 아직 안 보냈거나)")
except Exception as e:
    print("ERR:", e)
