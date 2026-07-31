"""Anti-hallucination / guardrail evals for the mentor stack."""

from __future__ import annotations

import re

import pytest

from app.agent.graph import run_turn
from app.agent.router import heuristic_route
from app.domain.models import EvidenceBundle, InvestorProfile
from app.memory import should_write_memories
from app.principles.engine import review_symbol
from app.tools.contracts import run_tool


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "mock")


def test_eval_broad_never_calls_tools(store):
    for msg in ("你好", "我该怎么看仓位？", "价值投资最重要的原则"):
        resp = run_turn(msg, store=store)
        assert resp.mode == "broad", msg
        assert resp.tool_calls == []
        assert resp.review is None


def test_eval_review_numbers_subset_of_tools():
    results = [
        run_tool("get_company_overview", mode="company", symbol="600519"),
        run_tool("get_quote", mode="company", symbol="600519"),
        run_tool("get_financials_snapshot", mode="company", symbol="600519"),
    ]
    evidence = EvidenceBundle(symbol="600519", name="贵州茅台", tool_results=results)
    review = review_symbol(evidence, InvestorProfile())
    allowed = {n.key for n in evidence.all_numbers()}
    cited = review.cited_number_keys()
    assert cited
    assert cited.issubset(allowed)


def test_eval_tool_sources_are_labeled():
    q = run_tool("get_quote", mode="company", symbol="AAPL")
    assert q.numbers
    assert all(":" in n.source for n in q.numbers)


def test_eval_company_turn_grounded(store):
    resp = run_turn("看看茅台", store=store)
    assert resp.mode == "company"
    assert resp.tool_calls
    assert resp.review is not None
    # Collect tool numbers from a fresh call matching tool_calls
    allowed: set[str] = set()
    for name in resp.tool_calls:
        tr = run_tool(name, mode="company", symbol="600519")
        allowed |= {n.key for n in tr.numbers}
    assert resp.review.cited_number_keys().issubset(allowed)


def test_eval_reply_does_not_invent_price_when_mock_coach(store):
    """Mock coach path must not emit fabricated market prices."""
    resp = run_turn("我该怎么看仓位？", store=store)
    # crude: no currency-looking price patterns required from tools
    assert not re.search(r"最新价|PE\(TTM\)\s*=\s*\d", resp.reply)


def test_eval_memory_skip_on_greeting():
    assert should_write_memories("你好") is False
    assert should_write_memories("hello") is False
    assert should_write_memories("我想调整仓位因为风险承受变了") is True


def test_eval_heuristic_hello_not_ticker():
    assert heuristic_route("hello").mode == "broad"
