"""
fundamentals.py — 펀더멘털 실측 도구 (TradingDesk, Phase 1 신뢰도)

리서처가 웹에서 주워온 시총·PER·매출 등 정량 수치는 환각 위험이 크다(삼성 시총
'767조' 오기 사례). 이 도구는 yfinance에서 **실제 펀더멘털 수치**를 받아 '검증된 앵커'
표로 출력한다. 데스크는 이 표를 사실로 깔고, 웹 수치가 여기와 어긋나면 환각으로 의심한다.

기술 스냅샷(ta_snapshot.py)이 '차트/지표'의 사실 소스이듯, 이 도구는 '펀더멘털 숫자'의
사실 소스다.

주의: yfinance는 한국 종목의 후행PER·PBR·EPS를 종종 제공하지 않는다(None). 그런 항목은
'N/A (미제공 → 공식 공시 필요)'로 정직하게 표기하고, 절대 추정치로 채우지 않는다.

사용법:
    python tools/fundamentals.py <ticker>
    예: python tools/fundamentals.py 005930.KS   /   python tools/fundamentals.py NVDA
    6자리 숫자만 주면 .KS→.KQ 순으로 자동 시도.
"""

import sys
import argparse
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import yfinance as yf

NA = "N/A (yfinance 미제공 → 공식 공시(DART 등) 필요, 추정 금지)"


def resolve_ticker(raw: str):
    raw = raw.strip().upper()
    if raw.isdigit() and len(raw) == 6:
        return [f"{raw}.KS", f"{raw}.KQ"]
    return [raw]


def fmt_big(v, currency: str) -> str:
    """큰 금액을 통화별 단위로. KRW=조/억, 그 외=T/B/M."""
    if v is None:
        return NA
    v = float(v)
    if currency == "KRW":
        jo = v / 1e12
        if abs(jo) >= 1:
            return f"{jo:,.1f}조 원"
        eok = v / 1e8
        return f"{eok:,.0f}억 원"
    # USD 등
    if abs(v) >= 1e12:
        return f"${v/1e12:,.2f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:,.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:,.2f}M"
    return f"${v:,.0f}"


def fmt_num(v, suffix="", nd=2):
    if v is None:
        return NA
    return f"{float(v):,.{nd}f}{suffix}"


def fmt_price(v, currency: str):
    if v is None:
        return NA
    unit = "원" if currency == "KRW" else ""
    return f"{float(v):,.2f} {unit}".strip()


_REC_KO = {
    "strong_buy": "적극매수", "buy": "매수", "hold": "보유/중립",
    "underperform": "시장수익률 하회", "sell": "매도",
}


def build_consensus(info: dict, cur: str) -> str:
    """애널리스트 목표주가·투자의견 블록. yfinance info 재사용(추가 호출 없음).

    한국 종목은 yfinance 애널 커버리지가 얇어 대부분 None일 수 있다 → 정직하게
    '커버리지 없음'으로 표기하고 지어내지 않는다.
    """
    mean = info.get("targetMeanPrice")
    high = info.get("targetHighPrice")
    low = info.get("targetLowPrice")
    n = info.get("numberOfAnalystOpinions")
    reckey = info.get("recommendationKey")
    price = info.get("currentPrice")

    has_any = any(v is not None for v in (mean, high, low, n, reckey))
    lines = ["", "## 애널리스트 컨센서스 (yfinance)"]
    if not has_any or reckey in (None, "none"):
        lines.append("- 커버리지 없음 (yfinance 미제공) — 목표주가·투자의견 미확인. "
                     "국내 종목은 네이버증권/에프앤가이드 등 별도 확인 필요.")
        return "\n".join(lines)

    rec_ko = _REC_KO.get(reckey, reckey or NA)
    upside = ""
    if mean is not None and price:
        up = (float(mean) - float(price)) / float(price) * 100
        upside = f" · 현재가 대비 **{up:+.1f}%**"
    lines += [
        f"- 투자의견: **{rec_ko}**" + (f" (분석가 {int(n)}명)" if n else ""),
        f"- 목표주가 평균: {fmt_price(mean, cur)}{upside}",
        f"- 목표주가 범위: {fmt_price(low, cur)} ~ {fmt_price(high, cur)}",
        "> ⚠️ yfinance 애널 컨센서스는 시점·표본이 제한적일 수 있음(특히 한국). "
        "방향 참고용, 절대 신뢰 금지.",
    ]
    return "\n".join(lines)


def build(ticker: str) -> str:
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as e:
        return f"[오류] '{ticker}' 정보를 받지 못했습니다: {e}"

    if not info.get("marketCap") and not info.get("currentPrice"):
        return ""  # 사실상 빈 응답 → 상위에서 다음 후보 시도

    cur = info.get("currency") or ("KRW" if ticker.endswith((".KS", ".KQ")) else "USD")
    name = info.get("longName") or info.get("shortName") or ticker
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    # (라벨, 값, 미제공여부)
    rows = [
        ("현재가", fmt_price(info.get("currentPrice"), cur)),
        ("시가총액", fmt_big(info.get("marketCap"), cur)),
        ("선행 PER (forward)", fmt_num(info.get("forwardPE"))),
        ("후행 PER (trailing)", fmt_num(info.get("trailingPE"))),
        ("PBR (주가순자산)", fmt_num(info.get("priceToBook"))),
        ("EPS 후행", fmt_num(info.get("trailingEps"))),
        ("EPS 선행", fmt_num(info.get("forwardEps"))),
        ("매출(TTM)", fmt_big(info.get("totalRevenue"), cur)),
        ("발행주식수", fmt_num(info.get("sharesOutstanding"), nd=0)),
        ("배당수익률", fmt_num(info.get("dividendYield"), suffix="%")),
        ("52주 고점", fmt_price(info.get("fiftyTwoWeekHigh"), cur)),
        ("52주 저점", fmt_price(info.get("fiftyTwoWeekLow"), cur)),
    ]

    lines = [f"## 검증된 펀더멘털: {name} ({ticker})",
             f"- 출처: yfinance 실측 · 기준: {updated} · 통화: {cur}", "",
             "| 항목 | 실측값 |", "|------|--------|"]
    na_items = []
    for label, val in rows:
        lines.append(f"| {label} | {val} |")
        if val == NA:
            na_items.append(label)
    lines += ["", "> **이 값이 사실의 기준이다.** 리서처가 웹에서 가져온 수치가 이 표와 "
              "크게 다르면(예: 배 이상) **환각으로 의심**하고, 리포트에 ⚠️로 표기하라.",
              "> 값이 없는(N/A) 항목은 지어내지 말 것 — 특히 한국 종목의 후행PER·PBR·EPS는 "
              "yfinance가 자주 비운다(공식 공시로 보완)."]
    if na_items:
        lines.append(f"> 이번 미제공 항목: {', '.join(na_items)}")

    lines.append(build_consensus(info, cur))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    args = ap.parse_args()

    out = ""
    used = None
    for cand in resolve_ticker(args.ticker):
        out = build(cand)
        if out:
            used = cand
            break

    if not out:
        print(f"[오류] '{args.ticker}' 펀더멘털을 받지 못했습니다(티커 확인).", file=sys.stderr)
        sys.exit(1)
    print(out)


if __name__ == "__main__":
    main()
