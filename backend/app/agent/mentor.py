from __future__ import annotations

import os
from typing import Any

from app.domain.models import InvestorProfile, ReviewResult, ThesisCard


def _has_llm() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def mock_coach_reply(message: str, profile: InvestorProfile) -> str:
    bits = [
        "这是原则教练模式（未调用行情/财报工具）。",
        "先对齐框架，再谈具体标的。",
    ]
    if not profile.goals and not profile.horizon and not profile.risk_tolerance:
        bits.append(
            "你的档案几乎是空的。想往下聊仓位或出手，我需要先知道："
            "投资目标、期限、能承受的回撤、能力圈、明确禁忌。"
        )
    else:
        bits.append(
            f"已记录：目标={profile.goals or '未填'}，期限={profile.horizon or '未填'}，"
            f"风险={profile.risk_tolerance or '未填'}，"
            f"能力圈={profile.circle_of_competence or '未填'}。"
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


def llm_reply(system: str, user: str) -> str:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    model = os.environ.get("OPENAI_MODEL", "deepseek-v4-pro")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "base_url": base,
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }
    llm = ChatOpenAI(**kwargs)
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(resp.content)


SYSTEM_BROAD = (
    "你是个人价值投资导师，引导原则与纪律，不荐股、不承诺收益、不自动交易。"
    "当前是宽泛话题模式：禁止引用具体行情数字；可追问档案缺口。"
)

SYSTEM_COMPANY = (
    "你是个人价值投资导师。根据给定的结构化审查结果与工具证据回复；"
    "禁止编造未在证据中出现的数字；不做精确内在价值定价；人做决策。"
)


def coach_reply(message: str, profile: InvestorProfile) -> str:
    if not _has_llm():
        return mock_coach_reply(message, profile)
    ctx = (
        f"档案：{profile.model_dump_json()}\n"
        f"用户：{message}\n"
        "用简洁中文引导，可列 2-4 个追问。"
    )
    return llm_reply(SYSTEM_BROAD, ctx)


def company_reply(
    message: str,
    review: ReviewResult,
    thesis: ThesisCard,
) -> str:
    if not _has_llm():
        return mock_company_reply(message, review, thesis)
    ctx = (
        f"用户：{message}\n"
        f"审查：{review.model_dump_json()}\n"
        f"论点卡：{thesis.model_dump_json()}\n"
        "用简洁中文总结审查，点明缺信息与否决/存疑项，不荐股。"
    )
    return llm_reply(SYSTEM_COMPANY, ctx)
