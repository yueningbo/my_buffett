# Architecture

对齐 [VISION.md](../VISION.md)：Workflow + 局部 Agent；宽泛 / 具体公司分流；关键数字以工具为准。

## 栈

| 层 | 选型 |
|---|---|
| Agent / API | Python 3.11+、FastAPI、LangGraph、Pydantic |
| 薄 Web | Vite + React + TypeScript |
| 存储 MVP | 本地 JSON（档案、论点卡、审查快照） |
| LLM | OpenAI 兼容 API（`OPENAI_API_KEY`）；无 key 时确定性 mock 导师 |

## 模块

```
backend/app/
  api/          # HTTP：/chat, /profile, /thesis
  domain/       # 契约：Profile, Review, Thesis, ToolResult
  principles/   # 清单 + 审查引擎（pass/concern/veto）
  tools/        # 工具契约 + Mock 实现
  agent/        # LangGraph：route → coach | research+review
  store/        # JSON 读写
web/            # 对话入口 + 右侧审查 / 论点卡
```

## 运行时流程

```mermaid
flowchart TD
  userMsg[UserMessage] --> router[ModeRouter]
  router -->|broad| coach[CoachWorkflow]
  router -->|company| research[ResearchSubgraph]
  coach --> profile[InvestorProfile]
  coach --> principles[PrincipleCoach]
  research --> tools[ToolContracts]
  tools --> evidence[EvidenceBundle]
  evidence --> review[PrincipleReviewEngine]
  review --> thesis[ThesisCardUpsert]
  coach --> reply[MentorReply]
  review --> reply
  thesis --> reply
```

## 两档路由（硬护栏）

| 模式 | 触发 | 允许 | 禁止 |
|---|---|---|---|
| `broad` | 无明确标的 | 档案 + 原则教练 | 行情 / 财报 / 筛股工具 |
| `company` | ticker / 「看看 XX」 | 工具 + 审查 + 论点卡 | 空聊荐股；编造数字 |

路由由规则判定（正则 / 标的表），不靠模型自觉。`company` 下审查结果中的关键数字必须 ⊆ 当次 `ToolResult.numbers`。

## Context 分层

1. **System**：导师角色 + 不做清单（极简）
2. **Profile**：投资者档案摘要
3. **Session**：近几轮对话
4. **Evidence**（仅 company）：工具回传摘要，带 `evidence_refs`
5. **Review / Thesis**：结构化结果，供 UI 与下次接着教

开放式研究用子图，只把摘要写回主 context，避免膨胀。

## HITL

人决策；系统引导与否决建议。审查输出 `pass | concern | veto`，不自动下单。论点卡由审查后 upsert，用户可在后续对话中修正。

## 评测焦点

- broad 路径 tool call 数 = 0
- 审查数字 ⊆ 工具输出（反幻觉）
- 缺信息时 `missing_info` 非空，而非假装通过
