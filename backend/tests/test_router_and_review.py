from __future__ import annotations

from app.agent.graph import run_turn
from app.agent.router import route_message
from app.domain.models import InvestorProfile, Position
from app.principles.engine import review_symbol
from app.tools.contracts import run_tool
from app.tools.mock_data import resolve_symbol
from app.domain.models import EvidenceBundle


def test_route_broad():
    d = route_message("我该怎么看仓位？")
    assert d.mode == "broad"
    assert d.symbol is None


def test_route_company_alias():
    d = route_message("看看茅台")
    assert d.mode == "company"
    assert d.symbol == "600519"


def test_route_company_ticker():
    d = route_message("分析 600519 是否值得继续持有")
    assert d.mode == "company"
    assert d.symbol == "600519"


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
