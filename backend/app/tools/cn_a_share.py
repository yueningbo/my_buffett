"""CN A-share + HK stock data via East Money public HTTP APIs — free, no account.

Uses delayed quote host (push2delay) — fine for mentoring, not day-trading.
A-share quote fallback: Sina/Tencent. HK quote fallback: Tencent/Sina.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
}


def is_cn_a_share(symbol: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", symbol.strip()))


def normalize_cn_symbol(symbol: str) -> str:
    return symbol.strip()


def em_market_code(symbol: str) -> str:
    """SH600519 / SZ000858 for F10 endpoints."""
    s = normalize_cn_symbol(symbol)
    if s.startswith(("5", "6", "9")):
        return f"SH{s}"
    return f"SZ{s}"


def em_secid(symbol: str) -> str:
    """1.600519 (SSE) / 0.000858 (SZSE)."""
    s = normalize_cn_symbol(symbol)
    if s.startswith(("5", "6", "9")):
        return f"1.{s}"
    return f"0.{s}"


def sina_list_code(symbol: str) -> str:
    s = normalize_cn_symbol(symbol)
    if s.startswith(("5", "6", "9")):
        return f"sh{s}"
    return f"sz{s}"


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or v == "" or v == "-":
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _client() -> httpx.Client:
    # Some environments lack CA bundle for these hosts; public quote APIs only.
    return httpx.Client(timeout=20.0, verify=False, headers=_HEADERS, follow_redirects=True)


def _fetch_quote_em(symbol: str) -> dict[str, Any] | None:
    secid = em_secid(symbol)
    with _client() as client:
        r = client.get(
            "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
            params={
                "fltt": "2",
                "invt": "2",
                "fields": "f12,f14,f2,f3,f9,f23,f37,f20,f21",
                "secids": secid,
            },
            headers={**_HEADERS, "Referer": "https://quote.eastmoney.com/"},
        )
        r.raise_for_status()
        diff = ((r.json().get("data") or {}).get("diff")) or []
        if not diff:
            return None
        row = diff[0]
        price = _safe_float(row.get("f2"))
        if price is None:
            return None
        return {
            "symbol": str(row.get("f12") or symbol),
            "name": str(row.get("f14") or symbol),
            "last_price": price,
            "pe_ttm": _safe_float(row.get("f9")),
            "pb": _safe_float(row.get("f23")),
            "roe_quote": _safe_float(row.get("f37")),  # often TTM-ish from quote board
        }


def _fetch_quote_sina(symbol: str) -> dict[str, Any] | None:
    code = sina_list_code(symbol)
    with _client() as client:
        r = client.get(
            f"http://hq.sinajs.cn/list={code}",
            headers={**_HEADERS, "Referer": "https://finance.sina.com.cn"},
        )
        r.raise_for_status()
        text = r.content.decode("gb18030", errors="replace")
        # var hq_str_sh600519="name,open,prev,price,..."
        m = re.search(r'="([^"]*)"', text)
        if not m or not m.group(1):
            return None
        parts = m.group(1).split(",")
        if len(parts) < 4:
            return None
        price = _safe_float(parts[3])
        if price is None:
            return None
        return {
            "symbol": normalize_cn_symbol(symbol),
            "name": parts[0] or symbol,
            "last_price": price,
            "pe_ttm": None,
            "pb": None,
            "roe_quote": None,
        }


def _fetch_quote_tencent(symbol: str) -> dict[str, Any] | None:
    code = sina_list_code(symbol)
    with _client() as client:
        r = client.get(f"https://qt.gtimg.cn/q={code}")
        r.raise_for_status()
        text = r.text
        m = re.search(r'="([^"]*)"', text)
        if not m or not m.group(1):
            return None
        parts = m.group(1).split("~")
        # 1=name 2=code 3=price ... 39≈PE
        if len(parts) < 4:
            return None
        price = _safe_float(parts[3])
        if price is None:
            return None
        pe = _safe_float(parts[39]) if len(parts) > 39 else None
        return {
            "symbol": parts[2] or normalize_cn_symbol(symbol),
            "name": parts[1] or symbol,
            "last_price": price,
            "pe_ttm": pe,
            "pb": None,
            "roe_quote": None,
        }


def _fetch_financials(symbol: str) -> dict[str, Any]:
    """Prefer latest annual report for ROE / gross margin."""
    out: dict[str, Any] = {}
    with _client() as client:
        r = client.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_F10_FINANCE_MAINFINADATA",
                "columns": (
                    "SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_TYPE,"
                    "ROEJQ,XSMLL,EPSJB,BPS,TOTALOPERATEREVE,PARENTNETPROFIT"
                ),
                "filter": f'(SECURITY_CODE="{normalize_cn_symbol(symbol)}")',
                "pageNumber": "1",
                "pageSize": "8",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "WEB",
                "client": "WEB",
            },
            headers={**_HEADERS, "Referer": "https://emweb.securities.eastmoney.com/"},
        )
        r.raise_for_status()
        rows = ((r.json().get("result") or {}).get("data")) or []
        if not rows:
            return out
        annual = next((row for row in rows if row.get("REPORT_TYPE") == "年报"), None)
        chosen = annual or rows[0]
        out["roe_pct"] = _safe_float(chosen.get("ROEJQ"))
        gm = _safe_float(chosen.get("XSMLL"))
        out["gross_margin_pct"] = round(gm, 2) if gm is not None else None
        out["report_date"] = str(chosen.get("REPORT_DATE") or "")[:10]
        out["report_type"] = str(chosen.get("REPORT_TYPE") or "")
        rev = _safe_float(chosen.get("TOTALOPERATEREVE"))
        profit = _safe_float(chosen.get("PARENTNETPROFIT"))
        if rev is not None:
            out["revenue_yi"] = round(rev / 1e8, 2)
        if profit is not None:
            out["net_profit_yi"] = round(profit / 1e8, 2)
        if chosen.get("SECURITY_NAME_ABBR"):
            out["name"] = str(chosen["SECURITY_NAME_ABBR"])
    return out


def _fetch_overview(symbol: str) -> dict[str, Any]:
    code = em_market_code(symbol)
    out: dict[str, Any] = {}
    with _client() as client:
        r = client.get(
            "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax",
            params={"code": code},
            headers={**_HEADERS, "Referer": "https://emweb.securities.eastmoney.com/"},
        )
        r.raise_for_status()
        jbzl = (r.json().get("jbzl") or [])
        if not jbzl:
            return out
        jb = jbzl[0]
        out["name"] = str(jb.get("SECURITY_NAME_ABBR") or jb.get("ORG_NAME") or "")
        industry = str(jb.get("EM2016") or jb.get("INDUSTRYCSRC1") or "")
        out["industry"] = industry
        profile = str(jb.get("ORG_PROFILE") or "").strip()
        scope = str(jb.get("BUSINESS_SCOPE") or "").strip()
        bits = [b for b in (profile, f"经营范围：{scope}" if scope else "") if b]
        if industry:
            bits.insert(0, f"行业：{industry}")
        out["business"] = "\n".join(bits)[:800]
    return out


def fetch_cn_bundle(symbol: str) -> dict[str, Any] | None:
    """Normalized fundamentals for a 6-digit A-share code."""
    if not is_cn_a_share(symbol):
        return None
    sym = normalize_cn_symbol(symbol)

    quote: dict[str, Any] | None = None
    for fetcher in (_fetch_quote_em, _fetch_quote_sina, _fetch_quote_tencent):
        try:
            quote = fetcher(sym)
            if quote and quote.get("last_price") is not None:
                break
        except Exception:
            quote = None
    if not quote:
        return None

    fin: dict[str, Any] = {}
    try:
        fin = _fetch_financials(sym)
    except Exception:
        fin = {}

    overview: dict[str, Any] = {}
    try:
        overview = _fetch_overview(sym)
    except Exception:
        overview = {}

    name = (
        overview.get("name")
        or fin.get("name")
        or quote.get("name")
        or sym
    )
    pe = quote.get("pe_ttm")
    roe = fin.get("roe_pct") or quote.get("roe_quote")
    gross = fin.get("gross_margin_pct")
    business = overview.get("business") or ""
    industry = overview.get("industry") or ""
    if not business:
        business = f"{name}（{industry or 'A股'}）" if name else sym

    return {
        "symbol": sym,
        "name": name,
        "industry": industry,
        "business": business,
        "currency": "CNY",
        "last_price": quote.get("last_price"),
        "pe_ttm": pe,
        "roe_pct": roe,
        "gross_margin_pct": gross,
        "revenue_yi": fin.get("revenue_yi"),
        "net_profit_yi": fin.get("net_profit_yi"),
        "report_date": fin.get("report_date"),
        "report_type": fin.get("report_type"),
        "provider": "eastmoney",
    }


# ----- Hong Kong -----


def normalize_hk_symbol(token: str) -> str | None:
    """Normalize to 5-digit HK code: 00700 / 0700.HK / HK00700 → 00700."""
    t = token.strip().upper().replace(" ", "")
    m = re.fullmatch(r"(?:HK)?(\d{1,5})\.HK", t)
    if not m:
        m = re.fullmatch(r"HK(\d{1,5})", t)
    if not m:
        # Bare 5-digit only (avoid years / noise from 4-digit bare codes)
        m = re.fullmatch(r"(\d{5})", t)
    if not m:
        return None
    return m.group(1).zfill(5)


def search_listed_candidates(query: str, *, limit: int = 6) -> list[dict[str, str]]:
    """East Money suggest → candidate list [{symbol, name, market}]."""
    q = (query or "").strip()
    if not q or len(q) > 40:
        return []
    if is_cn_a_share(q):
        return [{"symbol": q, "name": q, "market": "A"}]
    hk = normalize_hk_symbol(q)
    if hk:
        return [{"symbol": hk, "name": hk, "market": "HK"}]

    prefer = {"AStock": ("A", 0), "HK": ("HK", 1), "USStock": ("US", 2)}
    try:
        with _client() as client:
            r = client.get(
                "https://searchapi.eastmoney.com/api/suggest/get",
                params={
                    "input": q,
                    "type": "14",
                    "token": "D43BF722C8E33BDC906FB84D85E326E8",
                    "count": str(max(limit, 8)),
                },
                headers={**_HEADERS, "Referer": "https://so.eastmoney.com/"},
            )
            r.raise_for_status()
            rows = ((r.json().get("QuotationCodeTable") or {}).get("Data")) or []
    except Exception:
        return []

    ranked: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    for row in rows:
        classify = str(row.get("Classify") or "")
        if classify not in prefer:
            continue
        market, rank = prefer[classify]
        code = str(row.get("Code") or "").strip()
        name = str(row.get("Name") or "").strip() or code
        if not code:
            continue
        if classify == "HK":
            code = code.zfill(5)
        stype = str(row.get("SecurityTypeName") or "")
        if classify == "USStock" and (
            "ETF" in stype or "Notes" in name or "收益" in name
        ):
            continue
        if code in seen:
            continue
        seen.add(code)
        ranked.append((rank, {"symbol": code, "name": name, "market": market}))
    ranked.sort(key=lambda x: x[0])
    return [item for _, item in ranked[:limit]]


def search_listed_symbol(query: str) -> tuple[str, str] | None:
    """Best single hit from suggest (exact name match preferred)."""
    q = (query or "").strip()
    cands = search_listed_candidates(q)
    if not cands:
        return None
    for c in cands:
        if c["name"] == q or c["symbol"] == q:
            return c["symbol"], c["name"]
    # unique top market tier
    top_mkt = cands[0]["market"]
    same = [c for c in cands if c["market"] == top_mkt]
    if len(same) == 1 or cands[0]["name"] in q or q in cands[0]["name"]:
        return cands[0]["symbol"], cands[0]["name"]
    return cands[0]["symbol"], cands[0]["name"]


def is_hk_share(symbol: str) -> bool:
    return normalize_hk_symbol(symbol) is not None and not is_cn_a_share(symbol)


def hk_secid(symbol: str) -> str:
    return f"116.{normalize_hk_symbol(symbol) or symbol}"


def _fetch_hk_quote_em(symbol: str) -> dict[str, Any] | None:
    code = normalize_hk_symbol(symbol)
    if not code:
        return None
    with _client() as client:
        r = client.get(
            "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
            params={
                "fltt": "2",
                "invt": "2",
                "fields": "f12,f14,f2,f3,f9,f23,f37",
                "secids": hk_secid(code),
            },
            headers={**_HEADERS, "Referer": f"https://quote.eastmoney.com/hk/{code}.html"},
        )
        r.raise_for_status()
        diff = ((r.json().get("data") or {}).get("diff")) or []
        if not diff:
            return None
        row = diff[0]
        price = _safe_float(row.get("f2"))
        if price is None:
            return None
        return {
            "symbol": str(row.get("f12") or code),
            "name": str(row.get("f14") or code),
            "last_price": price,
            "pe_ttm": _safe_float(row.get("f9")),
            "roe_quote": _safe_float(row.get("f37")),
        }


def _fetch_hk_quote_tencent(symbol: str) -> dict[str, Any] | None:
    code = normalize_hk_symbol(symbol)
    if not code:
        return None
    with _client() as client:
        r = client.get(f"https://qt.gtimg.cn/q=hk{code}")
        r.raise_for_status()
        m = re.search(r'="([^"]*)"', r.text)
        if not m or not m.group(1):
            return None
        parts = m.group(1).split("~")
        if len(parts) < 4:
            return None
        price = _safe_float(parts[3])
        if price is None:
            return None
        return {
            "symbol": parts[2] or code,
            "name": parts[1] or code,
            "last_price": price,
            "pe_ttm": _safe_float(parts[39]) if len(parts) > 39 else None,
            "roe_quote": None,
        }


def _fetch_hk_quote_sina(symbol: str) -> dict[str, Any] | None:
    code = normalize_hk_symbol(symbol)
    if not code:
        return None
    with _client() as client:
        r = client.get(
            f"http://hq.sinajs.cn/list=rt_hk{code}",
            headers={**_HEADERS, "Referer": "https://finance.sina.com.cn"},
        )
        r.raise_for_status()
        text = r.content.decode("gb18030", errors="replace")
        m = re.search(r'="([^"]*)"', text)
        if not m or not m.group(1):
            return None
        parts = m.group(1).split(",")
        # name_en, name_cn, ..., price often index 6
        if len(parts) < 7:
            return None
        price = _safe_float(parts[6])
        if price is None:
            return None
        return {
            "symbol": code,
            "name": parts[1] or parts[0] or code,
            "last_price": price,
            "pe_ttm": None,
            "roe_quote": None,
        }


def _fetch_hk_financials(symbol: str) -> dict[str, Any]:
    code = normalize_hk_symbol(symbol)
    out: dict[str, Any] = {}
    if not code:
        return out
    with _client() as client:
        r = client.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_HKF10_FN_MAININDICATOR",
                "columns": (
                    "SECURITY_CODE,SECURITY_NAME_ABBR,STD_REPORT_DATE,REPORT_TYPE,"
                    "ROE_AVG,GROSS_PROFIT_RATIO,PE_TTM,OPERATE_INCOME,HOLDER_PROFIT"
                ),
                "filter": f'(SECURITY_CODE="{code}")',
                "pageNumber": "1",
                "pageSize": "8",
                "sortTypes": "-1",
                "sortColumns": "STD_REPORT_DATE",
                "source": "WEB",
                "client": "WEB",
            },
            headers={**_HEADERS, "Referer": "https://emweb.securities.eastmoney.com/"},
        )
        r.raise_for_status()
        rows = ((r.json().get("result") or {}).get("data")) or []
        if not rows:
            return out
        annual = next((row for row in rows if "年报" in str(row.get("REPORT_TYPE") or "")), None)
        chosen = annual or rows[0]
        out["roe_pct"] = _safe_float(chosen.get("ROE_AVG"))
        if out["roe_pct"] is not None:
            out["roe_pct"] = round(float(out["roe_pct"]), 2)
        gm = _safe_float(chosen.get("GROSS_PROFIT_RATIO"))
        out["gross_margin_pct"] = round(gm, 2) if gm is not None else None
        pe = _safe_float(chosen.get("PE_TTM"))
        out["pe_ttm"] = round(pe, 2) if pe is not None else None
        out["report_date"] = str(chosen.get("STD_REPORT_DATE") or "")[:10]
        out["report_type"] = str(chosen.get("REPORT_TYPE") or "")
        if chosen.get("SECURITY_NAME_ABBR"):
            out["name"] = str(chosen["SECURITY_NAME_ABBR"])
        # HK reports often in HKD/CNY millions or raw — store as 亿元 when large enough
        rev = _safe_float(chosen.get("OPERATE_INCOME"))
        profit = _safe_float(chosen.get("HOLDER_PROFIT"))
        if rev is not None and rev > 1e6:
            out["revenue_yi"] = round(rev / 1e8, 2)
        if profit is not None and profit > 1e6:
            out["net_profit_yi"] = round(profit / 1e8, 2)
    return out


def _fetch_hk_overview(symbol: str) -> dict[str, Any]:
    code = normalize_hk_symbol(symbol)
    out: dict[str, Any] = {}
    if not code:
        return out
    with _client() as client:
        r = client.get(
            "https://emweb.securities.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax",
            params={"code": code},
            headers={**_HEADERS, "Referer": "https://emweb.securities.eastmoney.com/"},
        )
        r.raise_for_status()
        data = r.json()
        zq = data.get("zqzl") or {}
        gs = data.get("gszl") or {}
        name = str(zq.get("zqjc") or gs.get("gsmc") or "")
        out["name"] = name
        industry = str(zq.get("bk") or zq.get("zqlx") or "港股")
        out["industry"] = industry
        profile = str(gs.get("gsjs") or "").strip()
        en = str(gs.get("ywmc") or "").strip()
        bits = []
        if en:
            bits.append(en)
        if profile:
            bits.append(profile)
        if industry:
            bits.insert(0, f"市场：港交所 · {industry}")
        out["business"] = "\n".join(bits)[:800]
    return out


def fetch_hk_bundle(symbol: str) -> dict[str, Any] | None:
    """Normalized fundamentals for a Hong Kong listing (5-digit code)."""
    code = normalize_hk_symbol(symbol)
    if not code:
        return None

    quote: dict[str, Any] | None = None
    for fetcher in (_fetch_hk_quote_em, _fetch_hk_quote_tencent, _fetch_hk_quote_sina):
        try:
            quote = fetcher(code)
            if quote and quote.get("last_price") is not None:
                break
        except Exception:
            quote = None
    if not quote:
        return None

    fin: dict[str, Any] = {}
    try:
        fin = _fetch_hk_financials(code)
    except Exception:
        fin = {}

    overview: dict[str, Any] = {}
    try:
        overview = _fetch_hk_overview(code)
    except Exception:
        overview = {}

    name = overview.get("name") or fin.get("name") or quote.get("name") or code
    pe = quote.get("pe_ttm") or fin.get("pe_ttm")
    roe = fin.get("roe_pct") or quote.get("roe_quote")
    if roe is not None:
        roe = round(float(roe), 2)
    gross = fin.get("gross_margin_pct")
    business = overview.get("business") or ""
    industry = overview.get("industry") or "港股"
    if not business:
        business = f"{name}（港股 {code}.HK）"

    return {
        "symbol": code,
        "name": name,
        "industry": industry,
        "business": business,
        "currency": "HKD",
        "last_price": quote.get("last_price"),
        "pe_ttm": pe,
        "roe_pct": roe,
        "gross_margin_pct": gross,
        "revenue_yi": fin.get("revenue_yi"),
        "net_profit_yi": fin.get("net_profit_yi"),
        "report_date": fin.get("report_date"),
        "report_type": fin.get("report_type"),
        "provider": "eastmoney",
        "market": "HK",
    }
