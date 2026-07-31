"""Turn-level observability: LLM reasoning + intermediate agent steps."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

_TRACE: ContextVar[list["TraceEvent"] | None] = ContextVar("my_buffett_trace", default=None)
_VERBOSE: ContextVar[bool] = ContextVar("my_buffett_verbose", default=False)
_STREAMED: ContextVar[bool] = ContextVar("my_buffett_streamed", default=False)


@dataclass
class TraceEvent:
    kind: str  # classify | extract | mentor | tool | note
    title: str
    detail: str = ""
    reasoning: str = ""
    streamed: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


def set_verbose(on: bool) -> None:
    _VERBOSE.set(on)


def is_verbose() -> bool:
    return bool(_VERBOSE.get())


def mark_streamed() -> None:
    _STREAMED.set(True)


def was_streamed() -> bool:
    return bool(_STREAMED.get())


@contextmanager
def capture_trace() -> Iterator[list[TraceEvent]]:
    events: list[TraceEvent] = []
    token = _TRACE.set(events)
    streamed_token = _STREAMED.set(False)
    try:
        yield events
    finally:
        _TRACE.reset(token)
        _STREAMED.reset(streamed_token)


def add_trace(
    kind: str,
    title: str,
    *,
    detail: str = "",
    reasoning: str = "",
    streamed: bool = False,
    **meta: Any,
) -> None:
    bucket = _TRACE.get()
    if bucket is None:
        return
    bucket.append(
        TraceEvent(
            kind=kind,
            title=title,
            detail=detail,
            reasoning=reasoning,
            streamed=streamed,
            meta=meta,
        )
    )


def stream_print(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def progress(msg: str) -> None:
    """Short status line for non-verbose turns (skipped when verbose — headers cover it)."""
    if is_verbose():
        return
    stream_print(f"… {msg}\n")


def format_trace(events: list[TraceEvent], *, max_reason_chars: int = 2500) -> str:
    if not events:
        return "(本轮无追踪事件)"
    if any(ev.streamed for ev in events):
        return "（思考过程已在上方流式输出）"
    chunks: list[str] = []
    for i, ev in enumerate(events, 1):
        chunks.append(f"### {i}. [{ev.kind}] {ev.title}")
        if ev.meta:
            meta = ", ".join(f"{k}={v}" for k, v in ev.meta.items())
            chunks.append(f"meta: {meta}")
        if ev.reasoning:
            reason = ev.reasoning.strip()
            if len(reason) > max_reason_chars:
                reason = reason[:max_reason_chars] + "\n…(截断)"
            chunks.append("思考:\n" + reason)
        if ev.detail:
            detail = ev.detail.strip()
            if len(detail) > 1200:
                detail = detail[:1200] + "\n…(截断)"
            chunks.append("输出:\n" + detail)
        chunks.append("")
    return "\n".join(chunks).rstrip()
