from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from app.domain.models import ToolNumber, ToolResult
from app.tools.mock_data import MOCK_COMPANIES


class ToolSpec(BaseModel):
    name: str
    description: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    modes_allowed: list[str] = Field(default_factory=lambda: ["company"])


def _company(symbol: str) -> dict[str, Any]:
    data = MOCK_COMPANIES.get(symbol.upper()) or MOCK_COMPANIES.get(symbol)
    if not data:
        raise KeyError(f"unknown symbol: {symbol}")
    return data


def get_quote(symbol: str) -> ToolResult:
    c = _company(symbol)
    price = float(c["last_price"])
    unit = str(c.get("currency") or "")
    return ToolResult(
        tool="get_quote",
        args={"symbol": c["symbol"]},
        summary=f"{c['name']}({c['symbol']}) 最新价（mock）{price} {unit}",
        numbers=[
            ToolNumber(
                key="last_price",
                value=price,
                unit=unit,
                source="mock:get_quote",
            )
        ],
        raw={"symbol": c["symbol"], "name": c["name"], "currency": unit},
    )


def get_financials_snapshot(symbol: str) -> ToolResult:
    c = _company(symbol)
    numbers: list[ToolNumber] = [
        ToolNumber(
            key="pe_ttm",
            value=float(c["pe_ttm"]),
            unit="x",
            source="mock:get_financials_snapshot",
        ),
        ToolNumber(
            key="roe_pct",
            value=float(c["roe_pct"]),
            unit="%",
            source="mock:get_financials_snapshot",
        ),
        ToolNumber(
            key="gross_margin_pct",
            value=float(c["gross_margin_pct"]),
            unit="%",
            source="mock:get_financials_snapshot",
        ),
    ]
    if c.get("revenue_yi") is not None:
        numbers.append(
            ToolNumber(
                key="revenue_yi",
                value=float(c["revenue_yi"]),
                unit="亿元",
                source="mock:get_financials_snapshot",
            )
        )
    if c.get("net_profit_yi") is not None:
        numbers.append(
            ToolNumber(
                key="net_profit_yi",
                value=float(c["net_profit_yi"]),
                unit="亿元",
                source="mock:get_financials_snapshot",
            )
        )
    if c.get("revenue_b_usd") is not None:
        numbers.append(
            ToolNumber(
                key="revenue_b_usd",
                value=float(c["revenue_b_usd"]),
                unit="十亿美元",
                source="mock:get_financials_snapshot",
            )
        )
    summary = (
        f"{c['name']} 财务快照（mock）：PE(TTM)={c['pe_ttm']}x，"
        f"ROE={c['roe_pct']}%，毛利率={c['gross_margin_pct']}%"
    )
    return ToolResult(
        tool="get_financials_snapshot",
        args={"symbol": c["symbol"]},
        summary=summary,
        numbers=numbers,
        raw={
            "symbol": c["symbol"],
            "name": c["name"],
            "industry": c.get("industry"),
        },
    )


def get_company_overview(symbol: str) -> ToolResult:
    c = _company(symbol)
    return ToolResult(
        tool="get_company_overview",
        args={"symbol": c["symbol"]},
        summary=c["business"],
        numbers=[],
        raw={
            "symbol": c["symbol"],
            "name": c["name"],
            "industry": c["industry"],
            "business": c["business"],
        },
    )


TOOL_IMPLS: dict[str, Callable[..., ToolResult]] = {
    "get_quote": get_quote,
    "get_financials_snapshot": get_financials_snapshot,
    "get_company_overview": get_company_overview,
}

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="get_quote",
        description="获取标的最新价（mock）",
        args_schema={"symbol": "string"},
        modes_allowed=["company"],
    ),
    ToolSpec(
        name="get_financials_snapshot",
        description="获取财务快照：PE/ROE/毛利率等（mock）",
        args_schema={"symbol": "string"},
        modes_allowed=["company"],
    ),
    ToolSpec(
        name="get_company_overview",
        description="获取公司业务与行业概述（mock）",
        args_schema={"symbol": "string"},
        modes_allowed=["company"],
    ),
]


def run_tool(name: str, *, mode: str, symbol: str) -> ToolResult:
    spec = next((s for s in TOOL_SPECS if s.name == name), None)
    if spec is None:
        raise ValueError(f"unknown tool: {name}")
    if mode not in spec.modes_allowed:
        raise PermissionError(f"tool {name} not allowed in mode={mode}")
    impl = TOOL_IMPLS[name]
    return impl(symbol)
