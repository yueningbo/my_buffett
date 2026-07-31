from __future__ import annotations

from app.domain.models import PrincipleItem, Verdict

DEFAULT_CHECKLIST: list[PrincipleItem] = [
    PrincipleItem(
        id="circle_of_competence",
        statement="标的是否落在投资者能力圈内",
        how_to_check="对照档案 circle_of_competence 与行业/业务标签；档案为空则存疑并要求补充",
        severity_if_fail=Verdict.CONCERN,
    ),
    PrincipleItem(
        id="understand_business",
        statement="是否理解生意如何赚钱（而非只看故事）",
        how_to_check="工具摘要是否给出清晰业务与盈利模式说明；缺失则列为缺信息",
        severity_if_fail=Verdict.CONCERN,
    ),
    PrincipleItem(
        id="business_before_price",
        statement="先生意质量，后谈价格；不因便宜单独买入",
        how_to_check="是否有业务质量信号（ROE/毛利率等）；仅有价格无质量信息则存疑",
        severity_if_fail=Verdict.CONCERN,
    ),
    PrincipleItem(
        id="margin_of_safety",
        statement="需要安全边际意识，但不做精确内在价值定价当卖点",
        how_to_check="有价格与基础财务即可讨论相对贵贱区间；禁止输出精确公允价值结论",
        severity_if_fail=Verdict.CONCERN,
    ),
    PrincipleItem(
        id="position_and_risk",
        statement="仓位与风险是否与档案中的期限/风险承受匹配",
        how_to_check="对照档案 risk_tolerance / horizon；缺失则要求补充，不默认通过",
        severity_if_fail=Verdict.CONCERN,
    ),
    PrincipleItem(
        id="taboos",
        statement="是否触碰投资者明确禁忌",
        how_to_check="对照档案 taboos 与标的行业/特征；命中则否决",
        severity_if_fail=Verdict.VETO,
    ),
    PrincipleItem(
        id="opportunity_cost",
        statement="相对现有持仓与现金，机会成本是否被考虑",
        how_to_check="档案有持仓则提示对比；无持仓信息则记录缺信息",
        severity_if_fail=Verdict.CONCERN,
    ),
]


def get_checklist() -> list[PrincipleItem]:
    return list(DEFAULT_CHECKLIST)
