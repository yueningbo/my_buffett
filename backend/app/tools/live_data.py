"""Live market / fundamentals fetchers with graceful failure.

A-shares: East Money public APIs (delayed quote, free, no account).
Other markets: yfinance.
Set MY_BUFFETT_TOOL_MODE=live|mock|auto (default auto).
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from app.domain.models import ToolNumber, ToolResult
from app.tools.cn_a_share import fetch_cn_bundle, fetch_hk_bundle, is_cn_a_share, is_hk_share, normalize_hk_symbol
from app.tools.mock_data import MOCK_COMPANIES, resolve_symbol

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_CN = 900.0  # 15 min — delayed quotes are enough for mentoring
_CACHE_TTL_OTHER = 300.0


def tool_mode() -> str:
    return (os.environ.get("MY_BUFFETT_TOOL_MODE") or "auto").strip().lower()


def _yf_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if re.fullmatch(r"\d{6}", s):
        if s.startswith(("5", "6", "9")):
            return f"{s}.SS"
        return f"{s}.SZ"
    return s


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _fetch_yf_bundle(symbol: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    ysym = _yf_symbol(symbol)
    name = symbol
    industry = ""
    business = ""
    currency = "USD"
    price = None
    pe = None
    roe = None
    gross = None

    try:
        t = yf.Ticker(ysym)
        try:
            fi = t.fast_info
            price = _safe_float(getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None))
            currency = str(getattr(fi, "currency", None) or currency)
        except Exception:
            pass
        if price is None:
            hist = t.history(period="5d")
            if hist is not None and not hist.empty:
                price = _safe_float(hist["Close"].iloc[-1])

        info: dict[str, Any] = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}

        if info:
            price = (
                price
                or _safe_float(info.get("regularMarketPrice"))
                or _safe_float(info.get("currentPrice"))
                or _safe_float(info.get("previousClose"))
            )
            pe = _safe_float(info.get("trailingPE")) or _safe_float(info.get("forwardPE"))
            roe_raw = _safe_float(info.get("returnOnEquity"))
            roe = roe_raw * 100 if roe_raw is not None and abs(roe_raw) <= 2 else roe_raw
            gross_raw = _safe_float(info.get("grossMargins"))
            gross = (
                gross_raw * 100 if gross_raw is not None and abs(gross_raw) <= 2 else gross_raw
            )
            currency = str(info.get("currency") or currency)
            name = str(info.get("longName") or info.get("shortName") or name)
            industry = str(info.get("industry") or info.get("sector") or "")
            business = str(info.get("longBusinessSummary") or industry or name)
        if ysym.endswith((".SS", ".SZ")) and currency == "USD":
            currency = "CNY"
        mock = MOCK_COMPANIES.get(symbol) or MOCK_COMPANIES.get(symbol.upper())
        if mock:
            name = mock.get("name") or name
            industry = industry or mock.get("industry") or ""
            business = business if len(business) > 20 else (mock.get("business") or business)
    except Exception:
        return None

    if price is None and pe is None and not business:
        return None

    return {
        "symbol": symbol if re.fullmatch(r"\d{6}", str(symbol)) else str(symbol).upper(),
        "yf_symbol": ysym,
        "name": name,
        "industry": industry,
        "business": (business or name)[:500],
        "currency": currency,
        "last_price": price,
        "pe_ttm": pe,
        "roe_pct": roe,
        "gross_margin_pct": gross,
        "provider": "yfinance",
    }


def fetch_live_bundle(symbol: str) -> dict[str, Any] | None:
    """Return normalized fundamentals dict or None on failure."""
    raw = symbol.strip()
    cache_key = raw.upper()
    resolved = resolve_symbol(raw)
    if resolved:
        cache_key = str(resolved[0]).strip().upper()
    elif is_cn_a_share(raw):
        cache_key = raw
    else:
        hk = normalize_hk_symbol(raw)
        if hk:
            cache_key = hk

    now = time.time()
    hit = _CACHE.get(cache_key)
    ttl = (
        _CACHE_TTL_CN
        if (is_cn_a_share(cache_key) or is_hk_share(cache_key))
        else _CACHE_TTL_OTHER
    )
    if hit and now - hit[0] < ttl:
        return hit[1]

    out: dict[str, Any] | None = None
    if is_cn_a_share(cache_key):
        try:
            out = fetch_cn_bundle(cache_key)
        except Exception:
            out = None
    elif is_hk_share(cache_key):
        try:
            out = fetch_hk_bundle(cache_key)
        except Exception:
            out = None
    else:
        # yfinance accepts 0700.HK
        yf_key = cache_key
        if is_hk_share(raw) and not cache_key.endswith(".HK"):
            yf_key = f"{cache_key}.HK"
        out = _fetch_yf_bundle(yf_key)

    if out is None:
        return None
    _CACHE[cache_key] = (now, out)
    return out


def live_quote(symbol: str) -> ToolResult | None:
    data = fetch_live_bundle(symbol)
    if not data or data.get("last_price") is None:
        return None
    price = float(data["last_price"])
    unit = str(data.get("currency") or "")
    provider = str(data.get("provider") or "live")
    return ToolResult(
        tool="get_quote",
        args={"symbol": data["symbol"]},
        summary=f"{data['name']}({data['symbol']}) 最新价（{provider}）{price} {unit}",
        numbers=[
            ToolNumber(
                key="last_price",
                value=price,
                unit=unit,
                source=f"{provider}:get_quote",
            )
        ],
        raw={
            "symbol": data["symbol"],
            "name": data["name"],
            "currency": unit,
            "yf_symbol": data.get("yf_symbol"),
            "provider": provider,
        },
    )


def live_financials(symbol: str) -> ToolResult | None:
    data = fetch_live_bundle(symbol)
    if not data:
        return None
    provider = str(data.get("provider") or "live")
    numbers: list[ToolNumber] = []
    for key, unit, val in [
        ("pe_ttm", "x", data.get("pe_ttm")),
        ("roe_pct", "%", data.get("roe_pct")),
        ("gross_margin_pct", "%", data.get("gross_margin_pct")),
        ("revenue_yi", "亿元", data.get("revenue_yi")),
        ("net_profit_yi", "亿元", data.get("net_profit_yi")),
    ]:
        if val is None:
            continue
        numbers.append(
            ToolNumber(
                key=key,
                value=float(val),
                unit=unit,
                source=f"{provider}:get_financials_snapshot",
            )
        )
    if not numbers and data.get("last_price") is None:
        return None
    pe, roe, gross = data.get("pe_ttm"), data.get("roe_pct"), data.get("gross_margin_pct")
    period = ""
    if data.get("report_type") or data.get("report_date"):
        period = f"（{data.get('report_type') or ''} {data.get('report_date') or ''}）".strip()
    summary = (
        f"{data['name']} 财务快照（{provider}）{period}："
        f"PE(TTM)={pe if pe is not None else 'n/a'}，"
        f"ROE={roe if roe is not None else 'n/a'}%，"
        f"毛利率={gross if gross is not None else 'n/a'}%"
    )
    return ToolResult(
        tool="get_financials_snapshot",
        args={"symbol": data["symbol"]},
        summary=summary,
        numbers=numbers,
        raw={
            "symbol": data["symbol"],
            "name": data["name"],
            "industry": data.get("industry"),
            "provider": provider,
            "report_date": data.get("report_date"),
            "report_type": data.get("report_type"),
        },
    )


def live_overview(symbol: str) -> ToolResult | None:
    data = fetch_live_bundle(symbol)
    if not data:
        return None
    business = str(data.get("business") or "").strip()
    if not business:
        return None
    provider = str(data.get("provider") or "live")
    return ToolResult(
        tool="get_company_overview",
        args={"symbol": data["symbol"]},
        summary=business,
        numbers=[],
        raw={
            "symbol": data["symbol"],
            "name": data["name"],
            "industry": data.get("industry"),
            "business": business,
            "provider": provider,
        },
    )
