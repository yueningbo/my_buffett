# my_buffett

个人价值投资导师（原则引导 + 证据审查）。

- 产品边界：[VISION.md](./VISION.md)
- 架构：[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- 本阶段范围：[docs/MVP.md](./docs/MVP.md)

## 栈

Python Agent 核（FastAPI + LangGraph）+ 薄 Web（Vite + React）。

## 启动

### Backend

```bash
cd backend
python3.11 -m venv .venv   # 需要 Python 3.11+
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```


LLM：复制 `backend/.env.example` 为 `backend/.env`。默认按 **DeepSeek** OpenAI 兼容接口：

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
```

未设置 key 时走确定性 mock 导师。`.env` 已在 `.gitignore`，勿提交。

数据目录默认 `backend/data/`（可用 `MY_BUFFETT_DATA_DIR` 覆盖）。

### Web

```bash
cd web
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（默认 http://localhost:5173）。API 代理到 `http://127.0.0.1:8000`。

### 测试

```bash
cd backend
source .venv/bin/activate
pytest
```

## 验收路径

1. 宽泛：「我该怎么看仓位？」→ 无工具调用，原则引导
2. 具体：「看看茅台」或「看看 600519」→ mock 证据 + 审查结果 + 右侧论点卡
