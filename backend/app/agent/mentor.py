from __future__ import annotations

from app.agent.llm import has_llm, invoke_llm
from app.agent.profile_memory import profile_context_block
from app.domain.models import InvestorProfile, MemoryEntry, ReviewResult, ThesisCard
from app.memory import memories_block


def mock_coach_reply(message: str, profile: InvestorProfile) -> str:
    bits = [
        "这是原则教练模式（未调用行情/财报工具）。",
        "我会记住你的档案、会话摘要与检索到的情节记忆。",
    ]
    if not profile.goals and not profile.horizon and not profile.risk_tolerance:
        bits.append(
            "你的档案几乎是空的。想往下聊仓位或出手，我需要先知道："
            "投资目标、期限、能承受的回撤、能力圈、明确禁忌；"
            "也可顺便说说收入/开销/应急金等生活财务背景。"
        )
    else:
        bits.append(
            f"已记录：目标={profile.goals or '未填'}，期限={profile.horizon or '未填'}，"
            f"风险={profile.risk_tolerance or '未填'}，"
            f"能力圈={profile.circle_of_competence or '未填'}。"
        )
        if profile.life.income_monthly or profile.life.cash_buffer:
            bits.append(
                f"生活财务：收入={profile.life.income_monthly or '未填'}，"
                f"现金缓冲={profile.life.cash_buffer or '未填'}。"
            )
    if "仓位" in message or "position" in message.lower():
        bits.append(
            "看仓位时建议按顺序问：1) 单票是否在能力圈；2) 生意是否先于价格；"
            "3) 最坏回撤是否睡得着；4) 相对现金与其他持仓的机会成本。"
            "人做决策；我只帮你拦违背原则的冲动。"
        )
    else:
        bits.append(
            "你可以继续问原则/心态/仓位纪律；若要审查具体公司，直接说「看看茅台」或 ticker。"
        )
    return "\n".join(bits)


def mock_company_reply(
    message: str,
    review: ReviewResult,
    thesis: ThesisCard,
) -> str:
    missing: list[str] = []
    for it in review.items:
        missing.extend(it.missing_info)
    missing_u = sorted(set(missing))
    lines = [
        f"已按具体公司路径审查 {review.name or review.symbol}（{review.symbol}）。",
        f"总览：{review.overall.value}。",
        review.summary,
        "关键数字均来自本次工具结果，未另行编造。",
    ]
    if missing_u:
        lines.append("仍缺信息：" + "、".join(missing_u) + "。补齐前请保持克制。")
    lines.append(f"论点卡已更新：{thesis.thesis[:120]}")
    lines.append("最终买不买由你决定。")
    return "\n".join(lines)


def llm_reply(system: str, user: str, *, trace_title: str = "导师回复") -> str:
    result = invoke_llm(
        system=system,
        user=user,
        temperature=0.2,
        trace_kind="mentor",
        trace_title=trace_title,
        stream_content=True,
    )
    return result.content


SYSTEM_BROAD = (
    "你是用户的长期个人价值投资导师助手：主要帮投资原则与纪律，"
    "也可理解其生活经济背景（收入、开销、应急金、负债等），但不要变成全能生活教练或流水账记账。"
    "你能看到：长期档案、会话摘要、检索到的情节记忆、近期对话。请衔接这些记忆，不要假装失忆。"
    "当前是宽泛话题模式：禁止编造具体行情/估值数字；可讨论原则、仓位纪律、回撤与能力圈。"
    "若用户在谈具体买卖/加减仓等操作：可以提醒「要对这家公司做原则审查需要点名标的，我才能拉行情与财报」；"
    "不要说「系统禁止看行情」——只是本轮还没锁定公司代码。"
    "不荐股、不承诺收益、不自动交易。"
)

SYSTEM_COMPANY = (
    "你是长期个人价值投资导师。根据结构化审查、工具证据、用户档案与检索记忆回复；"
    "禁止编造未在证据中出现的数字；不做精确内在价值定价；人做决策。"
    "可讨论操作纪律（加减仓、回撤边界），但数字与结论必须落在本次工具证据与审查结果上。"
    "可轻度关联用户风险承受与生活财务背景，但不要喧宾夺主。"
)


def _history_block(history: list[dict[str, str]] | None, limit: int = 12) -> str:
    if not history:
        return "（无近期对话）"
    lines = []
    for h in history[-limit:]:
        lines.append(f"{h.get('role')}: {h.get('content')}")
    return "\n".join(lines)


def _memory_context(
    *,
    session_summary: str | None,
    recalled: list[MemoryEntry] | None,
    history: list[dict[str, str]] | None,
    recent_limit: int,
) -> str:
    parts: list[str] = []
    if session_summary and session_summary.strip():
        parts.append(f"【会话摘要】\n{session_summary.strip()}")
    parts.append(memories_block(recalled or []))
    parts.append("【近期对话】\n" + _history_block(history, limit=recent_limit))
    return "\n\n".join(parts)


def coach_reply(
    message: str,
    profile: InvestorProfile,
    history: list[dict[str, str]] | None = None,
    *,
    session_summary: str | None = None,
    recalled_memories: list[MemoryEntry] | None = None,
) -> str:
    if not has_llm():
        return mock_coach_reply(message, profile)
    ctx = (
        f"{profile_context_block(profile)}\n"
        f"{_memory_context(session_summary=session_summary, recalled=recalled_memories, history=history, recent_limit=12)}\n\n"
        f"【本轮用户】\n{message}\n"
        "用简洁中文引导，可列 2-4 个追问；优先引用档案与检索记忆中的既有信息。"
    )
    return llm_reply(SYSTEM_BROAD, ctx, trace_title="原则教练回复")


def company_reply(
    message: str,
    review: ReviewResult,
    thesis: ThesisCard,
    profile: InvestorProfile | None = None,
    history: list[dict[str, str]] | None = None,
    *,
    session_summary: str | None = None,
    recalled_memories: list[MemoryEntry] | None = None,
) -> str:
    if not has_llm():
        return mock_company_reply(message, review, thesis)
    profile_bit = profile_context_block(profile) if profile else ""
    ctx = (
        f"{profile_bit}\n"
        f"{_memory_context(session_summary=session_summary, recalled=recalled_memories, history=history, recent_limit=8)}\n\n"
        f"用户：{message}\n"
        f"审查：{review.model_dump_json()}\n"
        f"论点卡：{thesis.model_dump_json()}\n"
        "用简洁中文总结审查，点明缺信息与否决/存疑项，不荐股。"
    )
    return llm_reply(SYSTEM_COMPANY, ctx, trace_title="公司审查回复")
