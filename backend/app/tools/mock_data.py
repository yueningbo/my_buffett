from __future__ import annotations

from typing import Any

# Minimal mock universe for happy-path demos (CN names + tickers).
MOCK_COMPANIES: dict[str, dict[str, Any]] = {
    "600519": {
        "symbol": "600519",
        "name": "贵州茅台",
        "aliases": ["茅台", "贵州茅台", "maotai"],
        "industry": "白酒",
        "business": "主营白酒酿造与销售，核心单品飞天茅台，品牌与定价权较强。",
        "last_price": 1680.0,
        "currency": "CNY",
        "pe_ttm": 28.5,
        "roe_pct": 32.1,
        "gross_margin_pct": 91.2,
        "revenue_yi": 750.0,
        "net_profit_yi": 370.0,
    },
    "000858": {
        "symbol": "000858",
        "name": "五粮液",
        "aliases": ["五粮液", "wuliangye"],
        "industry": "白酒",
        "business": "浓香型白酒龙头之一，品牌矩阵覆盖高端与次高端。",
        "last_price": 145.0,
        "currency": "CNY",
        "pe_ttm": 18.2,
        "roe_pct": 22.0,
        "gross_margin_pct": 75.0,
        "revenue_yi": 860.0,
        "net_profit_yi": 300.0,
    },
    "AAPL": {
        "symbol": "AAPL",
        "name": "Apple",
        "aliases": ["苹果", "apple", "aapl"],
        "industry": "消费电子",
        "business": "设计并销售 iPhone、Mac、服务订阅等，生态与现金流强。",
        "last_price": 190.0,
        "currency": "USD",
        "pe_ttm": 29.0,
        "roe_pct": 147.0,
        "gross_margin_pct": 46.0,
        "revenue_yi": None,
        "revenue_b_usd": 383.0,
        "net_profit_b_usd": 97.0,
    },
    "00700": {
        "symbol": "00700",
        "name": "腾讯控股",
        "aliases": ["腾讯", "tencent", "0700.HK", "00700.HK", "hk00700"],
        "industry": "互联网",
        "business": "社交、游戏、金融科技与云服务等，港交所上市。",
        "last_price": 470.0,
        "currency": "HKD",
        "pe_ttm": 16.5,
        "roe_pct": 21.0,
        "gross_margin_pct": 56.0,
        "revenue_yi": 6600.0,
        "net_profit_yi": 1900.0,
    },
    "09988": {
        "symbol": "09988",
        "name": "阿里巴巴-W",
        "aliases": ["阿里", "阿里巴巴", "alibaba", "9988.HK", "09988.HK"],
        "industry": "电商",
        "business": "电商、云与本地生活等，港交所上市。",
        "last_price": 110.0,
        "currency": "HKD",
        "pe_ttm": 19.0,
        "roe_pct": 10.0,
        "gross_margin_pct": 40.0,
        "revenue_yi": 9000.0,
        "net_profit_yi": 800.0,
    },
}


def resolve_symbol(text: str) -> tuple[str, dict[str, Any]] | None:
    """Resolve ticker or Chinese/English alias from free text."""
    lowered = text.lower()
    # Direct ticker tokens
    for symbol, data in MOCK_COMPANIES.items():
        if symbol.lower() in lowered.split() or symbol in text:
            return symbol, data
        for alias in data["aliases"]:
            if alias.lower() in lowered:
                return symbol, data
    # Bare 6-digit CN / 5-digit HK in mock universe
    import re

    m = re.search(r"\b(\d{6})\b", text)
    if m and m.group(1) in MOCK_COMPANIES:
        sym = m.group(1)
        return sym, MOCK_COMPANIES[sym]
    m = re.search(r"\b(\d{5})\b", text) or re.search(r"\b(\d{1,5})\.HK\b", text, re.I)
    if m:
        from app.tools.cn_a_share import normalize_hk_symbol

        hk = normalize_hk_symbol(m.group(0) if ".HK" in m.group(0).upper() else m.group(1))
        if hk and hk in MOCK_COMPANIES:
            return hk, MOCK_COMPANIES[hk]
    return None
