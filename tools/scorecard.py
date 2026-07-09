"""
scorecard.py — 예측 성적표 자동 채점 도구 (TradingDesk)

데스크가 매일 낸 "사요/마요" 콜을, 기준일 이후 실제 주가로 자동 채점한다.
채점 시점: 다음날(D+1) · 1주 · 1개월 · 3개월.
채점 기준: 절대 방향 (매수=올랐으면 적중 / 거절·관망=안 올랐으면 적중).

동작:
  1) workspace/scorecard.md 안의 '콜 원장'(LEDGER 블록)을 읽는다.
  2) 각 콜의 티커를 yfinance로 받아, 기준가 대비 각 시점 수익률을 계산한다.
  3) 시점이 아직 안 지난 콜은 '대기(D-n)'로 표기한다.
  4) 적중/빗나감을 판정하고, 적중률·평균수익률을 집계해
     scorecard.md의 채점 결과 블록을 새로 쓴다. (원장은 건드리지 않는다)

사용법:
    python tools/scorecard.py                # workspace/scorecard.md 채점
    python tools/scorecard.py --file <경로>  # 다른 성적표 파일 지정

콜 원장(LEDGER) 한 줄 형식:
    | 티켓ID | 티커 | 종목명 | 방향 | 기준일 | 기준가 |
      - 티커: yfinance 티커 (예: 005930.KS, 000660.KS, NVDA)
      - 방향: 매수 / 거절 / 관망
      - 기준일: YYYY-MM-DD
      - 기준가: 비워두면 기준일 종가를 자동으로 채워 계산한다.
"""

import sys
import argparse
from datetime import date, datetime, timedelta

# 윈도우 콘솔(cp949)에서도 한글 출력이 깨지지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import yfinance as yf

# 채점 시점 (라벨, 기준일로부터 경과일)
HORIZONS = [("다음날", 1), ("1주", 7), ("1개월", 30), ("3개월", 90)]

# 중립 밴드(%). ±이 값 안이면 '보합'으로 보고 승패에 넣지 않는다(잡음 방지).
NEUTRAL_BAND = 2.0

LEDGER_BEGIN = "<!-- LEDGER:BEGIN -->"
LEDGER_END = "<!-- LEDGER:END -->"
SCORES_BEGIN = "<!-- SCORES:BEGIN -->"
SCORES_END = "<!-- SCORES:END -->"


# ---------------------------------------------------------------- 원장 파싱

def parse_ledger(text: str) -> list[dict]:
    """LEDGER 블록의 표에서 콜 목록을 뽑는다."""
    if LEDGER_BEGIN not in text or LEDGER_END not in text:
        raise ValueError("scorecard.md에 LEDGER 블록이 없습니다.")
    block = text.split(LEDGER_BEGIN, 1)[1].split(LEDGER_END, 1)[0]
    calls = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        ticket, ticker, name, direction, base_date, base_px = cells[:6]
        # 헤더/구분선 스킵
        if ticket in ("티켓ID", "") or set(ticket) <= set("-: "):
            continue
        try:
            bd = datetime.strptime(base_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        try:
            bp = float(base_px.replace(",", "")) if base_px else None
        except ValueError:
            bp = None
        calls.append({
            "ticket": ticket, "ticker": ticker, "name": name,
            "direction": direction, "base_date": bd, "base_px": bp,
        })
    return calls


# ---------------------------------------------------------------- 시세

def fetch_prices(ticker: str, start: date) -> pd.DataFrame:
    df = yf.download(ticker, start=start.isoformat(),
                     end=(date.today() + timedelta(days=2)).isoformat(),
                     interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def close_on_or_after(df: pd.DataFrame, target: date):
    """target 날짜 이상인 첫 거래일의 종가와 실제 날짜를 반환. 없으면 (None, None)."""
    if df.empty:
        return None, None
    idx = df.index.normalize()
    mask = idx >= pd.Timestamp(target)
    sub = df[mask]
    if sub.empty:
        return None, None
    return float(sub["Close"].iloc[0]), sub.index[0].date()


# ---------------------------------------------------------------- 채점

def grade(direction: str, ret_pct: float) -> tuple[str, str]:
    """(판정마크, 승패코드) 반환. 승패코드: 'win'/'loss'/'flat'."""
    bullish = direction == "매수"
    if bullish:
        if ret_pct >= NEUTRAL_BAND:
            return "✅ 적중", "win"
        if ret_pct <= -NEUTRAL_BAND:
            return "❌ 빗나감", "loss"
        return "➖ 보합", "flat"
    # 거절·관망 = "오르지 않을 것/피할 것"에 베팅
    if ret_pct <= NEUTRAL_BAND:
        return "✅ 적중", "win"   # 안 올랐으니 회피 정당(하락이면 더 좋음)
    return "❌ 놓침", "loss"       # 크게 올랐으면 기회 놓침


def score_call(call: dict) -> dict:
    df = fetch_prices(call["ticker"], call["base_date"] - timedelta(days=5))
    if df.empty:
        call["error"] = "시세 없음(티커 확인)"
        call["rows"] = []
        return call

    base_px = call["base_px"]
    if base_px is None:
        base_px, base_used = close_on_or_after(df, call["base_date"])
        call["base_px"] = base_px
        call["base_used_date"] = base_used
    if base_px is None:
        call["error"] = "기준가를 구하지 못함"
        call["rows"] = []
        return call

    today = date.today()
    rows = []
    for label, days in HORIZONS:
        target = call["base_date"] + timedelta(days=days)
        if target > today:
            rows.append({"label": label, "status": "대기",
                         "detail": f"D-{(target - today).days}"})
            continue
        px, used = close_on_or_after(df, target)
        if px is None:
            rows.append({"label": label, "status": "데이터없음", "detail": "—"})
            continue
        ret = (px / base_px - 1) * 100
        mark, code = grade(call["direction"], ret)
        rows.append({"label": label, "status": "채점", "price": px,
                     "used_date": used, "ret": ret, "mark": mark, "code": code})
    call["rows"] = rows
    return call


# ---------------------------------------------------------------- 렌더링

def _fmt_px(x: float) -> str:
    return f"{x:,.2f}"


def render_scores(calls: list[dict]) -> str:
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"_마지막 채점: {updated} · 채점기준: 절대 방향 · 중립밴드 ±{NEUTRAL_BAND:.0f}%_", ""]

    # 콜별 상세 표
    lines.append("### 콜별 채점")
    lines.append("| 티켓ID | 종목 | 방향 | 기준가 | 다음날 | 1주 | 1개월 | 3개월 |")
    lines.append("|--------|------|:---:|-------:|:---:|:---:|:---:|:---:|")
    agg = {}  # label -> {'win','loss','rets'(매수 수익률)}
    for c in calls:
        if c.get("error"):
            lines.append(f"| {c['ticket']} | {c['name']} | {c['direction']} | — | "
                         f"⚠️ {c['error']} |  |  |  |")
            continue
        cells = {h[0]: "—" for h in HORIZONS}
        for r in c["rows"]:
            if r["status"] == "대기":
                cells[r["label"]] = f"⏳{r['detail']}"
            elif r["status"] == "채점":
                cells[r["label"]] = f"{r['mark']}<br>{r['ret']:+.1f}%"
                a = agg.setdefault(r["label"], {"win": 0, "loss": 0, "rets": []})
                if r["code"] == "win":
                    a["win"] += 1
                elif r["code"] == "loss":
                    a["loss"] += 1
                if c["direction"] == "매수":
                    a["rets"].append(r["ret"])
            else:
                cells[r["label"]] = "·"
        base_str = _fmt_px(c["base_px"]) if c["base_px"] else "—"
        lines.append(f"| {c['ticket']} | {c['name']} | {c['direction']} | {base_str} | "
                     f"{cells['다음날']} | {cells['1주']} | {cells['1개월']} | {cells['3개월']} |")

    # 집계
    lines += ["", "### 집계 (누적)"]
    lines.append("| 시점 | 채점 콜 | 적중 | 빗나감 | 적중률 | 매수 평균수익률 |")
    lines.append("|------|:------:|:---:|:-----:|:-----:|:--------------:|")
    tot_w = tot_l = 0
    all_rets = []
    for label, _ in HORIZONS:
        a = agg.get(label)
        if not a:
            lines.append(f"| {label} | 0 | 0 | 0 | — | — |")
            continue
        w, l = a["win"], a["loss"]
        tot_w += w
        tot_l += l
        all_rets += a["rets"]
        decided = w + l
        hit = f"{w / decided * 100:.0f}%" if decided else "—"
        avg = f"{sum(a['rets']) / len(a['rets']):+.1f}%" if a["rets"] else "—"
        lines.append(f"| {label} | {decided} | {w} | {l} | {hit} | {avg} |")
    tot_dec = tot_w + tot_l
    tot_hit = f"{tot_w / tot_dec * 100:.0f}%" if tot_dec else "—"
    tot_avg = f"{sum(all_rets) / len(all_rets):+.1f}%" if all_rets else "—"
    lines.append(f"| **전체** | **{tot_dec}** | **{tot_w}** | **{tot_l}** | **{tot_hit}** | **{tot_avg}** |")

    lines += ["", "> 페이퍼 트레이딩·학습용. 실제 투자 성과가 아니며 표본이 작을 때 적중률은 참고만.",
              "> ⏳=아직 그 시점 미도래(D-n), ➖ 보합은 승패에서 제외."]
    return "\n".join(lines)


def rewrite(path: str, calls: list[dict]) -> str:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    scores = render_scores(calls)
    new_block = f"{SCORES_BEGIN}\n{scores}\n{SCORES_END}"
    if SCORES_BEGIN in text and SCORES_END in text:
        head = text.split(SCORES_BEGIN, 1)[0]
        tail = text.split(SCORES_END, 1)[1]
        text = head + new_block + tail
    else:
        text = text.rstrip() + "\n\n## 📊 채점 결과\n" + new_block + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="workspace/scorecard.md",
                    help="성적표 파일 경로 (기본: workspace/scorecard.md)")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as f:
            calls = parse_ledger(f.read())
    except FileNotFoundError:
        print(f"[오류] 파일이 없습니다: {args.file}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[오류] {e}", file=sys.stderr)
        sys.exit(1)

    if not calls:
        print("[안내] 원장에 채점할 콜이 없습니다. LEDGER 블록에 콜을 추가하세요.")
        sys.exit(0)

    print(f"콜 {len(calls)}건 채점 중...", file=sys.stderr)
    scored = [score_call(c) for c in calls]
    out = rewrite(args.file, scored)
    print(out)
    print(f"\n성적표 갱신 완료: {args.file}", file=sys.stderr)


if __name__ == "__main__":
    main()
