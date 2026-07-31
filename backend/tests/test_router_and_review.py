from __future__ import annotations

import pytest

from app.agent.graph import run_turn
from app.agent.router import heuristic_route, route_message
from app.domain.models import EvidenceBundle, InvestorProfile, Position
from app.principles.engine import review_symbol
from app.tools.contracts import run_tool
from app.tools.mock_data import resolve_symbol


@pytest.fixture(autouse=True)
def _deterministic_no_llm(monkeypatch):
    """Unit tests use heuristic classify + mock mentor (no network)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_heuristic_greeting_is_broad():
    for msg in ("你好", "你好！", "hello", "Hi", "在吗"):
        d = heuristic_route(msg)
        assert d.mode == "broad", msg
        assert d.symbol is None


def test_hello_not_treated_as_ticker():
    """Regression: bare English greetings must not become symbol HELLO."""
    for msg in ("hello", "Hello", "hi", "hey"):
        d = heuristic_route(msg)
        assert d.mode == "broad", msg
        assert d.symbol is None
    # Override helper must ignore ungrounded English words
    from app.agent.router import _bare_ticker_override, _enrich_symbol

    assert _bare_ticker_override("hello") is None
    assert _enrich_symbol("hello", "hello") == (None, None)


def test_route_broad():
    d = route_message("我该怎么看仓位？")
    assert d.mode == "broad"
    assert d.symbol is None


def test_greeting_turn_zero_tools(store):
    resp = run_turn("你好", store=store)
    assert resp.mode == "broad"
    assert resp.tool_calls == []
    assert resp.review is None
    assert resp.symbol is None


def test_route_company_alias():
    d = route_message("看看茅台")
    assert d.mode == "company"
    assert d.symbol == "600519"


def test_route_company_ticker():
    d = route_message("分析 600519 是否值得继续持有")
    assert d.mode == "company"
    assert d.symbol == "600519"


def test_route_hk_alias_and_ticker():
    d = route_message("看看腾讯")
    assert d.mode == "company"
    assert d.symbol == "00700"
    d2 = route_message("分析 00700.HK")
    assert d2.mode == "company"
    assert d2.symbol == "00700"


def test_ungrounded_name_searches_eastmoney(monkeypatch):
    """「联邦制药」不在 mock 宇宙时，应走名称搜索而不是降级 broad。"""
    from app.agent import router as router_mod

    def fake_search(q: str):
        if "联邦制药" in q:
            return [
                {"symbol": "03933", "name": "联邦制药", "market": "HK"},
            ]
        return []

    monkeypatch.setattr("app.tools.cn_a_share.search_listed_candidates", fake_search)
    d = heuristic_route("看看联邦制药现在的情况")
    assert d.mode == "company"
    assert d.symbol == "03933"
    assert d.name == "联邦制药"

    sym, name = router_mod._enrich_symbol("看看联邦制药现在的情况", "联邦制药")
    assert sym == "03933"
    assert name == "联邦制药"


def test_company_intent_stays_company_when_unresolved(monkeypatch):
    """Company intent without a lock must clarify, never silent→broad."""
    from app.agent.graph import reset_graph_for_tests, run_turn
    from app.agent.router import RouteDecision

    def fake_route(message, history=None):
        return RouteDecision(
            mode="company",
            symbol=None,
            needs_clarify=True,
            candidates=[],
            reason="test:need_clarify",
        )

    monkeypatch.setattr("app.agent.graph.route_message", fake_route)
    reset_graph_for_tests()
    resp = run_turn("聊聊那家药企的仓位", store=None)
    assert resp.mode == "company"
    assert resp.tool_calls == []
    assert resp.review is None
    assert "锁定" in resp.reply or "代码" in resp.reply
    reset_graph_for_tests()


def test_ambiguous_candidates_clarify(monkeypatch, store):
    from app.agent.graph import reset_graph_for_tests, run_turn
    from app.agent.router import RouteDecision

    def fake_route(message, history=None):
        return RouteDecision(
            mode="company",
            symbol=None,
            needs_clarify=True,
            candidates=[
                {"symbol": "03933", "name": "联邦制药", "market": "HK"},
                {"symbol": "600000", "name": "别的公司", "market": "A"},
            ],
            reason="test:ambiguous",
        )

    monkeypatch.setattr("app.agent.graph.route_message", fake_route)
    reset_graph_for_tests()
    resp = run_turn("看看联邦", store=store)
    assert resp.mode == "company"
    assert "03933" in resp.reply
    assert resp.tool_calls == []
    reset_graph_for_tests()


def test_broad_turn_zero_tools(store):
    resp = run_turn("我该怎么看仓位？", store=store)
    assert resp.mode == "broad"
    assert resp.tool_calls == []
    assert resp.review is None
    assert "工具" in resp.reply or "原则" in resp.reply


def test_company_turn_tools_and_numbers_subset(store):
    store.save_profile(
        InvestorProfile(
            goals="长期复利",
            horizon="5年+",
            risk_tolerance="中等",
            circle_of_competence=["白酒", "消费"],
            taboos=["杠杆炒作"],
            positions=[Position(symbol="600519", name="贵州茅台", weight_pct=10)],
        )
    )
    resp = run_turn("看看茅台", store=store)
    assert resp.mode == "company"
    assert set(resp.tool_calls) == {
        "get_company_overview",
        "get_quote",
        "get_financials_snapshot",
    }
    assert resp.review is not None
    assert resp.thesis is not None

    allowed = set()
    for name in resp.tool_calls:
        tr = run_tool(name, mode="company", symbol="600519")
        for n in tr.numbers:
            allowed.add(n.key)

    cited = resp.review.cited_number_keys()
    assert cited
    assert cited.issubset(allowed)


def test_review_numbers_only_from_evidence():
    results = [
        run_tool("get_company_overview", mode="company", symbol="600519"),
        run_tool("get_quote", mode="company", symbol="600519"),
        run_tool("get_financials_snapshot", mode="company", symbol="600519"),
    ]
    evidence = EvidenceBundle(symbol="600519", name="贵州茅台", tool_results=results)
    review = review_symbol(evidence, InvestorProfile())
    allowed = {n.key for n in evidence.all_numbers()}
    assert review.cited_number_keys().issubset(allowed)


def test_tool_blocked_in_broad_mode():
    try:
        run_tool("get_quote", mode="broad", symbol="600519")
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_resolve_symbol():
    assert resolve_symbol("我想聊聊贵州茅台")[0] == "600519"
