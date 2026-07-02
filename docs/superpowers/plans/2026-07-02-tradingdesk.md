# TradingDesk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code 네이티브(서브에이전트 + 스킬 + 마크다운 파일)로, 3명의 AI 에이전트가 협업해 주식을 리서치하고 사람 승인 후 페이퍼 포지션에 기록하는 미니 리서치 데스크를 만든다.

**Architecture:** 리서처·분석가는 자율 **서브에이전트**(`.claude/agents/`)로 웹 검색 후 마크다운 파일을 남기고 복귀한다. 매니저는 **메인 세션 오케스트레이터**(`.claude/skills/desk/`)로서 두 서브에이전트를 순서대로 호출하고, 결과를 종합해 주문 티켓 초안을 만든 뒤 **사람 승인 게이트에서 멈춘다**. 모든 상태는 `workspace/` 아래 읽을 수 있는 마크다운으로 쌓인다.

**Tech Stack:** Claude Code subagents(`.claude/agents/*.md`), Claude Code skill(`.claude/skills/desk/SKILL.md`), WebSearch/WebFetch, 순수 마크다운 파일 메모리. (Python/Django/DB/API 없음)

---

## 검증 철학

이 프로젝트에는 실행 코드가 없다(프롬프트 마크다운뿐). 따라서 단위 테스트 대신:
- **파일 작성 태스크**: 파일 생성 후 존재/구조를 눈으로 확인.
- **최종 통합 태스크(Task 6)**: 실제 `/desk <종목>`을 돌려 파일 산출·승인·거절 흐름을 실측한다. 이것이 진짜 "테스트"다.

## File Structure

| 파일 | 책임 |
|------|------|
| `.gitignore` | git 추적 제외 규칙 |
| `README.md` | 비개발자용 사용법 |
| `workspace/portfolio.md` | 승인된 페이퍼 포지션 장부(초기 빈 테이블) |
| `workspace/audit-log.md` | append-only 결정 이력(초기 헤더만) |
| `.claude/agents/researcher.md` | 🔍 리서처 서브에이전트 프롬프트 |
| `.claude/agents/analyst.md` | 📊 분석가 서브에이전트 프롬프트 |
| `.claude/agents/manager.md` | 🧭 매니저 역할 문서(학습용, 오케스트레이션은 스킬이 실행) |
| `.claude/skills/desk/SKILL.md` | `/desk` 명령 = 매니저 오케스트레이션 플레이북 |

---

### Task 1: 프로젝트 뼈대 + 워크스페이스 스텁 + README

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `workspace/portfolio.md`
- Create: `workspace/audit-log.md`

- [ ] **Step 1: `.gitignore` 작성**

```gitignore
# OS
Thumbs.db
.DS_Store

# 개별 리서치 산출물은 커밋하지 않음(개인 판단 기록). 장부/로그만 추적.
workspace/*/
```

- [ ] **Step 2: `workspace/portfolio.md` 작성 (빈 장부)**

```markdown
# 포트폴리오 (페이퍼)

> 승인된 주문만 여기에 기록됩니다. 실거래 아님.

| 티커 | 종목명 | 방향 | 비중 | 진입일 | 근거 티켓ID |
|------|--------|------|------|--------|-------------|
```

- [ ] **Step 3: `workspace/audit-log.md` 작성 (헤더만)**

```markdown
# 감사 로그 (append-only)

> 모든 승인/거절 결정이 시간순으로 덧붙여집니다. 줄을 지우거나 수정하지 마세요.

| 타임스탬프 | 티켓ID | 상태변경 | 사용자결정 | 사유 |
|-----------|--------|----------|-----------|------|
```

- [ ] **Step 4: `README.md` 작성 (비개발자용)**

```markdown
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
```

- [ ] **Step 5: 확인**

Run: `ls -R workspace && head -3 workspace/portfolio.md`
Expected: `portfolio.md`, `audit-log.md`가 존재하고 헤더가 보임.

- [ ] **Step 6: 커밋**

```bash
git add .gitignore README.md workspace/portfolio.md workspace/audit-log.md
git commit -m "chore: 프로젝트 뼈대와 워크스페이스 스텁 추가"
```

---

### Task 2: 리서처 서브에이전트

**Files:**
- Create: `.claude/agents/researcher.md`

- [ ] **Step 1: `researcher.md` 작성**

파일 전체 내용:

```markdown
---
name: researcher
description: 주식 리서치 담당. 웹 검색으로 특정 종목의 뉴스·공시·실적·현재가 수준·업황·경쟁구도·리스크를 수집하고 출처와 함께 research.md에 정리한다. 매니저가 리서치 단계에서 호출한다.
tools: WebSearch, WebFetch, Read, Write, Glob
---

너는 투자 리서치 데스크의 🔍 **리서처**다. 판단(매수/매도 의견)은 하지 않는다. 오직 **사실 수집**만 한다.

## 입력
매니저가 다음을 준다:
- 종목명/티커
- 정규화된 식별자(예: `005930-삼성전자`)
- 저장 경로(예: `workspace/005930-삼성전자/2026-07-02/research.md`)

## 할 일
1. WebSearch/WebFetch로 아래를 조사한다(한국 종목은 한국어 소스, 미국 종목은 영어 소스 우선):
   - 최근 뉴스 (최근 것 위주, 날짜 명시)
   - 최신 실적/공시 요약
   - 현재 주가 수준과 밸류에이션 참고치(가능한 범위에서)
   - 소속 섹터 업황(반도체면 메모리/파운드리/장비 사이클 등)
   - 주요 경쟁사 및 상대적 위치
   - 확인된 리스크
2. **모든 주장에는 출처 링크를 붙인다.** 확실치 않으면 "불확실"이라 명시한다. 지어내지 않는다.
3. 아래 형식으로 지정된 경로에 Write 한다.

## 출력 형식 (research.md)
```
# 리서치: <종목명> (<티커>)
- 조사일: <날짜>
- 조사자: researcher

## 개요
## 최근 뉴스 (출처 링크 포함)
## 실적 / 공시 요약
## 현재 주가 수준 / 밸류에이션 참고치
## 섹터 업황 및 경쟁 구도
## 확인된 리스크
## 출처 목록
```

## 복귀
파일을 저장한 뒤, 매니저에게 3~5줄 요약과 저장 경로를 보고한다.
```

- [ ] **Step 2: 확인**

Run: `head -6 .claude/agents/researcher.md`
Expected: 프론트매터에 `name: researcher`와 `tools:` 줄이 보임.

- [ ] **Step 3: 커밋**

```bash
git add .claude/agents/researcher.md
git commit -m "feat: 리서처 서브에이전트 추가"
```

---

### Task 3: 분석가 서브에이전트

**Files:**
- Create: `.claude/agents/analyst.md`

- [ ] **Step 1: `analyst.md` 작성**

파일 전체 내용:

```markdown
---
name: analyst
description: 주식 분석 담당. 리서처가 만든 research.md를 읽고 강점·약점·촉매·리스크를 평가해 방향성 의견(긍정/중립/부정)과 확신도를 analysis.md에 정리한다. 매니저가 분석 단계에서 호출한다.
tools: Read, Write, Glob, WebSearch
---

너는 투자 리서치 데스크의 📊 **분석가**다. 새 데이터를 대량 수집하지 않는다. 리서처의 자료를 **해석하고 판단**한다.

## 입력
매니저가 다음을 준다:
- 근거 파일 경로(`research.md`)
- 저장 경로(`analysis.md`)

## 할 일
1. `research.md`를 Read로 읽는다.
2. 다음을 평가한다:
   - 강점 / 약점
   - 촉매(Catalysts) — 주가를 움직일 수 있는 이벤트
   - 리스크 평가 — 발생 가능성과 영향
   - 방향성 의견: **긍정 / 중립 / 부정** 중 하나 + 확신도(상/중/하)
3. 판단 근거는 반드시 `research.md`의 내용을 인용한다. 자료에 없는 새 사실이 꼭 필요하면 WebSearch로 최소한만 보완하고 출처를 밝힌다.
4. 아래 형식으로 지정 경로에 Write 한다.

## 출력 형식 (analysis.md)
```
# 분석: <종목명> (<티커>)
- 분석일: <날짜>
- 분석가: analyst
- 근거 파일: research.md

## 강점
## 약점
## 촉매(Catalysts)
## 리스크 평가
## 방향성 의견: 긍정 / 중립 / 부정 (확신도: 상/중/하)
### 근거 요약
```

## 복귀
저장 후, 매니저에게 방향성 의견 한 줄 + 저장 경로를 보고한다.
```

- [ ] **Step 2: 확인**

Run: `head -6 .claude/agents/analyst.md`
Expected: 프론트매터에 `name: analyst`가 보임.

- [ ] **Step 3: 커밋**

```bash
git add .claude/agents/analyst.md
git commit -m "feat: 분석가 서브에이전트 추가"
```

---

### Task 4: 매니저 역할 문서 (학습용)

**Files:**
- Create: `.claude/agents/manager.md`

> 참고: 매니저 로직의 실제 실행은 Task 5의 `/desk` 스킬이 담당한다(승인 게이트가 사람과의 대화를 요구하기 때문). 이 파일은 매니저 역할을 사람이 읽고 이해하도록 남기는 **문서**이자 스킬이 참조하는 단일 출처다.

- [ ] **Step 1: `manager.md` 작성**

파일 전체 내용:

```markdown
---
name: manager
description: (문서) 리서치 데스크의 매니저 역할 정의. 실제 오케스트레이션은 /desk 스킬이 이 문서를 따라 메인 세션에서 실행한다. 서브에이전트로 직접 호출하지 않는다.
---

# 🧭 매니저 역할

매니저는 데스크의 지휘자다. 리서처·분석가를 순서대로 부리고, 결과를 종합해 주문 초안을 만들고, **사람의 승인을 받는다.**

## 책임
1. **접수(intake)**: 사용자가 준 종목명/티커를 정규화한다.
   - 한국: `<6자리코드>-<종목명>` (예: `005930-삼성전자`)
   - 미국: `<티커>-<회사명>` (예: `NVDA-NVIDIA`)
   - 코드/티커가 불확실하면 WebSearch로 확인한다.
2. **디스패치**: 리서처 → (완료 후) 분석가 순으로 호출한다. 각 단계는 파일로 넘어간다.
3. **종합**: `analysis.md`를 읽고 `recommendation.md`와 `order-ticket.md`(상태 DRAFT)를 만든다.
4. **승인 게이트**: 사용자에게 요약과 함께 "승인/거절"을 묻고 **멈춘다**. 스스로 승인하지 않는다.
5. **정산**: 승인 시 티켓 상태를 APPROVED로 바꾸고 `portfolio.md`·`audit-log.md`를 갱신한다. 거절 시 REJECTED로 바꾸고 `audit-log.md`에만 남긴다.

## 원칙
- 승인 없이는 절대 `portfolio.md`를 건드리지 않는다.
- `audit-log.md`는 기존 줄을 수정/삭제하지 않고 아래에 덧붙이기만 한다.
- 페이퍼 트레이딩 전용. 실거래·자금이동은 이 시스템에 존재하지 않는다.

## 산출 형식
recommendation.md, order-ticket.md 형식은 /desk 스킬(SKILL.md)에 정의된 것을 따른다.
```

- [ ] **Step 2: 확인**

Run: `head -4 .claude/agents/manager.md`
Expected: `name: manager` 프론트매터가 보임.

- [ ] **Step 3: 커밋**

```bash
git add .claude/agents/manager.md
git commit -m "docs: 매니저 역할 문서 추가"
```

---

### Task 5: `/desk` 오케스트레이션 스킬

**Files:**
- Create: `.claude/skills/desk/SKILL.md`

- [ ] **Step 1: `SKILL.md` 작성**

파일 전체 내용:

````markdown
---
name: desk
description: 주식 리서치 데스크 실행. `/desk <종목명 또는 티커>` 형태로 호출하면 매니저로서 리서처→분석가 서브에이전트를 순서대로 돌리고, 결과를 종합해 주문 티켓 초안을 만든 뒤 사용자 승인을 받아 페이퍼 포트폴리오에 기록한다. 한국/미국 주식 지원.
---

# /desk — 리서치 데스크 실행

너는 이제 🧭 **매니저**다. `.claude/agents/manager.md`의 역할 정의를 따른다. 아래 순서를 **정확히** 지켜라.

## 0. 입력 파싱
`$ARGUMENTS`에서 종목명/티커를 읽는다. 비어 있으면 사용자에게 "어떤 종목을 리서치할까요?"라고 묻고 멈춘다.

## 1. 접수 (intake)
- 종목을 정규화한다. 한국: `<6자리>-<종목명>` (예: `005930-삼성전자`), 미국: `<티커>-<회사명>` (예: `NVDA-NVIDIA`).
- 코드/티커가 불확실하면 WebSearch로 1회 확인한다.
- 오늘 날짜(YYYY-MM-DD)를 구한다.
- 작업 폴더 경로를 정한다: `workspace/<식별자>/<날짜>/`

## 2. 리서처 디스패치
- Agent 툴로 `subagent_type: researcher`를 호출한다.
- 프롬프트에 반드시 포함: 종목명/티커, 정규화 식별자, 저장 경로 `workspace/<식별자>/<날짜>/research.md`.
- 서브에이전트가 복귀하면 파일이 실제로 생성됐는지 확인한다.

## 3. 분석가 디스패치
- Agent 툴로 `subagent_type: analyst`를 호출한다.
- 프롬프트에 반드시 포함: 근거 파일 `workspace/<식별자>/<날짜>/research.md`, 저장 경로 `.../analysis.md`.
- 복귀 후 `analysis.md` 생성 확인.

## 4. 종합 → 초안 작성
- `analysis.md`를 Read로 읽는다.
- `workspace/<식별자>/<날짜>/recommendation.md`를 아래 형식으로 Write:
```
# 최종 의견: <종목명> (<티커>)
- 작성일: <날짜> / 작성: manager
## 종합 판단
## 권고: 매수 / 보유 / 매도
## 근거 요약 (analysis.md 인용)
## 주의사항
```
- `workspace/<식별자>/<날짜>/order-ticket.md`를 아래 형식으로 Write (상태는 반드시 DRAFT):
```
# 주문 티켓: <종목명> (<티커>)
- 티켓ID: <YYYYMMDD>-<티커>-1
- 상태: DRAFT
- 방향: 매수 / 매도 / 없음
- 가상 비중: <예: 포트폴리오의 5%>
- 근거: <recommendation.md 요약 1~2줄>
- 생성: <날짜>
- 승인/거절: (미정)
```

## 5. 승인 게이트 — 여기서 반드시 멈춘다
사용자에게 다음을 제시한다:
- 권고(매수/보유/매도)와 핵심 근거 3줄
- 티켓ID와 방향/비중
- 산출 파일 경로들(클릭 가능한 마크다운 링크)
- 마지막에 **"이 초안을 승인할까요, 거절할까요? (승인 / 거절)"**

**스스로 승인하지 마라. 사용자의 명시적 응답을 기다린다.**

## 6. 정산
### 승인이면:
- `order-ticket.md`의 `상태: DRAFT` → `상태: APPROVED`, `승인/거절:` 줄에 `<날짜>, 사용자 승인` 기록.
- `workspace/portfolio.md` 테이블에 한 줄 추가: `| 티커 | 종목명 | 방향 | 비중 | 진입일(오늘) | 티켓ID |`
- `workspace/audit-log.md`에 한 줄 **추가**: `| <타임스탬프> | <티켓ID> | DRAFT→APPROVED | 승인 | <한줄사유> |`
- 사용자에게 "포트폴리오에 기록 완료"를 알린다.

### 거절이면:
- `order-ticket.md`의 상태를 `REJECTED`, `승인/거절:` 줄에 `<날짜>, 사용자 거절` 기록.
- `workspace/audit-log.md`에 한 줄 **추가**: `| <타임스탬프> | <티켓ID> | DRAFT→REJECTED | 거절 | <한줄사유> |`
- `portfolio.md`는 **건드리지 않는다.**
- 사용자에게 "거절 처리됨(포지션 미기록)"을 알린다.

## 안전 규칙
- 실거래/자금이동 없음. 페이퍼 전용.
- 승인 없이 portfolio.md 수정 금지.
- audit-log.md는 덧붙이기만.
````

- [ ] **Step 2: 확인**

Run: `head -4 .claude/skills/desk/SKILL.md`
Expected: `name: desk` 프론트매터가 보임.

- [ ] **Step 3: 커밋**

```bash
git add .claude/skills/desk/SKILL.md
git commit -m "feat: /desk 오케스트레이션 스킬 추가"
```

---

### Task 6: 엔드투엔드 검증 (실제 실행)

> 이 태스크는 파일이 아니라 **실제 동작**을 검증한다. 사람(fisher)과 함께 진행한다.

**Files:** (실행 결과로 생성됨)
- `workspace/<식별자>/<날짜>/research.md`, `analysis.md`, `recommendation.md`, `order-ticket.md`
- `workspace/portfolio.md`, `workspace/audit-log.md` (갱신)

- [ ] **Step 1: 한국 종목 승인 경로**

Run: `/desk 삼성전자`
Expected:
- `workspace/005930-삼성전자/<오늘>/` 아래 4개 파일 생성
- 흐름이 승인 게이트에서 멈추고 "승인/거절"을 물음
- 사용자가 "승인" → `order-ticket.md` 상태 APPROVED, `portfolio.md`에 삼성전자 한 줄 추가, `audit-log.md`에 DRAFT→APPROVED 한 줄 추가

- [ ] **Step 2: 승인 결과 확인**

Run: `cat workspace/portfolio.md && echo '---' && cat workspace/audit-log.md`
Expected: portfolio에 삼성전자 행, audit-log에 APPROVED 행이 보임.

- [ ] **Step 3: 미국 종목 거절 경로**

Run: `/desk NVDA`
Expected:
- `workspace/NVDA-NVIDIA/<오늘>/` 아래 4개 파일 생성
- 승인 게이트에서 사용자가 "거절" → `order-ticket.md` 상태 REJECTED, `audit-log.md`에 DRAFT→REJECTED 한 줄 추가, **`portfolio.md`는 불변**

- [ ] **Step 4: 거절 결과 확인**

Run: `cat workspace/NVDA-NVIDIA/*/order-ticket.md | grep 상태 && echo '---' && cat workspace/portfolio.md`
Expected: 티켓 상태 REJECTED, portfolio에는 NVDA 행이 **없음**.

- [ ] **Step 5: 커밋 (장부/로그만 — 개별 리서치는 .gitignore로 제외됨)**

```bash
git add workspace/portfolio.md workspace/audit-log.md
git commit -m "test: 엔드투엔드 검증 (삼성전자 승인 / NVDA 거절)"
```

---

## Self-Review (작성자 체크)

**Spec coverage:**
- 4대 개념(에이전트 팀=Task2~4, handoff=파일 경로 전달 Task5, 파일 메모리=Task1/5, 승인 게이트=Task5 Step5~6) ✅
- 3개 역할 ✅ / 웹검색 데이터원 ✅ / 한·미 종목 ✅(Task6) / 페이퍼·감사로그·append-only ✅
- 성공 기준 1~6 → Task6 Step1~4가 모두 커버 ✅

**Placeholder scan:** 각 파일의 전체 내용을 명시함. TBD/TODO 없음. ✅

**Type/naming consistency:** 식별자 규칙(`<코드>-<종목명>`), 티켓ID(`<YYYYMMDD>-<티커>-1`), 파일명(research/analysis/recommendation/order-ticket), 상태값(DRAFT/APPROVED/REJECTED)이 Task 전반에 일관됨. ✅
