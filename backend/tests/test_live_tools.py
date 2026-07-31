from __future__ import annotations

from app.domain.models import ToolNumber, ToolResult
from app.tools import contracts


def test_live_path_preferred_when_available(monkeypatch):
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "auto")

    def fake_live_quote(symbol: str):
        return ToolResult(
            tool="get_quote",
            args={"symbol": symbol},
            summary=f"{symbol} live",
            numbers=[
                ToolNumber(key="last_price", value=123.0, unit="USD", source="yfinance:get_quote")
            ],
            raw={"provider": "yfinance", "symbol": symbol, "name": symbol},
        )

    monkeypatch.setattr(contracts.live_data, "live_quote", fake_live_quote)
    tr = contracts.get_quote("AAPL")
    assert tr.numbers[0].source.startswith("yfinance")
    assert tr.numbers[0].value == 123.0


def test_mock_forced(monkeypatch):
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "mock")
    tr = contracts.get_quote("AAPL")
    assert tr.numbers[0].source.startswith("mock")
