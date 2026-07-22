# quote-bot — 텔레그램 종목조회 봇 📊

fisher_stock_bot 에게 종목을 보내면 **데이터 팩트 카드**를 회신한다.
AI 판단 없이 **실측 데이터만** (무료). tradingdesk 도구(ta_snapshot·dart·yfinance) 재활용.

## 보내는 법 (텔레그램에서)
```
005930        삼성전자        NVDA        /quote 000660
```
→ 현재가 · 시총 · 선행PER · **DART 확정실적** · 애널 목표주가 · 기술신호(이평선/RSI/MACD) 카드.

## 설정 (GitHub Secrets)
tradingdesk 저장소 → Settings → Secrets and variables → Actions:
- `TELEGRAM_BOT_TOKEN` = **fisher_stock_bot** 토큰 (night-brief와 같은 봇)
- `TELEGRAM_CHAT_ID` = 내 chat_id (내 메시지에만 응답)
- `DART_API_KEY` = OpenDART 키 (한글명 인식·확정실적용, 없어도 나머지는 동작)

> ⚠️ night-brief도 fisher_stock_bot을 쓰지만 **push(발송)만** 하고 getUpdates는 안 부르므로,
> 이 봇이 유일한 명령 수신자다(충돌 없음).

## 동작·한계
- GitHub Actions 크론(기본 10분)이 getUpdates로 밀린 명령을 처리 → **응답까지 최대 크론주기 지연**(즉답 아님).
- **Actions 분(minutes) 주의**: private 저장소는 무료 2000분/월. 10분 크론이면 초과 가능 →
  - **public 저장소로 두면 Actions 무료 무제한**(가장 간단), 또는
  - cron을 `*/30`으로 늘리거나, 로컬에서 `python bot/quote_bot.py`를 주기 실행.
- 투자자별 수급(외국인/기관/개인)은 이 환경에서 KRX 피드 미개방 → 카드에 미포함.

## 로컬 테스트
```
$env:DART_API_KEY = [Environment]::GetEnvironmentVariable('DART_API_KEY','User')
.venv/Scripts/python.exe bot/quote_bot.py   # 한 번 폴링 후 종료
```

⚠️ 데이터 스냅샷(참고용)이며 투자 조언이 아님.
