"""
ai_analysis.py — quote-bot용 AI 심층분석 레이어 (선택적, OpenAI)

수집한 실측 데이터(DART 확정실적·애널 컨센서스·시세/기술지표·최근공시)를 gpt-4o-mini에
넘겨, night-brief처럼 '관점(펀더멘털/기술/리스크) + 촉매/유의' 문장을 생성한다.
데이터에 근거만 하고 매수/매도 권유는 하지 않는다.

OPENAI_API_KEY 가 없거나 호출 실패하면 None 을 반환 → 봇은 데이터 카드만 보낸다(안 깨짐).
night-brief/brief/analyst.py 와 동일한 호출 방식(gpt-4o-mini, json_object).
"""
import json
import os

MODEL = "gpt-4o-mini"

SYSTEM = (
    "당신은 여러 전문가 관점(렌즈)에서 깊이 있게 분석하는 신중한 주식 애널리스트입니다.\n"
    "사용자가 준 실측 데이터(DART 확정실적·애널리스트 컨센서스·시세/기술지표(MA5/20/50/60·"
    "RSI·MACD)·최근공시·최근뉴스)에만 근거해 한국어로 분석합니다.\n"
    "[원칙]\n"
    "- 매수/매도/보유 권유 금지. 중립적 분석·시나리오만 (AI 추론이며 투자 권유가 아님).\n"
    "- 제공된 데이터에 없는 사실·수치를 지어내지 마세요. 불확실하면 불확실하다고 쓰세요.\n"
    "- DART 확정실적은 공식 수치이니 신뢰하고, 컨센서스는 '시장 기대'로만 다루세요.\n"
    "- 뉴스를 인용할 땐 매체를 함께 밝히세요(예: '로이터에 따르면'). 보도 사실과 본인 해석을 구분.\n"
    "- **최근뉴스에 애널리스트·증권사·투자기관(하우스)의 의견·목표주가·등급이 있으면 반드시 뽑아** "
    "expert_views에 기관/매체와 함께 정리하세요. 없으면 빈 배열.\n"
    "- 각 렌즈는 구체적으로 2~3문장. 최대한 상세하고 근거 있게.\n"
    "[출력] 다음 JSON만:\n"
    '{"summary_line": "이 종목 현 상황 핵심 한 줄", '
    '"lenses": {"fundamental": "실적·밸류에이션(DART·PER·YoY) 관점 2~3문장", '
    '"technical": "MA5/20/50/60·RSI·MACD·추세 관점 2~3문장", '
    '"macro": "섹터·업황·매크로·뉴스 흐름 관점 2~3문장", '
    '"risk": "하방/유의 시나리오 2~3문장"}, '
    '"expert_views": ["뉴스 속 애널/증권사/하우스 의견·목표가(기관·매체 명시), 없으면 []"], '
    '"thesis": {"catalysts": ["촉매 최대3"], "risks": ["유의점 최대3"], '
    '"checkpoints": ["앞으로 볼 관전포인트 최대3"]}}'
)


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _ask(messages):
    resp = _client().chat.completions.create(
        model=MODEL, messages=messages,
        response_format={"type": "json_object"}, temperature=0.4)
    return json.loads(resp.choices[0].message.content)


_REPRT = {"11011": "사업보고서", "11012": "반기보고서",
          "11013": "1분기보고서", "11014": "3분기보고서"}


def _yoy(cur, prev):
    if cur and prev and prev != 0:
        return round((cur / prev - 1) * 100, 1)
    return None


def build_payload(name, ticker, kr, info, m, dartd, day_chg, disc, news=None) -> dict:
    price = info.get("currentPrice") or m["last"]
    p = {
        "종목": name, "티커": ticker, "시장": "한국" if kr else "미국",
        "현재가": price, "당일등락%": round(day_chg, 2) if day_chg is not None else None,
        "시가총액": info.get("marketCap"),
        "선행PER": info.get("forwardPE"), "PBR": info.get("priceToBook"),
        "배당수익률%": info.get("dividendYield"),
        "기술지표": {
            "현재가_대비_5일선%": round(m.get("vs_sma5_pct", 0), 1),
            "현재가_대비_20일선%": round(m["vs_sma20_pct"], 1),
            "현재가_대비_50일선%": round(m.get("vs_sma50_pct", 0), 1),
            "현재가_대비_60일선%": round(m["vs_sma60_pct"], 1),
            "RSI14": round(m["rsi"], 1),
            "MACD": "골든" if m["macd"] >= m["macd_signal"] else "데드",
            "52주고점대비%": round(m["from_hi_pct"], 1),
            "52주저점대비%": round(m["from_lo_pct"], 1),
            "최근20일등락%": round(m["chg20_pct"], 1),
        },
    }
    if news:
        p["최근뉴스"] = [{"제목": n["title"], "매체": n.get("publisher")}
                     for n in news[:5]]
    if dartd:
        prev = dartd.get("prev") or {}
        p["DART확정실적"] = {
            "기준": f"{dartd['year']} {_REPRT.get(dartd['reprt'], dartd['reprt'])} ({dartd['fs']})",
            "매출액": dartd["매출액"], "영업이익": dartd["영업이익"],
            "당기순이익": dartd["당기순이익"],
            "매출_전년比%": _yoy(dartd["매출액"], prev.get("매출액")),
            "영업이익_전년比%": _yoy(dartd["영업이익"], prev.get("영업이익")),
        }
    if info.get("recommendationKey") and info.get("recommendationKey") != "none":
        p["애널컨센서스"] = {
            "투자의견": info.get("recommendationKey"),
            "목표주가평균": info.get("targetMeanPrice"),
            "분석가수": info.get("numberOfAnalystOpinions"),
        }
    if disc:
        p["최근공시"] = [d.get("report_nm", "") for d in disc[:3]]
    return p


def _format(j: dict) -> str:
    lens = j.get("lenses", {})
    th = j.get("thesis", {})
    lines = ["🔎 <b>AI 심층분석</b>"]
    if j.get("summary_line"):
        lines.append(j["summary_line"])
    lines.append("")
    if lens.get("fundamental"):
        lines.append(f"· <b>펀더멘털</b>: {lens['fundamental']}")
    if lens.get("technical"):
        lines.append(f"· <b>기술적</b>: {lens['technical']}")
    if lens.get("macro"):
        lines.append(f"· <b>매크로/섹터</b>: {lens['macro']}")
    if lens.get("risk"):
        lines.append(f"· <b>리스크</b>: {lens['risk']}")
    evs = j.get("expert_views") or []
    if evs:
        lines += ["", "🏦 <b>전문가·하우스 뷰</b>"]
        for ev in evs[:3]:
            lines.append(f"· {ev}")
    cats = th.get("catalysts") or []
    risks = th.get("risks") or []
    checks = th.get("checkpoints") or []
    if cats:
        lines += ["", "🚀 촉매: " + " / ".join(cats)]
    if risks:
        lines.append("⚠️ 유의: " + " / ".join(risks))
    if checks:
        lines.append("👀 관전포인트: " + " / ".join(checks))
    lines += ["", "⚠️ AI 추론(참고용) · 투자권유 아님"]
    return "\n".join(lines)


def analyze(name, ticker, kr, info, m, dartd, day_chg, disc, news=None, ask=None) -> str | None:
    """AI 심층분석 텍스트 반환. 키 없거나 실패 시 None."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    payload = build_payload(name, ticker, kr, info, m, dartd, day_chg, disc, news)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "이 종목을 분석하세요.\n"
         + json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        j = (ask or _ask)(messages)
        return _format(j)
    except Exception as e:
        print("[ai]", e)
        return None
