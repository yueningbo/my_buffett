"""Intent routing: classify broad vs company; resolve symbols without silent downgrade."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.llm import has_llm
from app.tools.mock_data import resolve_symbol

Mode = Literal["broad", "company"]

_LOOK_PATTERNS = [
    re.compile(r"看看\s*([^\s，。,.！!？?]+)"),
    re.compile(r"分析\s*([^\s，。,.！!？?]+)"),
    re.compile(r"研究\s*([^\s，。,.！!？?]+)"),
    re.compile(r"(?:review|analyze|look\s+at)\s+([A-Za-z0-9\.]+)", re.I),
]

_LOOK_SUFFIX_NOISE = (
    "现在的情况",
    "目前的情况",
    "的情况",
    "现在怎么样",
    "怎么样",
    "如何",
    "目前",
    "近期",
    "现在",
    "一下",
)


def _clean_look_token(token: str) -> str:
    t = token.strip().strip("的")
    changed = True
    while changed and t:
        changed = False
        for suffix in _LOOK_SUFFIX_NOISE:
            if t.endswith(suffix) and len(t) > len(suffix):
                t = t[: -len(suffix)].strip().strip("的")
                changed = True
                break
    return t


_CLASSIFY_SYSTEM = """你是路由分类器，不是投资顾问。
根据用户这句话，判断本轮对话模式，并只回复一个 JSON 对象（必须是 json，不要 markdown）：
{"mode":"broad"|"company","symbol_hint":null|"茅台或代码","rationale":"一句理由"}

含义：
- broad：寒暄、原则、仓位纪律、心态、能力圈、泛泛「该不该投资」等，本轮不需要拉某一只股票的行情/财报。
- company：用户在讨论或要求查看/审查某一具体公司/股票（点名公司、ticker、或「看看/分析 XX」），
  或明确要看某标的的价格/PE/财报等数据。即使你不确定准确代码，只要点了公司名，仍选 company，并尽量给 symbol_hint。

若 mode=company，尽量给 symbol_hint（中文名、别名或代码）；拿不准用最接近的公司名，不要因不确定就改成 broad。
若只是打招呼或闲聊（含 hello/hi），mode 必须为 broad，symbol_hint 为 null。
不要荐股，不要输出 JSON 以外的文字。
"""


class IntentClassification(BaseModel):
    mode: Mode = Field(description="broad=原则/闲聊；company=具体标的")
    symbol_hint: str | None = Field(
        default=None,
        description="公司名、别名或 ticker；broad 时一般为 null",
    )
    rationale: str = Field(default="", description="一句简短理由")


@dataclass
class RouteDecision:
    mode: Mode
    symbol: str | None = None
    name: str | None = None
    reason: str = ""
    candidates: list[dict[str, str]] = field(default_factory=list)
    needs_clarify: bool = False


@dataclass
class ResolveResult:
    symbol: str | None = None
    name: str | None = None
    candidates: list[dict[str, str]] = field(default_factory=list)
    needs_clarify: bool = False
    query: str | None = None


def _from_resolved(resolved: tuple[str, dict], reason: str) -> RouteDecision:
    symbol, data = resolved
    return RouteDecision(
        mode="company",
        symbol=symbol,
        name=data.get("name"),
        reason=reason,
    )


def _as_cn_ticker(token: str) -> str | None:
    t = token.strip()
    return t if re.fullmatch(r"\d{6}", t) else None


def _as_hk_ticker(token: str) -> str | None:
    from app.tools.cn_a_share import normalize_hk_symbol

    return normalize_hk_symbol(token)


def _pick_from_candidates(query: str, cands: list[dict[str, str]]) -> ResolveResult:
    if not cands:
        return ResolveResult(needs_clarify=True, query=query, candidates=[])
    q = query.strip()
    exact = [c for c in cands if c.get("name") == q or c.get("symbol") == q]
    if len(exact) == 1:
        c = exact[0]
        return ResolveResult(symbol=c["symbol"], name=c["name"], candidates=cands)
    # Strong containment + unique top market
    strong = [c for c in cands if q in c.get("name", "") or c.get("name", "") in q]
    if len(strong) == 1:
        c = strong[0]
        return ResolveResult(symbol=c["symbol"], name=c["name"], candidates=cands)
    if len(cands) == 1:
        c = cands[0]
        return ResolveResult(symbol=c["symbol"], name=c["name"], candidates=cands)
    # Ambiguous → clarify (still keep top hits)
    return ResolveResult(
        needs_clarify=True,
        query=query,
        candidates=cands[:5],
    )


def _queries_to_try(message: str, hint: str | None) -> list[str]:
    out: list[str] = []
    if hint:
        cleaned = _clean_look_token(hint)
        if cleaned:
            out.append(cleaned)
    for pat in _LOOK_PATTERNS:
        m = pat.search(message or "")
        if m:
            tok = _clean_look_token(m.group(1))
            if tok and tok not in out:
                out.append(tok)
    return out


def _symbol_from_history(history: list[dict[str, str]] | None) -> ResolveResult | None:
    """Reuse a recently mentioned ticker when user says「它/这只」类跟进。"""
    if not history:
        return None
    blob = "\n".join((h.get("content") or "") for h in history[-8:])
    # Prefer explicit CN / HK codes appearing late in history
    hk_hits = re.findall(r"\b(\d{5})\.HK\b", blob, flags=re.I)
    cn_hits = re.findall(r"\b(\d{6})\b", blob)
    bare_hk = re.findall(r"\b(0\d{4})\b", blob)
    if cn_hits:
        sym = cn_hits[-1]
        return ResolveResult(symbol=sym, name=None)
    if hk_hits:
        sym = hk_hits[-1].zfill(5)
        return ResolveResult(symbol=sym, name=None)
    if bare_hk:
        return ResolveResult(symbol=bare_hk[-1], name=None)
    return None


def resolve_company_query(
    message: str,
    hint: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> ResolveResult:
    """Ground a company mention → symbol, or candidates for clarify. Never invent tickers."""
    from app.tools.cn_a_share import search_listed_candidates

    for candidate in (hint, message):
        if not candidate:
            continue
        resolved = resolve_symbol(candidate.strip())
        if resolved:
            symbol, data = resolved
            return ResolveResult(symbol=symbol, name=data.get("name"))

    for q in _queries_to_try(message, hint):
        cn = _as_cn_ticker(q)
        if cn:
            return ResolveResult(symbol=cn, name=None, query=q)
        hk = _as_hk_ticker(q)
        if hk:
            return ResolveResult(symbol=hk, name=None, query=q)
        if re.fullmatch(r"[A-Za-z]{1,5}", q):
            # Ungrounded English word — do not treat as ticker
            continue
        if 1 < len(q) <= 20:
            cands = search_listed_candidates(q)
            picked = _pick_from_candidates(q, cands)
            if picked.symbol or picked.needs_clarify:
                return picked

    # Follow-up pronouns / bare ops talk after a company turn
    hist_hit = _symbol_from_history(history)
    if hist_hit and hist_hit.symbol:
        return hist_hit

    return ResolveResult(needs_clarify=True, query=(hint or None), candidates=[])


def _enrich_symbol(message: str, hint: str | None) -> tuple[str | None, str | None]:
    """Backward-compatible helper used by tests."""
    r = resolve_company_query(message, hint)
    return r.symbol, r.name


def _bare_ticker_override(message: str) -> RouteDecision | None:
    """Override broad→company for grounded / CN / HK tickers (not 'hello')."""
    bare = message.strip()
    resolved = resolve_symbol(bare)
    if resolved:
        return _from_resolved(resolved, "llm:broad_overridden_bare_ticker")
    cn = _as_cn_ticker(bare)
    if cn:
        return RouteDecision(
            mode="company",
            symbol=cn,
            reason="llm:broad_overridden_bare_cn_ticker",
        )
    hk = _as_hk_ticker(bare)
    if hk:
        return RouteDecision(
            mode="company",
            symbol=hk,
            reason="llm:broad_overridden_bare_hk_ticker",
        )
    return None


def heuristic_route(message: str) -> RouteDecision:
    """No-LLM fallback: company when ticker/alias/look-pattern evidence exists."""
    text = message.strip()
    if not text:
        return RouteDecision(mode="broad", reason="empty")

    resolved = resolve_symbol(text)
    if resolved:
        return _from_resolved(resolved, "heuristic:symbol_or_alias")

    for pat in _LOOK_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        token = _clean_look_token(m.group(1))
        r = resolve_company_query(text, token)
        if r.symbol:
            return RouteDecision(
                mode="company",
                symbol=r.symbol,
                name=r.name,
                reason="heuristic:resolved",
                candidates=r.candidates,
            )
        return RouteDecision(
            mode="company",
            symbol=None,
            name=None,
            reason="heuristic:need_clarify",
            candidates=r.candidates,
            needs_clarify=True,
        )

    return RouteDecision(mode="broad", reason="heuristic:no_symbol")


def llm_classify(message: str, history: list[dict[str, str]] | None = None) -> RouteDecision:
    """Classify via JSON chat completion (DeepSeek-friendly; no response_format)."""
    from app.agent.llm import invoke_llm
    from app.agent.trace import add_trace, progress

    hist = history or []
    recent = hist[-6:]
    hist_lines = "\n".join(f"{h.get('role')}: {h.get('content')}" for h in recent)
    user = f"最近对话：\n{hist_lines or '（无）'}\n\n本轮用户：{message.strip()}"

    progress("意图分类中…")
    result_llm = invoke_llm(
        system=_CLASSIFY_SYSTEM,
        user=user,
        temperature=0.0,
        trace_kind="classify",
        trace_title="意图分类",
    )
    content = result_llm.content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence:
        content = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", content, re.DOTALL)
        if brace:
            content = brace.group(0)

    result = IntentClassification.model_validate(json.loads(content))
    add_trace(
        "classify",
        "分类结果",
        detail=result.model_dump_json(),
        mode=result.mode,
        symbol_hint=result.symbol_hint,
    )

    if result.mode == "broad":
        override = _bare_ticker_override(message)
        if override:
            add_trace("classify", "裸代码覆盖", detail=override.reason)
            return override
        return RouteDecision(mode="broad", reason=f"llm:{result.rationale or 'broad'}")

    resolved = resolve_company_query(message, result.symbol_hint, history=hist)
    add_trace(
        "resolve",
        "标的解析",
        detail=(
            f"symbol={resolved.symbol} name={resolved.name} "
            f"clarify={resolved.needs_clarify} cands={len(resolved.candidates)}"
        ),
    )
    if resolved.symbol:
        return RouteDecision(
            mode="company",
            symbol=resolved.symbol,
            name=resolved.name,
            reason=f"llm:{result.rationale or 'company'}",
            candidates=resolved.candidates,
        )
    # Stay in company — ask to clarify / show candidates. Never silent→broad.
    return RouteDecision(
        mode="company",
        symbol=None,
        name=None,
        reason=f"llm:company_need_clarify ({result.rationale})",
        candidates=resolved.candidates,
        needs_clarify=True,
    )


def route_message(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> RouteDecision:
    """Primary path: LLM JSON classify. Fallback: heuristic when no key / LLM errors."""
    if has_llm():
        try:
            return llm_classify(message, history)
        except Exception as exc:  # noqa: BLE001
            fallback = heuristic_route(message)
            fallback.reason = f"heuristic:after_llm_error ({type(exc).__name__}: {exc})"
            return fallback
    return heuristic_route(message)
