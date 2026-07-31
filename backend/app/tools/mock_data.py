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
    # Bare 6-digit CN ticker
    import re

    m = re.search(r"\b(\d{6})\b", text)
    if m and m.group(1) in MOCK_COMPANIES:
        sym = m.group(1)
        return sym, MOCK_COMPANIES[sym]
    return None
