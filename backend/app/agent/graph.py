from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.mentor import coach_reply, company_reply
from app.agent.router import route_message
from app.domain.models import (
    ChatResponse,
    EvidenceBundle,
    InvestorProfile,
    ReviewResult,
    ThesisCard,
    utc_now,
)
from app.principles.engine import review_symbol
from app.store.json_store import Store, get_store
from app.tools.contracts import run_tool
from app.tools.mock_data import MOCK_COMPANIES


class GraphState(TypedDict, total=False):
    message: str
    history: list[dict[str, str]]
    mode: Literal["broad", "company"]
    symbol: str | None
    name: str | None
    profile: InvestorProfile
    tool_calls: list[str]
    evidence: EvidenceBundle | None
    review: ReviewResult | None
    thesis: ThesisCard | None
    reply: str
    error: str | None


COMPANY_TOOLS = ["get_company_overview", "get_quote", "get_financials_snapshot"]


def node_route(state: GraphState) -> dict[str, Any]:
    decision = route_message(state["message"])
    return {
        "mode": decision.mode,
        "symbol": decision.symbol,
        "name": decision.name,
        "tool_calls": [],
        "error": None,
    }


def node_load_profile(state: GraphState) -> dict[str, Any]:
    store = get_store()
    return {"profile": store.get_profile()}


def node_coach(state: GraphState) -> dict[str, Any]:
    # Hard guard: broad never calls tools
    reply = coach_reply(state["message"], state["profile"])
    return {"reply": reply, "tool_calls": [], "review": None, "thesis": None}


def node_research(state: GraphState) -> dict[str, Any]:
    symbol = state.get("symbol")
    if not symbol:
        return {
            "error": "company mode without symbol",
            "reply": "我识别到你想看具体公司，但没解析到标的。请给出 ticker 或「看看茅台」。",
            "tool_calls": [],
        }
    if symbol not in MOCK_COMPANIES and symbol.upper() not in MOCK_COMPANIES:
        return {
            "error": "unknown_symbol",
            "reply": (
                f"标的 {symbol} 不在当前 mock 宇宙（600519/茅台、000858/五粮液、AAPL）。"
                "MVP 仅演示假数据。"
            ),
            "tool_calls": [],
            "evidence": None,
        }

    results = []
    calls: list[str] = []
    for tool_name in COMPANY_TOOLS:
        tr = run_tool(tool_name, mode="company", symbol=symbol)
        results.append(tr)
        calls.append(tool_name)

    meta = MOCK_COMPANIES.get(symbol) or MOCK_COMPANIES[symbol.upper()]
    evidence = EvidenceBundle(
        symbol=meta["symbol"],
        name=meta["name"],
        tool_results=results,
    )
    return {
        "evidence": evidence,
        "tool_calls": calls,
        "name": meta["name"],
        "symbol": meta["symbol"],
        "error": None,
    }


def node_review(state: GraphState) -> dict[str, Any]:
    if state.get("error") or not state.get("evidence"):
        return {}
    review = review_symbol(state["evidence"], state["profile"])
    return {"review": review}


def node_thesis(state: GraphState) -> dict[str, Any]:
    review = state.get("review")
    if not review:
        return {}
    store = get_store()
    store.save_review(review)
    existing = store.get_thesis(review.symbol)
    missing: list[str] = []
    for it in review.items:
        missing.extend(it.missing_info)
    open_q = sorted(set(missing))
    assumptions = [
        f"{it.principle_id}: {it.verdict.value}"
        for it in review.items
        if it.verdict.value != "pass"
    ]
    thesis_text = (
        existing.thesis
        if existing and existing.thesis
        else f"待你确认的研究草稿：{review.name} — 审查总览 {review.overall.value}。"
    )
    card = ThesisCard(
        symbol=review.symbol,
        name=review.name,
        thesis=thesis_text,
        key_assumptions=assumptions or (existing.key_assumptions if existing else []),
        open_questions=open_q,
        last_review=review,
        todos=[f"补齐：{q}" for q in open_q[:5]],
        updated_at=utc_now(),
    )
    store.upsert_thesis(card)
    return {"thesis": card}


def node_company_reply(state: GraphState) -> dict[str, Any]:
    if state.get("reply") and state.get("error"):
        return {}
    review = state.get("review")
    thesis = state.get("thesis")
    if not review or not thesis:
        return {}
    reply = company_reply(state["message"], review, thesis)
    return {"reply": reply}


def _after_route(state: GraphState) -> str:
    return "coach" if state.get("mode") == "broad" else "research"


def build_graph():
    g: StateGraph = StateGraph(GraphState)
    g.add_node("route", node_route)
    g.add_node("load_profile", node_load_profile)
    g.add_node("coach", node_coach)
    g.add_node("research", node_research)
    g.add_node("review", node_review)
    g.add_node("thesis", node_thesis)
    g.add_node("company_reply", node_company_reply)

    g.add_edge(START, "route")
    g.add_edge("route", "load_profile")
    g.add_conditional_edges(
        "load_profile",
        _after_route,
        {"coach": "coach", "research": "research"},
    )
    g.add_edge("coach", END)
    g.add_edge("research", "review")
    g.add_edge("review", "thesis")
    g.add_edge("thesis", "company_reply")
    g.add_edge("company_reply", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_turn(
    message: str,
    history: list[dict[str, str]] | None = None,
    store: Store | None = None,
) -> ChatResponse:
    if store is not None:
        from app.store import json_store as js

        js._store = store  # noqa: SLF001 — test injection

    graph = get_graph()
    final = graph.invoke(
        {
            "message": message,
            "history": history or [],
            "tool_calls": [],
        }
    )
    return ChatResponse(
        reply=final.get("reply") or "（无回复）",
        mode=final.get("mode") or "broad",
        symbol=final.get("symbol"),
        tool_calls=list(final.get("tool_calls") or []),
        review=final.get("review"),
        thesis=final.get("thesis"),
        profile=final.get("profile"),
    )
