# TradingDesk 🧭

AI 에이전트 3명이 협업하는 미니 주식 리서치 데스크. **페이퍼 트레이딩 전용**(실제 돈 안 나감).

## 쓰는 법
이 폴더에서 Claude Code를 열고:

    /desk 삼성전자      # 한국 종목
    /desk NVDA          # 미국 종목

그러면 순서대로:
1. 🔍 리서처가 웹에서 뉴스·공시·업황을 모아 `research.md`에 정리
2. 📊 분석가가 그걸 읽고 판단해 `analysis.md`에 정리
3. 🧭 매니저가 종합해 매수/보유/매도 초안(`order-ticket.md`)을 만들고 **승인을 요청**
4. 내가 "승인"하면 `portfolio.md`와 `audit-log.md`에 기록, "거절"하면 거절로 남김

## 결과는 어디에?
`workspace/<티커-종목명>/<날짜>/` 폴더 안에 마크다운으로 쌓입니다.
- `portfolio.md` : 내 페이퍼 포지션 장부
- `audit-log.md` : 모든 결정 이력

## 에이전트가 뭘 하는지 궁금하면
`.claude/agents/` 안의 `researcher.md`, `analyst.md`, `manager.md`를 열어보세요.
각 에이전트가 받는 지시가 그대로 적혀 있습니다.

## 원칙
- 승인 없이는 포지션에 안 들어감
- 모든 리서치는 출처를 남김
- `audit-log.md`는 덧붙이기만
