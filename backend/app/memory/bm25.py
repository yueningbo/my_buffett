"""Lightweight BM25 for Chinese-friendly tokenization (char bigrams + words)."""

from __future__ import annotations

import math
import re
from collections import Counter


_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    parts = _TOKEN_RE.findall(text)
    tokens: list[str] = []
    buf: list[str] = []
    for p in parts:
        if len(p) == 1 and "\u4e00" <= p <= "\u9fff":
            buf.append(p)
        else:
            if len(buf) >= 2:
                tokens.extend(buf[i] + buf[i + 1] for i in range(len(buf) - 1))
            elif buf:
                tokens.extend(buf)
            buf = []
            tokens.append(p)
    if len(buf) >= 2:
        tokens.extend(buf[i] + buf[i + 1] for i in range(len(buf) - 1))
    elif buf:
        tokens.extend(buf)
    return tokens or ([text[:8]] if text else [])


class BM25Index:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(doc) for doc in corpus]
        self.doc_len = [len(d) or 1 for d in self.docs]
        self.avgdl = sum(self.doc_len) / max(len(self.docs), 1)
        self.df: Counter[str] = Counter()
        for d in self.docs:
            for t in set(d):
                self.df[t] += 1
        self.n = len(self.docs)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out: list[float] = []
        for doc, dl in zip(self.docs, self.doc_len):
            tf = Counter(doc)
            score = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = self._idf(t)
                freq = tf[t]
                score += idf * (
                    freq * (self.k1 + 1) / (freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                )
            out.append(score)
        return out

    def top_k(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        scored = list(enumerate(self.scores(query)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in scored[:k] if s > 0]
