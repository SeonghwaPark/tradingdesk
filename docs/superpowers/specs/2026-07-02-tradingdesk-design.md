# TradingDesk 설계 문서

- **작성일**: 2026-07-02
- **작성자**: fisher (with Claude Code)
- **영감**: [monarchjuno/tradingcodex](https://github.com/monarchjuno/tradingcodex) (Apache-2.0)

---

## 1. 목적

두 가지를 동시에 만족한다:

1. **이해** — "AI 에이전트로 돌아가는 시스템이 실제로 어떻게 작동하는가"를 비개발자도 눈으로 볼 수 있게 만든다.
2. **실사용** — 한국/미국 주식(특히 반도체 분야) 리서치에 실제로 써먹는다.

원본 TradingCodex는 Python + Django + MCP 기반의 큰 시스템이다. 이 프로젝트는 그 **핵심 개념 4가지**만 뽑아 **Claude Code 네이티브(서브에이전트 + 스킬 + 마크다운 파일)**로 가볍게 재현한다.

재현하는 핵심 개념 4가지:
1. **에이전트 팀** — 역할이 나뉜 여러 AI가 협업
2. **작업 넘기기(handoff)** — 한 역할의 결과물을 다음 역할이 이어받음
3. **파일 기반 메모리** — 결과가 DB가 아니라 읽을 수 있는 마크다운으로 쌓임
4. **승인 게이트** — 사람이 승인해야만 포지션에 기록됨 (페이퍼 트레이딩)

## 2. 비목표 (YAGNI)

이번 버전에서 **하지 않는** 것:

- Django 웹서버 / Django Admin / REST API (원본의 웹 배관 전부 제외)
- MCP 서버 구축
- 실제 브로커 연동 / 실거래 (페이퍼 트레이딩만)
- 실시간 정밀 시세 API (yfinance 등) — 데이터는 웹 검색으로만
- 원본의 9개 역할 전체 — 3개로 시작 (확장은 나중에)
- 인증, 다중 사용자, 배포

## 3. 데이터 출처

- 에이전트는 Claude Code의 **WebSearch / WebFetch**로 뉴스·공시·시세·업황을 직접 찾는다.
- API 키·외부 설정 불필요 → 폴더 열면 바로 사용 가능.
- 한계: 실시간 정밀 시세는 약하다. 정성적 분석·업황·뉴스 중심으로 강하다.
- 대상 시장: 한국(KOSPI/KOSDAQ) + 미국. 초기 관심 섹터: 반도체.

## 4. 역할 (에이전트 3명)

| 역할 | 하는 일 | 입력 | 출력 |
|------|---------|------|------|
| 🔍 리서처 (researcher) | 웹 검색으로 사실 수집: 최근 뉴스, 공시/실적, 현재가 수준, 반도체 업황, 경쟁사 동향 | 종목명/티커 | `research.md` |
| 📊 분석가 (analyst) | 리서처 자료를 읽고 강점·약점·리스크·촉매를 평가, 방향성 의견 형성 | `research.md` | `analysis.md` |
| 🧭 매니저 (manager) | 전체 지휘. 분석가 의견을 종합해 매수/보유/매도 초안(order-ticket) 작성. 사람 승인 요청. 승인 시 장부·감사로그 갱신 | `analysis.md` | `recommendation.md`, `order-ticket.md`, (`portfolio.md`, `audit-log.md`) |

각 에이전트는 `.claude/agents/<role>.md`에 프롬프트(역할·책임·읽고 쓸 파일·출력 형식)로 정의된다. **비개발자도 이 파일을 열면 "이 에이전트가 무슨 지시를 받는지" 읽을 수 있다.** 이것이 학습 목표의 핵심.

## 5. 폴더 구조

```
C:\dev\tradingdesk\
├── workspace/
│   ├── <티커-종목명>/
│   │   └── <YYYY-MM-DD>/
│   │       ├── research.md        # 리서처 산출물
│   │       ├── analysis.md        # 분석가 산출물
│   │       ├── recommendation.md  # 매니저 최종 의견
│   │       └── order-ticket.md    # 주문 초안 (상태 필드 포함)
│   ├── portfolio.md               # 승인된 포지션 장부
│   └── audit-log.md               # append-only 결정 이력
├── .claude/
│   ├── agents/
│   │   ├── researcher.md
│   │   ├── analyst.md
│   │   └── manager.md
│   └── skills/
│       └── desk/
│           └── SKILL.md           # /desk 명령어 = 워크플로우 오케스트레이션
├── docs/superpowers/specs/        # 이 설계 문서
└── README.md                      # 사용법 (비개발자용)
```

## 6. 작동 흐름

진입점: 사용자가 `/desk 삼성전자` (또는 `/desk NVDA`) 입력.

```
1. 🧭 매니저    종목 식별(티커/종목명 정규화) → 오늘 날짜 폴더 생성 → 리서처 호출
        ↓
2. 🔍 리서처    WebSearch/WebFetch로 자료 수집 → research.md 저장
        ↓ (파일로 handoff)
3. 📊 분석가    research.md 읽기 → 평가 → analysis.md 저장
        ↓ (파일로 handoff)
4. 🧭 매니저    종합 → recommendation.md + order-ticket.md (상태: DRAFT) 작성
        ↓
5. ⏸️ 승인 게이트   사용자에게 요약 + "승인 / 거절?" 제시. 여기서 멈춤.
        ↓
6a. ✅ 승인 → order-ticket 상태 APPROVED → portfolio.md 갱신 + audit-log.md 추가
6b. ❌ 거절 → order-ticket 상태 REJECTED → audit-log.md 에 거절 기록
```

## 7. 파일 형식 (인터페이스)

각 파일은 잘 정의된 형식을 가져 다음 에이전트가 안정적으로 읽을 수 있게 한다.

### research.md
```markdown
# 리서치: <종목명> (<티커>)
- 조사일: <날짜>
- 조사자: researcher

## 개요
## 최근 뉴스 (출처 링크 포함)
## 실적 / 공시 요약
## 현재 주가 수준 / 밸류에이션 참고치
## 반도체 업황 및 경쟁 구도
## 확인된 리스크
## 출처 목록
```

### analysis.md
```markdown
# 분석: <종목명> (<티커>)
- 분석일: <날짜>
- 분석가: analyst
- 근거 파일: research.md

## 강점
## 약점
## 촉매(Catalysts)
## 리스크 평가
## 방향성 의견 (긍정 / 중립 / 부정) + 확신도
```

### recommendation.md
```markdown
# 최종 의견: <종목명> (<티커>)
- 작성일: <날짜> / 작성: manager
## 종합 판단
## 권고: 매수 / 보유 / 매도
## 근거 요약 (analysis.md 인용)
## 주의사항
```

### order-ticket.md
```markdown
# 주문 티켓: <종목명> (<티커>)
- 티켓ID: <YYYYMMDD-티커-N>
- 상태: DRAFT | APPROVED | REJECTED
- 방향: 매수 / 매도 / (없음)
- 가상 수량/비중: <예: 포트폴리오의 5%>
- 근거: <recommendation.md 요약>
- 생성: <날짜>
- 승인/거절: <날짜, 사용자>
```

### portfolio.md (승인 시 갱신)
```markdown
# 포트폴리오 (페이퍼)
| 티커 | 종목명 | 방향 | 비중 | 진입일 | 근거 티켓ID |
|------|--------|------|------|--------|-------------|
```

### audit-log.md (append-only)
```markdown
# 감사 로그
- <타임스탬프> | <티켓ID> | <상태변경> | <사용자결정> | <한줄사유>
```

## 8. 안전장치 / 원칙

- **승인 없이는 포지션 기록 없음.** 매니저는 5단계에서 반드시 멈춘다.
- **audit-log.md 는 덧붙이기만.** 결정 이력이 사라지지 않는다.
- **페이퍼 트레이딩 전용.** 실거래·실제 자금 이동 코드는 존재하지 않는다.
- **모든 리서치는 출처를 남긴다.** 나중에 "왜 이 판단?" 추적 가능.

## 9. 성공 기준 (검증 방법)

1. `C:\dev\tradingdesk`에서 Claude Code를 열고 `/desk 삼성전자` 실행 시, 4개 파일이 올바른 형식으로 workspace에 생성된다.
2. 흐름이 5단계에서 멈추고 사용자에게 승인을 요청한다.
3. "승인"하면 portfolio.md와 audit-log.md가 갱신된다.
4. "거절"하면 order-ticket 상태가 REJECTED가 되고 audit-log에 남으며 portfolio는 변하지 않는다.
5. 미국 종목(예: `/desk NVDA`)도 동일하게 작동한다.
6. 비개발자가 `.claude/agents/*.md`를 열어 각 에이전트의 역할을 읽고 이해할 수 있다.

## 10. 향후 확장 (이번 범위 아님)

- 역할 추가: 뉴스/매크로/밸류에이션/리스크 등 → 원본 9개 방향
- 여러 종목 비교, 포트폴리오 리밸런싱 뷰
- 간단한 웹 화면(읽기 전용)으로 workspace 시각화
- 실데이터 API 연동
```
