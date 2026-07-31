from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.mentor import coach_reply, company_reply
from app.agent.profile_memory import extract_profile_patch, merge_profile
from app.agent.router import route_message
from app.agent.trace import capture_trace, format_trace, was_streamed
from app.domain.models import (
    ChatResponse,
    EvidenceBundle,
    InvestorProfile,
    MemoryEntry,
    ReviewResult,
    ThesisCard,
    utc_now,
)
from app.memory import recall_memories
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
    route_reason: str
    candidates: list[dict[str, str]]
    needs_clarify: bool
    profile: InvestorProfile
    profile_updates: list[str]
    session_summary: str
    recalled_memories: list[MemoryEntry]
    tool_calls: list[str]
    evidence: EvidenceBundle | None
    review: ReviewResult | None
    thesis: ThesisCard | None
    reply: str
    error: str | None


COMPANY_TOOLS = ["get_company_overview", "get_quote", "get_financials_snapshot"]


def node_route(state: GraphState) -> dict[str, Any]:
    decision = route_message(state["message"], state.get("history") or [])
    out: dict[str, Any] = {
        "mode": decision.mode,
        "symbol": decision.symbol,
        "name": decision.name,
        "route_reason": decision.reason,
        "candidates": list(decision.candidates or []),
        "needs_clarify": bool(decision.needs_clarify),
        "tool_calls": [],
        "error": None,
    }
    # Broad turns must not inherit company artifacts from a prior invoke/session.
    if decision.mode == "broad":
        out.update(
            {
                "symbol": None,
                "name": None,
                "candidates": [],
                "needs_clarify": False,
                "evidence": None,
                "review": None,
                "thesis": None,
            }
        )
    return out


def node_load_profile(state: GraphState) -> dict[str, Any]:
    store = get_store()
    profile = store.get_profile()
    patch = extract_profile_patch(state["message"], profile)
    merged, changed = merge_profile(profile, patch)
    if changed:
        store.save_profile(merged)
        profile = merged
    # Episodic recall (BM25). Prefer precomputed list from run_turn if provided.
    recalled = state.get("recalled_memories")
    if recalled is None:
        recalled = recall_memories(store, state["message"], k=5)
    return {
        "profile": profile,
        "profile_updates": changed,
        "recalled_memories": recalled,
    }


def node_coach(state: GraphState) -> dict[str, Any]:
    # Hard guard: broad never calls tools
    reply = coach_reply(
        state["message"],
        state["profile"],
        history=state.get("history") or [],
        session_summary=state.get("session_summary") or "",
        recalled_memories=state.get("recalled_memories") or [],
    )
    updates = state.get("profile_updates") or []
    if updates:
        reply = f"（已写入档案：{', '.join(updates)}）\n" + reply
    return {"reply": reply, "tool_calls": [], "review": None, "thesis": None}


def node_research(state: GraphState) -> dict[str, Any]:
    from app.agent.trace import progress

    symbol = state.get("symbol")
    if not symbol:
        return {
            "error": "company mode without symbol",
            "reply": "",
            "tool_calls": [],
            "needs_clarify": True,
        }

    progress(f"拉取 {symbol} 行情/财报…")
    results = []
    calls: list[str] = []
    try:
        for tool_name in COMPANY_TOOLS:
            tr = run_tool(tool_name, mode="company", symbol=symbol)
            results.append(tr)
            calls.append(tool_name)
    except KeyError:
        return {
            "error": "unknown_symbol",
            "reply": (
                f"标的 {symbol} 暂无可用数据（live 失败且不在 mock 宇宙）。"
                "可换一个代码再试，或检查网络。"
            ),
            "tool_calls": [],
            "evidence": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "error": "tool_failure",
            "reply": f"拉取 {symbol} 证据失败：{exc}",
            "tool_calls": calls,
            "evidence": None,
        }

    name = state.get("name")
    canon = symbol
    for tr in results:
        name = name or tr.raw.get("name")
        canon = str(tr.raw.get("symbol") or canon)
    if not name and symbol in MOCK_COMPANIES:
        name = MOCK_COMPANIES[symbol]["name"]
        canon = MOCK_COMPANIES[symbol]["symbol"]

    evidence = EvidenceBundle(
        symbol=canon,
        name=name,
        tool_results=results,
    )
    return {
        "evidence": evidence,
        "tool_calls": calls,
        "name": name,
        "symbol": canon,
        "error": None,
    }


def node_clarify(state: GraphState) -> dict[str, Any]:
    """Company intent but symbol not locked — ask, don't pretend tools are forbidden."""
    cands = state.get("candidates") or []
    if cands:
        lines = []
        for i, c in enumerate(cands[:5], 1):
            mkt = c.get("market") or ""
            tag = f" · {mkt}" if mkt else ""
            lines.append(f"{i}. {c.get('name')}（{c.get('symbol')}{tag}）")
        reply = (
            "你在聊具体公司，拉行情/做原则审查前需要先锁定标的。我搜到这些候选：\n"
            + "\n".join(lines)
            + "\n请直接回复代码（或更准确的公司名）。确认后我会拉数并做审查。"
        )
    else:
        reply = (
            "你在聊具体公司或操作，但我还没锁定交易代码，所以这轮还不能引用行情数字。\n"
            "请发代码（如 600519、00700.HK）或更准确的公司全称；"
            "锁定后我会拉概况/报价/财务快照并做原则审查。\n"
            "若你只是想谈仓位纪律、能力圈、回撤边界，也可以继续说——那种讨论不依赖即时行情。"
        )
    return {
        "reply": reply,
        "tool_calls": [],
        "review": None,
        "thesis": None,
        "error": "need_symbol",
        "needs_clarify": True,
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
    reply = company_reply(
        state["message"],
        review,
        thesis,
        profile=state.get("profile"),
        history=state.get("history") or [],
        session_summary=state.get("session_summary") or "",
        recalled_memories=state.get("recalled_memories") or [],
    )
    updates = state.get("profile_updates") or []
    if updates:
        reply = f"（已写入档案：{', '.join(updates)}）\n" + reply
    return {"reply": reply}


def _after_route(state: GraphState) -> str:
    if state.get("mode") == "broad":
        return "coach"
    if state.get("symbol"):
        return "research"
    return "clarify"


def build_graph():
    g: StateGraph = StateGraph(GraphState)
    g.add_node("route", node_route)
    g.add_node("load_profile", node_load_profile)
    g.add_node("coach", node_coach)
    g.add_node("clarify", node_clarify)
    g.add_node("research", node_research)
    g.add_node("review", node_review)
    g.add_node("thesis", node_thesis)
    g.add_node("company_reply", node_company_reply)

    g.add_edge(START, "route")
    g.add_edge("route", "load_profile")
    g.add_conditional_edges(
        "load_profile",
        _after_route,
        {"coach": "coach", "research": "research", "clarify": "clarify"},
    )
    g.add_edge("coach", END)
    g.add_edge("clarify", END)
    g.add_edge("research", "review")
    g.add_edge("review", "thesis")
    g.add_edge("thesis", "company_reply")
    g.add_edge("company_reply", END)
    return g.compile()


_GRAPH = None


def reset_graph_for_tests() -> None:
    global _GRAPH
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
    *,
    session_summary: str = "",
    recalled_memories: list[MemoryEntry] | None = None,
) -> ChatResponse:
    if store is not None:
        from app.store import json_store as js

        js._store = store  # noqa: SLF001 — test injection

    graph = get_graph()
    with capture_trace() as events:
        final = graph.invoke(
            {
                "message": message,
                "history": history or [],
                "tool_calls": [],
                "profile_updates": [],
                "session_summary": session_summary,
                "recalled_memories": recalled_memories,
            }
        )
        if final.get("tool_calls"):
            from app.agent.trace import add_trace

            add_trace(
                "tool",
                "本轮工具",
                detail=", ".join(final.get("tool_calls") or []),
            )
        if final.get("review"):
            from app.agent.trace import add_trace

            review = final["review"]
            add_trace(
                "review",
                "原则审查",
                detail=review.summary,
                overall=review.overall.value,
            )

    return ChatResponse(
        reply=final.get("reply") or "（无回复）",
        mode=final.get("mode") or "broad",
        symbol=final.get("symbol"),
        route_reason=final.get("route_reason"),
        profile_updates=list(final.get("profile_updates") or []),
        tool_calls=list(final.get("tool_calls") or []),
        review=final.get("review"),
        thesis=final.get("thesis"),
        profile=final.get("profile"),
        trace=format_trace(events),
        streamed=was_streamed() or any(getattr(e, "streamed", False) for e in events),
    )
