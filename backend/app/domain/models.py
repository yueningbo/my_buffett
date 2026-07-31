from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Verdict(str, Enum):
    PASS = "pass"
    CONCERN = "concern"
    VETO = "veto"


class Position(BaseModel):
    symbol: str
    name: str | None = None
    weight_pct: float | None = None
    cost: float | None = None
    notes: str | None = None


class LifeFinance(BaseModel):
    """生活侧经济情况 — 服务投资决策，不是记账本。"""

    income_monthly: str | None = None
    expenses_monthly: str | None = None
    emergency_fund: str | None = None
    cash_buffer: str | None = None
    liabilities: list[str] = Field(default_factory=list)
    dependents: str | None = None
    life_goals: str | None = None
    notes: str | None = None


class InvestorProfile(BaseModel):
    goals: str | None = None
    horizon: str | None = None
    risk_tolerance: str | None = None
    circle_of_competence: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    positions: list[Position] = Field(default_factory=list)
    life: LifeFinance = Field(default_factory=LifeFinance)
    notes: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    ts: datetime = Field(default_factory=utc_now)
    mode: Literal["broad", "company"] | None = None


class ChatSession(BaseModel):
    id: str
    title: str = "默认会话"
    messages: list[ChatMessage] = Field(default_factory=list)
    summary: str = ""
    summarized_until: int = 0  # number of messages already folded into summary
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def as_history_dicts(self, limit: int = 30) -> list[dict[str, str]]:
        msgs = self.messages[-limit:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    def working_context(self, recent_limit: int = 12) -> str:
        """Summary (long-term session) + recent raw turns (working memory)."""
        parts: list[str] = []
        if self.summary.strip():
            parts.append(f"【会话摘要】\n{self.summary.strip()}")
        recent = self.as_history_dicts(limit=recent_limit)
        if recent:
            lines = [f"{m['role']}: {m['content']}" for m in recent]
            parts.append("【近期对话】\n" + "\n".join(lines))
        return "\n\n".join(parts) if parts else "（无会话记忆）"


class MemoryEntry(BaseModel):
    """Episodic / semantic memory item for retrieval."""

    id: str
    text: str
    tags: list[str] = Field(default_factory=list)
    source_session: str | None = None
    kind: str = "episodic"
    created_at: datetime = Field(default_factory=utc_now)


class PrincipleItem(BaseModel):
    id: str
    statement: str
    how_to_check: str
    severity_if_fail: Verdict = Verdict.CONCERN


class ToolNumber(BaseModel):
    key: str
    value: float
    unit: str = ""
    source: str


class ToolResult(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str
    numbers: list[ToolNumber] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    symbol: str
    name: str | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)

    def all_numbers(self) -> list[ToolNumber]:
        out: list[ToolNumber] = []
        for tr in self.tool_results:
            out.extend(tr.numbers)
        return out

    def number_map(self) -> dict[str, ToolNumber]:
        return {n.key: n for n in self.all_numbers()}

    def evidence_refs(self) -> list[str]:
        refs: list[str] = []
        for tr in self.tool_results:
            refs.append(tr.tool)
            for n in tr.numbers:
                refs.append(f"{tr.tool}:{n.key}")
        return refs


class ReviewVerdict(BaseModel):
    principle_id: str
    verdict: Verdict
    rationale: str
    missing_info: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    symbol: str
    name: str | None = None
    items: list[ReviewVerdict] = Field(default_factory=list)
    overall: Verdict
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    def cited_number_keys(self) -> set[str]:
        """Keys referenced as tool:key in evidence_refs across items + top-level."""
        keys: set[str] = set()
        for ref in self.evidence_refs:
            if ":" in ref:
                keys.add(ref.split(":", 1)[1])
        for item in self.items:
            for ref in item.evidence_refs:
                if ":" in ref:
                    keys.add(ref.split(":", 1)[1])
        return keys


class ThesisCard(BaseModel):
    symbol: str
    name: str | None = None
    thesis: str = ""
    key_assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    last_review: ReviewResult | None = None
    todos: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    mode: Literal["broad", "company"]
    symbol: str | None = None
    route_reason: str | None = None
    profile_updates: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    review: ReviewResult | None = None
    thesis: ThesisCard | None = None
    profile: InvestorProfile | None = None
    trace: str | None = None
    streamed: bool = False
