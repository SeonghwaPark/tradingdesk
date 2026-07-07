# TradingDesk 🧭

AI 에이전트가 협업하는 미니 주식 리서치 데스크 + 주린이 학습 시스템. **페이퍼 트레이딩 전용**(실제 돈 안 나감).

## 쓰는 법
이 폴더에서 Claude Code를 열고:

    /desk 삼성전자      # 한국 종목
    /desk NVDA          # 미국 종목
    /learn RSI          # 개념 하나 배우기 (아무때나)

`/desk`를 실행하면 순서대로:
1. 🔍 리서처가 웹에서 뉴스·공시·업황을 모아 `research.md`에 정리
2. 📈 기술분석가가 실제 시세(yfinance)로 이평선·RSI·MACD·차트를 계산해 `technical.md`에 정리
3. 📊 분석가가 둘을 읽고 판단해 `analysis.md`에 정리
4. 🧭 매니저가 종합해 "사/말아 + 매수 타점" 초안(`order-ticket.md`)을 만들고 **승인을 요청**
5. 내가 "승인"하면 `portfolio.md`·`audit-log.md`에 기록, "거절"하면 거절로 남김
6. 🎓 멘토가 오늘 나온 개념 1개를 눈높이로 설명 + 퀴즈 → 학습 진도 기록

## 결과는 어디에?
`workspace/<티커-종목명>/<날짜>/`에 마크다운으로 쌓입니다.
- `portfolio.md` : 내 페이퍼 포지션 장부
- `audit-log.md` : 모든 결정 이력
- `_learning/profile.md` : 내 학습 진도(배운 개념·다음에 배울 것)

## 다른 PC에서 이어서 하기 (동기화)
```
git clone https://github.com/SeonghwaPark/tradingdesk.git
cd tradingdesk
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # 시세도구 라이브러리
```
이후 평소처럼 `git pull` / `git push`로 공유. (`.venv`는 각 PC에서 위 명령으로 새로 만듦)

## 에이전트가 뭘 하는지 궁금하면
`.claude/agents/`의 `researcher.md`·`technical-analyst.md`·`analyst.md`·`manager.md`·`mentor.md`를 열어보세요. 각 에이전트가 받는 지시가 그대로 적혀 있습니다.

## 문서
- `docs/기술적분석-입문.md` : 주린이용 용어 사전
- `docs/비전-고도화.md` : 9-에이전트 + 학습레이어 로드맵

## 원칙
- 승인 없이는 포지션에 안 들어감
- 모든 리서치는 출처를 남김 (웹 정량수치는 신뢰도 주의 — 실제 시세는 기술분석 도구가 담당)
- `audit-log.md`는 덧붙이기만
- 페이퍼 트레이딩·학습 목적, 실거래 아님
