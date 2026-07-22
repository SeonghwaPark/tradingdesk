"""
quote_bot.py — 텔레그램 종목조회 봇 (fisher_stock_bot)

fisher_stock_bot 에게 `/quote 005930`, `삼성전자`, `NVDA` 처럼 보내면
현재가·시총·선행PER·DART 확정실적·애널 목표주가·기술신호(이평선/RSI/MACD)를
담은 '팩트 카드'를 회신한다. **AI 판단 없이 실측 데이터만** (무료).

- 기존 tradingdesk 도구 재활용: ta_snapshot(기술), dart(확정실적), yfinance(밸류·컨센)
- GitHub Actions 크론이 주기적으로 실행 → getUpdates 로 밀린 명령 처리 → 회신
- 소유자(TELEGRAM_CHAT_ID)의 메시지에만 응답
"""
import json
import os
import sys

import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import ta_snapshot as ta   # noqa: E402
import dart                # noqa: E402

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
STATE = os.path.join(HERE, "quote_state.json")

REC_KO = {"strong_buy": "적극매수", "buy": "매수", "hold": "보유/중립",
          "underperform": "하회", "sell": "매도"}


# ---------- 상태(offset) ----------
def load_offset() -> int:
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f).get("offset", 0)
    except Exception:
        return 0


def save_offset(o: int):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"offset": o}, f)


# ---------- 텔레그램 ----------
def tg_get_updates(offset: int):
    try:
        r = requests.get(f"{API}/getUpdates",
                         params={"offset": offset, "timeout": 0}, timeout=20)
        return r.json().get("result", []) if r.ok else []
    except Exception as e:
        print("[getUpdates]", e)
        return []


def send(chat_id, text: str):
    try:
        requests.post(f"{API}/sendMessage",
                      json={"chat_id": chat_id, "text": text,
                            "parse_mode": "HTML", "disable_web_page_preview": True},
                      timeout=15)
    except Exception as e:
        print("[send]", e)


# ---------- 포맷 ----------
def _won(v):
    if v is None:
        return "N/A"
    jo = v / 1e12
    return f"{jo:,.2f}조" if abs(jo) >= 1 else f"{v/1e8:,.0f}억"


def _price(v, kr):
    if v is None:
        return "N/A"
    return f"{v:,.0f}원" if kr else f"${v:,.2f}"


def _mktcap(v, kr):
    if v is None:
        return None
    return _won(v) if kr else f"${v/1e9:,.0f}B"


# ---------- 분석(데이터 수집) ----------
def classify(q: str):
    """입력을 (종류, 조회키)로. kr→6자리코드, us→티커."""
    q = q.strip()
    digits = "".join(c for c in q if c.isdigit())
    up = q.upper()
    if up.endswith((".KS", ".KQ")):
        return "kr", up.split(".")[0]
    if len(digits) == 6 and digits == q:
        return "kr", digits
    if q.isascii() and all(c.isalpha() or c in ".-" for c in q):
        return "us", up
    code = dart.code_for_name(q)   # 한글명 → 코드 (DART 키 필요)
    return ("kr", code) if code else (None, None)


def build_card(kind, ticker, info, m, dartd) -> str:
    kr = (kind == "kr")
    name = info.get("longName") or info.get("shortName") or ticker
    price = info.get("currentPrice") or m["last"]

    lines = [f"📊 <b>{name}</b> ({ticker})", "━━━━━━━━━━━━",
             f"현재가 <b>{_price(price, kr)}</b>"]

    vparts = []
    mc = _mktcap(info.get("marketCap"), kr)
    if mc:
        vparts.append(f"시총 {mc}")
    if info.get("forwardPE"):
        vparts.append(f"선행PER {info['forwardPE']:.2f}")
    if vparts:
        lines.append(" · ".join(vparts))

    if dartd:
        rn = dart.REPRT.get(dartd["reprt"], dartd["reprt"])
        lines += ["", f"🏛 <b>DART 확정</b> ({dartd['year']} {rn}·{dartd['fs']})",
                  f"매출 {_won(dartd['매출액'])} · 영업익 {_won(dartd['영업이익'])} · 순익 {_won(dartd['당기순이익'])}"]

    reckey = info.get("recommendationKey")
    mean = info.get("targetMeanPrice")
    n = info.get("numberOfAnalystOpinions")
    if reckey and reckey != "none":
        up = f" (<b>{(mean/price-1)*100:+.0f}%</b>)" if mean and price else ""
        lines += ["", f"🎯 컨센 <b>{REC_KO.get(reckey, reckey)}</b>"
                  + (f"({int(n)}명)" if n else ""),
                  f"목표가 {_price(mean, kr)}{up}"]

    macd_state = "골든" if m["macd"] >= m["macd_signal"] else "데드"
    rsi_state = "과매수" if m["rsi"] >= 70 else "과매도" if m["rsi"] <= 30 else "중립"
    if m["vs_sma20_pct"] < 0 and m["vs_sma60_pct"] < 0:
        ma = "20·60일선 아래"
    elif m["vs_sma20_pct"] >= 0 and m["vs_sma60_pct"] >= 0:
        ma = "20·60일선 위"
    else:
        ma = "이평선 혼조"
    lines += ["", f"📈 {ma} · RSI {m['rsi']:.0f}({rsi_state}) · MACD {macd_state}",
              f"52주고점 {m['from_hi_pct']:+.0f}% · 최근20일 {m['chg20_pct']:+.0f}%"]

    lines += ["", "⚠️ 데이터 스냅샷(참고용) · 투자조언 아님"]
    return "\n".join(lines)


def analyze(query: str):
    kind, key = classify(query)
    if not kind:
        return None
    used, m = None, None
    for c in ta.resolve_ticker(key):
        df = ta.fetch(c, "1y")
        if len(df) >= 60:
            used, m = c, ta.compute(df)
            break
    if not used:
        return None
    try:
        info = yf.Ticker(used).info or {}
    except Exception:
        info = {}
    dartd = None
    if kind == "kr":
        code6 = "".join(c for c in used if c.isdigit())[:6]
        try:
            cc, _ = dart.corp_code_for(code6)
            if cc:
                dartd = dart.latest_financials(cc)
        except Exception as e:
            print("[dart]", e)
    return build_card(kind, used, info, m, dartd)


# ---------- 메인 루프 ----------
HELP = ("📊 <b>종목조회봇</b>\n"
        "종목코드·티커·한글명을 보내면 데이터 카드를 보냅니다.\n"
        "예) <code>005930</code> · <code>삼성전자</code> · <code>NVDA</code> · <code>/quote 000660</code>\n"
        "현재가·시총·선행PER·DART 확정실적·목표주가·기술신호(이평선/RSI/MACD)")


def process():
    offset = load_offset()
    updates = tg_get_updates(offset)
    new_offset = offset
    for u in updates:
        new_offset = u["update_id"] + 1
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            continue
        chat = str(msg.get("chat", {}).get("id", ""))
        if CHAT_ID and chat != CHAT_ID:   # 소유자만 응답
            continue
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        if text in ("/start", "/help"):
            send(chat, HELP)
            continue
        q = text[6:].strip() if text.lower().startswith("/quote") else text
        if text.startswith("/") and not text.lower().startswith("/quote"):
            continue  # 다른 명령 무시
        if not q:
            send(chat, "종목을 알려주세요. 예: <code>/quote 005930</code>")
            continue
        send(chat, f"🔎 <b>{q}</b> 조회 중…")
        try:
            card = analyze(q)
        except Exception as e:
            print("[analyze]", e)
            card = None
        send(chat, card or (f"'{q}' 를 못 찾았어요. 종목코드(005930)·티커(NVDA) 또는 "
                            "정확한 한글명으로 보내보세요. (한글명은 DART 키 필요)"))
    save_offset(new_offset)


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN 없음 — 종료")
        sys.exit(0)
    process()
