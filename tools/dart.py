"""
dart.py — DART(금융감독원 전자공시) 1차 자료 도구 (한국 종목 전용)

OpenDART API로 **확정 재무(연결 기준: 매출액·영업이익·당기순이익)**와 **최근 공시 목록**을
받아온다. 리서처가 웹 뉴스에서 주워온 실적 수치가 이 1차 자료와 크게 다르면(자릿수 등)
환각으로 의심하는 '공식 앵커'로 쓴다. (yfinance가 못 채우는 한국 후행실적의 구멍을 메움)

준비(한 번만):
  1) https://opendart.fss.or.kr 무료 가입 → '인증키 신청/관리'에서 API 인증키 발급
  2) 환경변수 DART_API_KEY 에 그 키를 설정 (.env 또는 시스템 환경변수)

사용:
  python tools/dart.py 005930        # 삼성전자
  python tools/dart.py 000660.KS     # .KS/.KQ 접미사 붙어도 됨(6자리만 사용)

키가 없거나 해당 종목이 DART에 없으면(미국주 등) 에러 대신 '미확인' 안내를 출력하고
정상 종료(exit 0)한다 — 데스크 파이프라인을 끊지 않기 위해서다.
"""
import argparse
import datetime
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

KEY = os.environ.get("DART_API_KEY", "").strip()
BASE = "https://opendart.fss.or.kr/api"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")
CORPCODE_XML = os.path.join(CACHE_DIR, "CORPCODE.xml")

REPRT = {"11011": "사업보고서(연간)", "11012": "반기보고서",
         "11013": "1분기보고서", "11014": "3분기보고서"}


def _http(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tradingdesk-dart/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _http_json(path: str, params: dict) -> dict:
    params = {**params, "crtfc_key": KEY}
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    return json.loads(_http(url).decode("utf-8"))


def normalize_code(raw: str) -> str:
    raw = raw.strip().upper().replace(".KS", "").replace(".KQ", "")
    digits = "".join(c for c in raw if c.isdigit())
    return digits.zfill(6) if digits else raw


def ensure_corpcode() -> bool:
    """corpCode.xml(종목코드→고유번호 매핑)을 1회 내려받아 캐시."""
    if os.path.exists(CORPCODE_XML):
        return True
    os.makedirs(CACHE_DIR, exist_ok=True)
    data = _http(f"{BASE}/corpCode.xml?crtfc_key={KEY}")
    # 키 오류 등은 zip이 아니라 JSON/XML 에러로 온다
    if data[:2] != b"PK":  # zip 시그니처 아님
        return False
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        inner = z.namelist()[0]
        with z.open(inner) as f, open(CORPCODE_XML, "wb") as out:
            out.write(f.read())
    return True


def corp_code_for(stock_code: str):
    if not ensure_corpcode():
        return None, None
    tree = ET.parse(CORPCODE_XML)
    for el in tree.getroot().iter("list"):
        if (el.findtext("stock_code") or "").strip() == stock_code:
            return (el.findtext("corp_code") or "").strip(), (el.findtext("corp_name") or "").strip()
    return None, None


def _amt(s: str):
    s = (s or "").strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _won(v):
    if v is None:
        return "N/A"
    jo = v / 1e12
    if abs(jo) >= 1:
        return f"{jo:,.2f}조 원"
    return f"{v/1e8:,.0f}억 원"


def latest_financials(corp_code: str):
    """가장 최근에 제출된 보고서의 연결(CFS) 주요 손익을 반환."""
    y = datetime.date.today().year
    # 최신 제출분부터 시도 (mid-year 기준: 당해 1Q → 전년 사업보고서 → 전년 3Q ...)
    candidates = [
        (y, "11014"), (y, "11012"), (y, "11013"),
        (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012"), (y - 1, "11013"),
        (y - 2, "11011"),
    ]
    for year, reprt in candidates:
        try:
            res = _http_json("fnlttSinglAcnt.json", {
                "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt})
        except Exception:
            continue
        if res.get("status") != "000" or not res.get("list"):
            continue
        rows = res["list"]
        # account_nm 은 회사마다 '당기순이익(손실)' 처럼 표기가 달라 부분일치로 잡는다.
        keys = ["매출액", "영업이익", "당기순이익"]
        for pref in ("CFS", "OFS"):  # 연결 우선, 없으면 별도
            want = {k: None for k in keys}
            for r in rows:
                if r.get("fs_div") != pref:
                    continue
                nm = (r.get("account_nm") or "").strip()
                for k in keys:
                    if want[k] is None and k in nm:   # 첫 부분일치 채택(주계정이 먼저 옴)
                        want[k] = _amt(r.get("thstrm_amount"))
            if any(v is not None for v in want.values()):
                fs_label = "연결" if pref == "CFS" else "별도"
                return {"year": year, "reprt": reprt, "fs": fs_label, **want}
    return None


def recent_disclosures(corp_code: str, days=120, n=8):
    end = datetime.date.today()
    bgn = end - datetime.timedelta(days=days)
    try:
        res = _http_json("list.json", {
            "corp_code": corp_code, "bgn_de": bgn.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"), "page_count": str(n)})
    except Exception:
        return []
    if res.get("status") != "000":
        return []
    return res.get("list", [])[:n]


def build(raw_code: str) -> str:
    if not KEY:
        return ("## DART 1차 공시\n"
                "- ⚠️ **DART_API_KEY 미설정** — 확정 재무·공시 미확인.\n"
                "- 발급: https://opendart.fss.or.kr 가입 → 인증키 신청 → 환경변수 `DART_API_KEY` 설정.\n"
                "- (키 설정 전까지 한국 종목 확정 실적은 웹 재인용에만 의존 → 자릿수 환각 주의)")

    code = normalize_code(raw_code)
    if not (code.isdigit() and len(code) == 6):
        return f"## DART 1차 공시\n- 해당 티커({raw_code})는 국내 종목코드가 아님 → DART 대상 아님(미국주 등)."

    corp_code, corp_name = corp_code_for(code)
    if not corp_code:
        return (f"## DART 1차 공시\n- 종목코드 {code} 에 해당하는 DART 고유번호를 찾지 못함"
                " (비상장/폐지/키 오류 가능). 확정 실적 미확인.")

    fin = latest_financials(corp_code)
    disc = recent_disclosures(corp_code)

    lines = [f"## DART 1차 공시: {corp_name} ({code})",
             f"- 출처: OpenDART 실측 · 기준: {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]

    if fin:
        rn = REPRT.get(fin["reprt"], fin["reprt"])
        lines += [
            f"### 확정 재무 ({fin['year']} {rn}, {fin['fs']} 기준)",
            "| 항목 | 금액 |", "|------|------|",
            f"| 매출액 | {_won(fin['매출액'])} |",
            f"| 영업이익 | {_won(fin['영업이익'])} |",
            f"| 당기순이익 | {_won(fin['당기순이익'])} |",
            "> **이 수치가 공식 확정치다.** 웹 뉴스의 실적 숫자가 이와 자릿수부터 다르면 환각으로 의심.",
            "> 분기/반기 보고서는 누적 기준일 수 있으니 기간 라벨을 함께 볼 것.", "",
        ]
    else:
        lines += ["### 확정 재무", "- 최근 보고서에서 손익 수치를 확보하지 못함(보고서 미제출 시기 등). 미확인.", ""]

    lines.append("### 최근 공시")
    if disc:
        for d in disc:
            dt = d.get("rcept_dt", "")
            dt = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}" if len(dt) == 8 else dt
            nm = (d.get("report_nm") or "").strip()
            rno = d.get("rcept_no", "")
            url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}" if rno else ""
            lines.append(f"- {dt} · {nm}" + (f" ({url})" if url else ""))
    else:
        lines.append("- 최근 공시 없음 또는 조회 실패.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="국내 종목코드 6자리 (005930, 000660.KS 등)")
    args = ap.parse_args()
    print(build(args.code))


if __name__ == "__main__":
    main()
