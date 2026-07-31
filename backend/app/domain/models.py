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


class InvestorProfile(BaseModel):
    goals: str | None = None
    horizon: str | None = None
    risk_tolerance: str | None = None
    circle_of_competence: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    positions: list[Position] = Field(default_factory=list)
    notes: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


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
    tool_calls: list[str] = Field(default_factory=list)
    review: ReviewResult | None = None
    thesis: ThesisCard | None = None
    profile: InvestorProfile | None = None
