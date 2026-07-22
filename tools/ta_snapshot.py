"""
ta_snapshot.py — 기술적 분석 스냅샷 도구 (TradingDesk)

yfinance로 일봉 OHLCV를 받아 이동평균/RSI/MACD 등을 계산하고,
기술 분석가 에이전트가 해석할 수 있도록 마크다운 요약을 출력한다.
선택적으로 캔들차트 PNG를 저장한다.

사용법:
    python ta_snapshot.py <ticker> [--chart <저장경로.png>] [--period 1y]

ticker 예:
    005930.KS   (한국 코스피: 6자리코드 + .KS)
    000660.KS   (SK하이닉스)
    035720.KQ   (코스닥은 .KQ)
    NVDA        (미국)

6자리 숫자만 주면 .KS → .KQ 순으로 자동 시도한다.
"""

import sys
import argparse

# 윈도우 콘솔(cp949)에서도 한글·특수문자 출력이 깨지지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD


def resolve_ticker(raw: str):
    """6자리 숫자면 .KS, .KQ 순으로 시도. 그 외엔 그대로 사용."""
    raw = raw.strip().upper()
    if raw.isdigit() and len(raw) == 6:
        return [f"{raw}.KS", f"{raw}.KQ"]
    return [raw]


def fetch(ticker: str, period: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    # yfinance가 MultiIndex 컬럼을 줄 때 평탄화
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def compute(df: pd.DataFrame) -> dict:
    close = df["Close"].astype(float)
    sma5 = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma60 = close.rolling(60).mean()
    rsi = RSIIndicator(close=close, window=14).rsi()
    macd = MACD(close=close)

    last = float(close.iloc[-1])
    s5 = float(sma5.iloc[-1])
    s20 = float(sma20.iloc[-1])
    s50 = float(sma50.iloc[-1])
    s60 = float(sma60.iloc[-1])
    hi52 = float(close.tail(252).max())
    lo52 = float(close.tail(252).min())
    chg20 = (last / float(close.iloc[-21]) - 1) * 100 if len(close) > 21 else float("nan")

    return {
        "last": last,
        "sma5": s5,
        "sma20": s20,
        "sma50": s50,
        "sma60": s60,
        "vs_sma5_pct": (last / s5 - 1) * 100,
        "vs_sma20_pct": (last / s20 - 1) * 100,
        "vs_sma50_pct": (last / s50 - 1) * 100,
        "vs_sma60_pct": (last / s60 - 1) * 100,
        "rsi": float(rsi.iloc[-1]),
        "macd": float(macd.macd().iloc[-1]),
        "macd_signal": float(macd.macd_signal().iloc[-1]),
        "hi52": hi52,
        "lo52": lo52,
        "from_hi_pct": (last / hi52 - 1) * 100,
        "from_lo_pct": (last / lo52 - 1) * 100,
        "chg20_pct": chg20,
        "n_bars": len(close),
    }


def render(ticker: str, m: dict) -> str:
    def sign(x):
        return "위" if x >= 0 else "아래"

    rsi_state = ("과매수(>70)" if m["rsi"] >= 70
                 else "과매도(<30)" if m["rsi"] <= 30
                 else "중립")
    macd_state = "골든(신호선 위)" if m["macd"] >= m["macd_signal"] else "데드(신호선 아래)"

    return f"""## 기술적 지표 스냅샷: {ticker}
- 데이터: 최근 {m['n_bars']}거래일 (일봉, 배당·분할 조정)

| 지표 | 값 | 해석 |
|------|-----|------|
| 현재가 | {m['last']:,.2f} | — |
| 20일 이평선(SMA20) | {m['sma20']:,.2f} | 현재가가 20일선 **{sign(m['vs_sma20_pct'])}** ({m['vs_sma20_pct']:+.1f}%) |
| 60일 이평선(SMA60) | {m['sma60']:,.2f} | 현재가가 60일선 **{sign(m['vs_sma60_pct'])}** ({m['vs_sma60_pct']:+.1f}%) |
| RSI(14) | {m['rsi']:.1f} | {rsi_state} |
| MACD | {m['macd']:.2f} / 신호 {m['macd_signal']:.2f} | {macd_state} |
| 52주 고점 대비 | {m['from_hi_pct']:+.1f}% | 고점 {m['hi52']:,.2f} |
| 52주 저점 대비 | {m['from_lo_pct']:+.1f}% | 저점 {m['lo52']:,.2f} |
| 최근 20거래일 등락 | {m['chg20_pct']:+.1f}% | — |

> 위 값은 계산된 사실이다. 매수 타점·추세 판단은 기술 분석가가 이 값을 근거로 서술한다.
"""


def save_chart(df: pd.DataFrame, ticker: str, path: str):
    import mplfinance as mpf
    plot_df = df.tail(180).copy()
    plot_df.index.name = "Date"
    mpf.plot(plot_df, type="candle", mav=(20, 60), volume=True,
             style="yahoo", title=ticker, savefig=path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--chart", default=None, help="캔들차트 PNG 저장 경로")
    ap.add_argument("--period", default="1y")
    args = ap.parse_args()

    df = pd.DataFrame()
    used = None
    for cand in resolve_ticker(args.ticker):
        df = fetch(cand, args.period)
        if not df.empty:
            used = cand
            break

    if df.empty or len(df) < 60:
        print(f"[오류] '{args.ticker}' 시세를 충분히 받지 못했습니다 "
              f"(티커 확인 필요, 최소 60거래일 필요). 받은 봉 수: {len(df)}",
              file=sys.stderr)
        sys.exit(1)

    m = compute(df)
    print(render(used, m))

    if args.chart:
        try:
            save_chart(df, used, args.chart)
            print(f"\n차트 저장: {args.chart}")
        except Exception as e:
            print(f"\n[경고] 차트 저장 실패: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
