# MVP（技术骨架阶段）

## 目标

可本地点通：假工具 + 原则审查 happy path；宽泛话题不拉数。

## 范围内

- 投资者档案读写（JSON）
- 内置原则清单（5–8 条）+ 结构化审查
- 两档路由：`broad` / `company`
- Mock 工具：报价、财报摘要
- 论点卡 upsert + 审查快照
- FastAPI（可选）+ LangGraph 编排
- 本地 CLI：对话 + 审查摘要 + 论点卡查看
- 无 API key 时 mock 导师仍可跑
- 单测：路由护栏、数字 ⊆ 工具

## 范围外

- Web / 小程序 UI（以后再说）
- 提醒调度、真实行情、自动交易
- 多用户 / 鉴权
- 精确 DCF / 内在价值卖点
- 精美设计系统、巴菲特人设工程

## 验收

1. `python -m app.cli` 可交互
2. 「我该怎么看仓位？」→ 不调工具，原则引导
3. 「看看茅台 / 600519」→ mock 证据 → `ReviewResult` → `/thesis` 可见
4. `pytest`：broad 零工具；审查数字 ⊆ mock 输出
