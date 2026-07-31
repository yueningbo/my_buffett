"""Episodic memory write / recall / session compaction."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agent.llm import has_llm, invoke_llm
from app.agent.trace import add_trace
from app.domain.models import ChatSession, MemoryEntry, utc_now
from app.memory.bm25 import BM25Index
from app.store.json_store import Store

_SUMMARY_SYSTEM = """你是会话摘要器。把给定对话压缩成简洁中文摘要（投资导师场景）。
保留：用户目标/风险/能力圈/生活财务要点、重要决策与未决问题、提到的标的。
不要编造。输出纯文本摘要，不要 markdown 标题堆砌。"""

_MEMORY_SYSTEM = """你是长期记忆写入器。从本轮对话提取 0-3 条值得跨会话记住的要点，只输出 JSON（含 json 字样）：
{"memories":[{"text":"一句话事实或决策","tags":["invest|life|decision|preference"],"kind":"episodic|preference|decision|life|invest"}]}

规则：
- 寒暄、重复档案已有字段、无信息 → memories 为空数组
- text 要可独立理解（不要“如上所述”）
- 不要编造用户没说的内容
"""


def recall_memories(store: Store, query: str, *, k: int = 5) -> list[MemoryEntry]:
    items = store.list_memories()
    if not items or not query.strip():
        return []
    index = BM25Index([m.text + " " + " ".join(m.tags) for m in items])
    hits = index.top_k(query, k=k)
    recalled = [items[i] for i, score in hits]
    add_trace(
        "memory",
        "情节记忆召回",
        detail="\n".join(f"- ({m.kind}) {m.text}" for m in recalled) or "(无命中)",
        hits=len(recalled),
    )
    return recalled


def memories_block(memories: list[MemoryEntry]) -> str:
    if not memories:
        return "（无检索到的情节记忆）"
    lines = [f"- [{m.kind}] {m.text}" for m in memories]
    return "【检索记忆】\n" + "\n".join(lines)


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


def should_write_memories(
    user_text: str,
    *,
    profile_updates: list[str] | None = None,
    mode: str | None = None,
) -> bool:
    """Skip LLM memory write on low-signal turns to cut latency."""
    text = user_text.strip()
    if not text:
        return False
    if profile_updates:
        return True
    if mode == "company":
        return True
    if re.fullmatch(r"(你好|您好|hello|hi|hey|在吗)[\s!！。.?？~～]*", text, re.I):
        return False
    cues = (
        "决定",
        "持仓",
        "买入",
        "卖出",
        "目标",
        "风险",
        "能力圈",
        "房贷",
        "收入",
        "开销",
        "应急",
        "仓位",
        "原则",
        "财富",
        "期限",
    )
    if any(c in text for c in cues):
        return True
    return len(text) >= 40


def extract_and_store_memories(
    store: Store,
    *,
    user_text: str,
    assistant_text: str,
    session_id: str | None,
    profile_updates: list[str] | None = None,
    mode: str | None = None,
) -> list[MemoryEntry]:
    """Write episodic memories for this turn (LLM when available)."""
    if not should_write_memories(user_text, profile_updates=profile_updates, mode=mode):
        add_trace("memory", "情节记忆写入", detail="skipped (low-signal turn)")
        return []

    created: list[MemoryEntry] = []
    if has_llm():
        try:
            raw = invoke_llm(
                system=_MEMORY_SYSTEM,
                user=f"用户：{user_text}\n助手：{assistant_text[:800]}",
                temperature=0.0,
                trace_kind="memory",
                trace_title="情节记忆写入",
            )
            data = _parse_json_object(raw.content)
            for item in data.get("memories") or []:
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                entry = MemoryEntry(
                    id=uuid.uuid4().hex[:12],
                    text=text,
                    tags=list(item.get("tags") or []),
                    kind=item.get("kind") or "episodic",
                    source_session=session_id,
                    created_at=utc_now(),
                )
                store.add_memory(entry)
                created.append(entry)
            return created
        except Exception:
            pass

    # Heuristic fallback: keep short non-greeting user statements as weak memories
    if len(user_text) >= 20 and not re.fullmatch(r"(你好|hello|hi|hey)[!！.。]*", user_text.strip(), re.I):
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            text=user_text.strip()[:180],
            tags=["heuristic"],
            kind="episodic",
            source_session=session_id,
        )
        store.add_memory(entry)
        created.append(entry)
    return created


def maybe_compact_session(
    store: Store,
    session: ChatSession,
    *,
    every_n: int = 12,
    keep_recent: int = 10,
) -> ChatSession:
    """Fold older messages into session.summary when enough new turns accumulated."""
    total = len(session.messages)
    pending = total - session.summarized_until
    if pending < every_n:
        return session

    old = session.messages[session.summarized_until : max(session.summarized_until, total - keep_recent)]
    if not old:
        return session

    transcript = "\n".join(f"{m.role}: {m.content}" for m in old)
    prior = session.summary.strip()
    if has_llm():
        try:
            raw = invoke_llm(
                system=_SUMMARY_SYSTEM,
                user=f"已有摘要：\n{prior or '（无）'}\n\n新增对话：\n{transcript}",
                temperature=0.0,
                trace_kind="memory",
                trace_title="会话摘要滚动",
            )
            session.summary = raw.content.strip()
        except Exception:
            session.summary = (prior + "\n" + transcript[:500]).strip()
    else:
        # Deterministic stub summary
        session.summary = (
            (prior + "\n" if prior else "")
            + f"（自动摘要）覆盖消息 {session.summarized_until}..{total - keep_recent}；"
            + "；".join(m.content[:40] for m in old if m.role == "user")[:300]
        ).strip()

    session.summarized_until = max(0, total - keep_recent)
    return store.save_session(session)
