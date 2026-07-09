"""
context_snapshot.py — 매크로·시장 배경 스냅샷 도구 (TradingDesk)

특정 기간(기준일→채점일) 동안의 시장 지수·환율 **실제 등락**을 yfinance로 뽑는다.
성적표 복기(`/desk review`)에서 "이 종목이 왜 이렇게 움직였나"를 설명할 때,
매크로 숫자를 지어내지 않고 사실로 깔아주기 위한 도구.

리서처(웹검색)는 이 숫자 위에 '정성적 뉴스 원인'만 얹는다. 숫자는 여기서만 나온다.

사용법:
    python tools/context_snapshot.py <시작일> <종료일> [--ticker 005930.KS]
    예: python tools/context_snapshot.py 2026-07-02 2026-07-09 --ticker 005930.KS

출력: 코스피·코스닥·필라델피아반도체·원/달러(+선택 종목)의 기간 등락률 표.
"""

import sys
import argparse
from datetime import date, datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import yfinance as yf

# (심볼, 표시이름). 종목이 주어지면 맨 앞에 끼워 넣는다.
MACRO = [
    ("^KS11", "코스피"),
    ("^KQ11", "코스닥"),
    ("^SOX", "필라델피아 반도체(SOX)"),
    ("^IXIC", "나스닥"),
    ("KRW=X", "원/달러 환율"),
]


def fetch(symbol: str, start: date, end: date) -> pd.DataFrame:
    df = yf.download(symbol, start=start.isoformat(),
                     end=(end + timedelta(days=2)).isoformat(),
                     interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def close_on_or_after(df: pd.DataFrame, target: date):
    if df.empty:
        return None, None
    sub = df[df.index.normalize() >= pd.Timestamp(target)]
    if sub.empty:
        return None, None
    return float(sub["Close"].iloc[0]), sub.index[0].date()


def close_on_or_before(df: pd.DataFrame, target: date):
    if df.empty:
        return None, None
    sub = df[df.index.normalize() <= pd.Timestamp(target)]
    if sub.empty:
        return None, None
    return float(sub["Close"].iloc[-1]), sub.index[-1].date()


def move(symbol: str, name: str, start: date, end: date) -> dict:
    df = fetch(symbol, start - timedelta(days=5), end)
    p0, d0 = close_on_or_after(df, start)
    p1, d1 = close_on_or_before(df, end)
    if p0 is None or p1 is None:
        return {"name": name, "ok": False}
    return {"name": name, "ok": True, "p0": p0, "p1": p1,
            "d0": d0, "d1": d1, "ret": (p1 / p0 - 1) * 100}


def render(rows: list[dict], start: date, end: date) -> str:
    out = [f"## 매크로·시장 배경: {start} → {end} (실제 종가 기준)", "",
           "| 지표 | 시작 | 끝 | 등락 |", "|------|-----:|----:|:---:|"]
    for r in rows:
        if not r["ok"]:
            out.append(f"| {r['name']} | — | — | 데이터없음 |")
            continue
        arrow = "🔺" if r["ret"] > 0.3 else "🔻" if r["ret"] < -0.3 else "▬"
        out.append(f"| {r['name']} | {r['p0']:,.2f} | {r['p1']:,.2f} | {arrow} {r['ret']:+.1f}% |")
    out += ["", "> 위 등락은 계산된 사실이다. '왜 이렇게 움직였나'의 뉴스·원인 해석만 리서처가 덧붙인다.",
            "> 종목 등락을 지수와 비교하면 개별재료(알파) vs 시장흐름(베타)을 구분할 수 있다."]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", help="시작일 YYYY-MM-DD (기준일)")
    ap.add_argument("end", help="종료일 YYYY-MM-DD (채점일)")
    ap.add_argument("--ticker", default=None, help="종목 yfinance 티커(선택). 지수와 함께 비교 표시.")
    args = ap.parse_args()

    try:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        print("[오류] 날짜 형식은 YYYY-MM-DD 여야 합니다.", file=sys.stderr)
        sys.exit(1)
    if end < start:
        print("[오류] 종료일이 시작일보다 앞섭니다.", file=sys.stderr)
        sys.exit(1)

    symbols = list(MACRO)
    if args.ticker:
        symbols = [(args.ticker, f"📌 {args.ticker}")] + symbols

    rows = [move(sym, name, start, end) for sym, name in symbols]
    print(render(rows, start, end))


if __name__ == "__main__":
    main()
