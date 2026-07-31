# my_buffett

个人价值投资导师（原则引导 + 证据审查）。本地以 **CLI** 为前端，支持**长期会话与档案记忆**。

- 产品边界：[VISION.md](./VISION.md)
- 架构：[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- 本阶段范围：[docs/MVP.md](./docs/MVP.md)

## 栈

Python Agent 核（LangGraph + Pydantic）+ 本地 CLI；FastAPI 可选（脚本/集成用）。

## 启动（CLI）

```bash
cd backend
python3.11 -m venv .venv   # 需要 Python 3.11+
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 交互
python -m app.cli

# 一次性
python -m app.cli "我该怎么看仓位？"
python -m app.cli "看看茅台"
```

CLI 命令：`/help` `/profile` `/thesis` `/sessions` `/new` `/resume` `/quit`

数据目录 `backend/data/`：

- `profile.json` — 投资档案 + 生活财务
- `sessions/` — 聊天记录 + 滚动摘要
- `memories.jsonl` — 情节记忆（BM25 召回）
- `thesis/` / `reviews/` — 论点卡与审查快照

LLM：复制 `backend/.env.example` 为 `backend/.env`。默认 DeepSeek：

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
MY_BUFFETT_TOOL_MODE=auto
```

`MY_BUFFETT_TOOL_MODE`：`auto`（yfinance 真数据，失败回退 mock）| `live` | `mock`。

未设置 key 时走确定性 mock 导师。`.env` 已在 `.gitignore`，勿提交。

可用 `MY_BUFFETT_DATA_DIR` 覆盖数据根目录。

### 可选：HTTP API

```bash
uvicorn app.main:app --reload --port 8000
```

### 测试

```bash
cd backend
source .venv/bin/activate
pytest                 # 含护栏/反幻觉 eval
pytest tests/eval -q   # 只跑评测
```

## 验收路径

1. `python -m app.cli` → 「我该怎么看仓位？」→ 无工具调用，原则引导
2. 「看看茅台」→ mock 证据 + 审查结果 + 论点卡（`/thesis 600519`）
