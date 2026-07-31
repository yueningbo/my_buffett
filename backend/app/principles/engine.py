from __future__ import annotations

from app.domain.models import (
    EvidenceBundle,
    InvestorProfile,
    ReviewResult,
    ReviewVerdict,
    ToolNumber,
    Verdict,
)
from app.principles.checklist import get_checklist


def _worst(a: Verdict, b: Verdict) -> Verdict:
    order = {Verdict.PASS: 0, Verdict.CONCERN: 1, Verdict.VETO: 2}
    return a if order[a] >= order[b] else b


def _num(evidence: EvidenceBundle, key: str) -> ToolNumber | None:
    return evidence.number_map().get(key)


def _ref(tool: str, key: str) -> str:
    return f"{tool}:{key}"


def review_symbol(
    evidence: EvidenceBundle,
    profile: InvestorProfile,
) -> ReviewResult:
    """Rule-based principle review. Numbers only from evidence tools."""
    items: list[ReviewVerdict] = []
    name = evidence.name or evidence.symbol
    industry = ""
    business = ""
    for tr in evidence.tool_results:
        industry = industry or str(tr.raw.get("industry") or "")
        business = business or str(tr.raw.get("business") or tr.summary)

    # circle_of_competence
    if not profile.circle_of_competence:
        items.append(
            ReviewVerdict(
                principle_id="circle_of_competence",
                verdict=Verdict.CONCERN,
                rationale="档案未填写能力圈，无法确认是否在圈内。",
                missing_info=["circle_of_competence"],
            )
        )
    else:
        hay = f"{name} {industry} {business}".lower()
        hit = any(c.lower() in hay for c in profile.circle_of_competence)
        items.append(
            ReviewVerdict(
                principle_id="circle_of_competence",
                verdict=Verdict.PASS if hit else Verdict.CONCERN,
                rationale=(
                    f"档案能力圈 {profile.circle_of_competence} 与标的「{industry or '未知行业'}」有重叠。"
                    if hit
                    else f"档案能力圈 {profile.circle_of_competence} 与「{industry or '未知行业'}」未见明显重叠，请自行确认。"
                ),
                evidence_refs=["get_company_overview"] if industry else [],
                missing_info=[] if industry else ["industry"],
            )
        )

    # understand_business
    if business and len(business) >= 20:
        items.append(
            ReviewVerdict(
                principle_id="understand_business",
                verdict=Verdict.PASS,
                rationale=f"工具给出业务摘要，可作理解起点（非投资建议）：{business[:160]}",
                evidence_refs=["get_company_overview"],
            )
        )
    else:
        items.append(
            ReviewVerdict(
                principle_id="understand_business",
                verdict=Verdict.CONCERN,
                rationale="缺少足够的业务说明，暂不能认为已理解生意。",
                missing_info=["business_description"],
            )
        )

    # business_before_price
    roe = _num(evidence, "roe_pct")
    gross = _num(evidence, "gross_margin_pct")
    price = _num(evidence, "last_price")
    quality_refs: list[str] = []
    if roe:
        quality_refs.append(_ref("get_financials_snapshot", "roe_pct"))
    if gross:
        quality_refs.append(_ref("get_financials_snapshot", "gross_margin_pct"))
    if roe or gross:
        parts = []
        if roe:
            parts.append(f"ROE {roe.value}{roe.unit}（来源 {roe.source}）")
        if gross:
            parts.append(f"毛利率 {gross.value}{gross.unit}（来源 {gross.source}）")
        items.append(
            ReviewVerdict(
                principle_id="business_before_price",
                verdict=Verdict.PASS,
                rationale="已有质量信号，可先谈生意再谈价格：" + "；".join(parts),
                evidence_refs=quality_refs,
            )
        )
    elif price:
        items.append(
            ReviewVerdict(
                principle_id="business_before_price",
                verdict=Verdict.CONCERN,
                rationale=(
                    f"目前主要只有价格 {price.value}{price.unit}（{price.source}），"
                    "质量信号不足，避免因「看起来便宜」单独行动。"
                ),
                evidence_refs=[_ref("get_quote", "last_price")],
                missing_info=["roe_pct", "gross_margin_pct"],
            )
        )
    else:
        items.append(
            ReviewVerdict(
                principle_id="business_before_price",
                verdict=Verdict.CONCERN,
                rationale="缺少质量与价格证据。",
                missing_info=["roe_pct", "gross_margin_pct", "last_price"],
            )
        )

    # margin_of_safety — discuss range, never precise IV
    pe = _num(evidence, "pe_ttm")
    if price and pe:
        items.append(
            ReviewVerdict(
                principle_id="margin_of_safety",
                verdict=Verdict.PASS,
                rationale=(
                    f"可对照价格 {price.value}{price.unit} 与 PE(TTM) {pe.value}"
                    f"（{pe.source}）讨论相对贵贱与安全边际意识；"
                    "本系统不做精确内在价值定价。"
                ),
                evidence_refs=[
                    _ref("get_quote", "last_price"),
                    _ref("get_financials_snapshot", "pe_ttm"),
                ],
            )
        )
    else:
        missing = []
        if not price:
            missing.append("last_price")
        if not pe:
            missing.append("pe_ttm")
        items.append(
            ReviewVerdict(
                principle_id="margin_of_safety",
                verdict=Verdict.CONCERN,
                rationale="价格或估值倍数不足，只能强调「先留安全边际」，无法讨论相对贵贱。",
                missing_info=missing,
            )
        )

    # position_and_risk
    if not profile.risk_tolerance and not profile.horizon:
        items.append(
            ReviewVerdict(
                principle_id="position_and_risk",
                verdict=Verdict.CONCERN,
                rationale="档案缺少风险承受与投资期限，无法判断仓位是否匹配。",
                missing_info=["risk_tolerance", "horizon"],
            )
        )
    else:
        items.append(
            ReviewVerdict(
                principle_id="position_and_risk",
                verdict=Verdict.PASS,
                rationale=(
                    f"已记录期限={profile.horizon or '未填'}、风险={profile.risk_tolerance or '未填'}；"
                    "若加仓请自行核对单票上限与回撤承受力。"
                ),
            )
        )

    # taboos
    if profile.taboos:
        hay = f"{name} {industry} {business}".lower()
        hits = [t for t in profile.taboos if t.lower() in hay]
        if hits:
            items.append(
                ReviewVerdict(
                    principle_id="taboos",
                    verdict=Verdict.VETO,
                    rationale=f"触碰档案禁忌：{hits}。建议否决或先改禁忌定义。",
                    evidence_refs=["get_company_overview"] if industry else [],
                )
            )
        else:
            items.append(
                ReviewVerdict(
                    principle_id="taboos",
                    verdict=Verdict.PASS,
                    rationale=f"未命中已登记禁忌 {profile.taboos}。",
                )
            )
    else:
        items.append(
            ReviewVerdict(
                principle_id="taboos",
                verdict=Verdict.CONCERN,
                rationale="档案未设置禁忌，无法做否决检查。",
                missing_info=["taboos"],
            )
        )

    # opportunity_cost
    if profile.positions:
        symbols = [p.symbol for p in profile.positions]
        items.append(
            ReviewVerdict(
                principle_id="opportunity_cost",
                verdict=Verdict.PASS,
                rationale=f"现有持仓 {symbols}：请对比机会成本，而非孤立看单一标的。",
            )
        )
    else:
        items.append(
            ReviewVerdict(
                principle_id="opportunity_cost",
                verdict=Verdict.CONCERN,
                rationale="档案无持仓信息，机会成本只能口头提醒。",
                missing_info=["positions"],
            )
        )

    overall = Verdict.PASS
    for it in items:
        overall = _worst(overall, it.verdict)

    top_refs = evidence.evidence_refs()
    summary_bits = [f"{it.principle_id}={it.verdict.value}" for it in items]
    summary = (
        f"{name}（{evidence.symbol}）原则审查总览：{overall.value}。"
        f"明细：{', '.join(summary_bits)}。人做决策；以上非荐股。"
    )

    # Ensure checklist coverage
    ids = {i.principle_id for i in items}
    for p in get_checklist():
        if p.id not in ids:
            items.append(
                ReviewVerdict(
                    principle_id=p.id,
                    verdict=Verdict.CONCERN,
                    rationale="未执行该项检查。",
                    missing_info=["engine_gap"],
                )
            )
            overall = _worst(overall, Verdict.CONCERN)

    return ReviewResult(
        symbol=evidence.symbol,
        name=evidence.name,
        items=items,
        overall=overall,
        summary=summary,
        evidence_refs=top_refs,
    )
