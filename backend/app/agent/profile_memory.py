"""Extract / merge / persist investor + life-finance profile from user utterances."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agent.llm import get_chat_model, has_llm
from app.domain.models import InvestorProfile, Position, utc_now

_EXTRACT_SYSTEM = """你是长期助手的档案抽取器（侧重投资，也记生活经济背景）。
从「本轮用户发言」提取增量更新，只回复一个 JSON 对象（必须含 json 字样，不要 markdown）：
{
  "goals": null或字符串,
  "horizon": null或字符串,
  "risk_tolerance": null或字符串,
  "circle_of_competence": null或字符串数组,
  "taboos": null或字符串数组,
  "positions": null或[{"symbol":"600519","name":null,"weight_pct":null,"cost":null,"notes":null}],
  "notes": null或字符串,
  "life": {
    "income_monthly": null或字符串,
    "expenses_monthly": null或字符串,
    "emergency_fund": null或字符串,
    "cash_buffer": null或字符串,
    "liabilities": null或字符串数组,
    "dependents": null或字符串,
    "life_goals": null或字符串,
    "notes": null或字符串
  },
  "changed_fields": ["goals", "life.income_monthly", ...]
}

规则：
- 没提到的字段一律 null，不要编造。
- life.* 用于工资/开销/应急金/负债/家庭负担等；仍服务投资决策，不是流水账。
- changed_fields：本轮实际写入的字段路径；无更新则为 []。
"""

_LIFE_KEYS = (
    "income_monthly",
    "expenses_monthly",
    "emergency_fund",
    "cash_buffer",
    "dependents",
    "life_goals",
    "notes",
)


class LifePatch(BaseModel):
    income_monthly: str | None = None
    expenses_monthly: str | None = None
    emergency_fund: str | None = None
    cash_buffer: str | None = None
    liabilities: list[str] | None = None
    dependents: str | None = None
    life_goals: str | None = None
    notes: str | None = None


class ProfilePatch(BaseModel):
    goals: str | None = None
    horizon: str | None = None
    risk_tolerance: str | None = None
    circle_of_competence: list[str] | None = None
    taboos: list[str] | None = None
    positions: list[Position] | None = None
    notes: str | None = None
    life: LifePatch | None = None
    changed_fields: list[str] = Field(default_factory=list)


def _uniq_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        key = x.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def merge_profile(profile: InvestorProfile, patch: ProfilePatch) -> tuple[InvestorProfile, list[str]]:
    data = profile.model_dump()
    changed: list[str] = []

    for key in ("goals", "horizon", "risk_tolerance", "notes"):
        val = getattr(patch, key)
        if val is not None and str(val).strip():
            data[key] = str(val).strip()
            changed.append(key)

    if patch.circle_of_competence is not None:
        data["circle_of_competence"] = _uniq_keep_order(
            list(data.get("circle_of_competence") or []) + list(patch.circle_of_competence)
        )
        if patch.circle_of_competence:
            changed.append("circle_of_competence")

    if patch.taboos is not None:
        data["taboos"] = _uniq_keep_order(list(data.get("taboos") or []) + list(patch.taboos))
        if patch.taboos:
            changed.append("taboos")

    if patch.positions is not None and patch.positions:
        by_sym = {p["symbol"]: p for p in (data.get("positions") or [])}
        for pos in patch.positions:
            by_sym[pos.symbol] = pos.model_dump()
        data["positions"] = list(by_sym.values())
        changed.append("positions")

    if patch.life is not None:
        life = dict(data.get("life") or {})
        for key in _LIFE_KEYS:
            val = getattr(patch.life, key)
            if val is not None and str(val).strip():
                life[key] = str(val).strip()
                changed.append(f"life.{key}")
        if patch.life.liabilities is not None:
            life["liabilities"] = _uniq_keep_order(
                list(life.get("liabilities") or []) + list(patch.life.liabilities)
            )
            if patch.life.liabilities:
                changed.append("life.liabilities")
        data["life"] = life

    data["updated_at"] = utc_now()
    if patch.changed_fields:
        # Keep extractor's list when provided, still require merge actually applied something.
        changed = _uniq_keep_order(list(patch.changed_fields) + changed)
    return InvestorProfile.model_validate(data), _uniq_keep_order(changed)


def heuristic_extract(message: str) -> ProfilePatch:
    text = message.strip()
    patch = ProfilePatch()
    changed: list[str] = []
    life = LifePatch()

    if any(k in text for k in ("目标", "增值", "财富自由", "退休", "收益")):
        patch.goals = text if len(text) < 200 else text[:200]
        changed.append("goals")

    m = re.search(r"(无限期|长期|短线|\d+\s*年|\d+\s*个月)", text)
    if m or "期限" in text or "时间范围" in text:
        patch.horizon = m.group(0) if m else text[:120]
        changed.append("horizon")

    if any(k in text for k in ("风险", "回撤", "失眠", "承受")):
        patch.risk_tolerance = text[:200]
        changed.append("risk_tolerance")

    circles = [tag for tag in ("白酒", "消费", "科技", "银行", "医药", "能源", "地产", "制造") if tag in text]
    if "能力圈" in text or circles:
        if circles:
            patch.circle_of_competence = circles
            changed.append("circle_of_competence")

    if any(k in text for k in ("工资", "收入", "月入")):
        life.income_monthly = text[:120]
        changed.append("life.income_monthly")
    if any(k in text for k in ("开销", "支出", "生活费")):
        life.expenses_monthly = text[:120]
        changed.append("life.expenses_monthly")
    if any(k in text for k in ("应急", "现金", "活期", "存款")):
        life.cash_buffer = text[:120]
        changed.append("life.cash_buffer")
    if any(k in text for k in ("房贷", "车贷", "负债", "欠款")):
        life.liabilities = ["（见对话）"]
        changed.append("life.liabilities")

    if any(getattr(life, k) is not None for k in _LIFE_KEYS) or life.liabilities:
        patch.life = life

    patch.changed_fields = changed
    return patch


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)


def llm_extract(message: str, profile: InvestorProfile) -> ProfilePatch:
    from app.agent.llm import invoke_llm
    from app.agent.trace import progress

    user = (
        f"当前档案：{profile.model_dump_json()}\n"
        f"本轮用户发言：{message.strip()}\n"
        "只输出档案增量 JSON。"
    )
    progress("更新档案中…")
    result = invoke_llm(
        system=_EXTRACT_SYSTEM,
        user=user,
        temperature=0.0,
        trace_kind="extract",
        trace_title="档案抽取",
    )
    data = _parse_json_object(result.content)
    return ProfilePatch.model_validate(data)


def extract_profile_patch(message: str, profile: InvestorProfile) -> ProfilePatch:
    if not message.strip():
        return ProfilePatch()
    if has_llm():
        try:
            return llm_extract(message, profile)
        except Exception:
            return heuristic_extract(message)
    return heuristic_extract(message)


def profile_context_block(profile: InvestorProfile) -> str:
    """Compact memory block for prompts."""
    return (
        "【长期档案·投资】\n"
        f"{profile.model_dump_json(exclude={'updated_at'}, indent=2)}\n"
    )
