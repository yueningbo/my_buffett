from __future__ import annotations

from app.domain.models import MemoryEntry
from app.memory.bm25 import BM25Index, tokenize
from app.memory import maybe_compact_session, recall_memories
from app.domain.models import ChatMessage, ChatSession


def test_tokenize_chinese_bigrams():
    toks = tokenize("我喜欢白酒和消费")
    assert "白酒" in toks or ("白" in toks and "酒" in toks)


def test_bm25_ranks_relevant_doc():
    corpus = [
        "用户能力圈是白酒和消费",
        "今天天气不错适合散步",
        "茅台属于白酒龙头",
    ]
    idx = BM25Index(corpus)
    hits = idx.top_k("白酒能力圈", k=2)
    assert hits
    assert hits[0][0] in (0, 2)


def test_memory_store_and_recall(store):
    store.add_memory(
        MemoryEntry(id="m1", text="用户几乎无限期持有，追求财富自由", tags=["invest"], kind="preference")
    )
    store.add_memory(
        MemoryEntry(id="m2", text="周末喜欢爬山", tags=["life"], kind="life")
    )
    hits = recall_memories(store, "投资期限和财富自由", k=2)
    assert hits
    assert "财富自由" in hits[0].text or "无限期" in hits[0].text


def test_session_compaction_without_llm(store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = store.create_session(title="压测")
    msgs = []
    for i in range(14):
        msgs.append(ChatMessage(role="user", content=f"用户消息{i}关于仓位纪律"))
        msgs.append(ChatMessage(role="assistant", content=f"助手回复{i}"))
    s.messages = msgs
    store.save_session(s)
    s2 = maybe_compact_session(store, s, every_n=10, keep_recent=4)
    assert s2.summary
    assert s2.summarized_until > 0
