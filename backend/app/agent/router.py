from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.tools.mock_data import resolve_symbol

Mode = Literal["broad", "company"]

_LOOK_PATTERNS = [
    re.compile(r"看看\s*([^\s，。,.！!？?]+)"),
    re.compile(r"分析\s*([^\s，。,.！!？?]+)"),
    re.compile(r"研究\s*([^\s，。,.！!？?]+)"),
    re.compile(r"(?:review|analyze|look\s+at)\s+([A-Za-z0-9\.]+)", re.I),
]


@dataclass
class RouteDecision:
    mode: Mode
    symbol: str | None = None
    name: str | None = None
    reason: str = ""


def route_message(message: str) -> RouteDecision:
    resolved = resolve_symbol(message)
    if resolved:
        symbol, data = resolved
        return RouteDecision(
            mode="company",
            symbol=symbol,
            name=data.get("name"),
            reason="matched_symbol_or_alias",
        )

    for pat in _LOOK_PATTERNS:
        m = pat.search(message)
        if m:
            token = m.group(1)
            resolved = resolve_symbol(token)
            if resolved:
                symbol, data = resolved
                return RouteDecision(
                    mode="company",
                    symbol=symbol,
                    name=data.get("name"),
                    reason="look_pattern",
                )
            # Unknown ticker-like token still company mode but tools may fail
            if re.fullmatch(r"\d{6}|[A-Za-z]{1,5}", token):
                return RouteDecision(
                    mode="company",
                    symbol=token.upper() if token.isalpha() else token,
                    reason="unknown_ticker_token",
                )

    return RouteDecision(mode="broad", reason="no_symbol")
