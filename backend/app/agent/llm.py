from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI


def has_llm() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def get_chat_model(*, temperature: float = 0.0) -> ChatOpenAI:
    model = os.environ.get("OPENAI_MODEL", "deepseek-v4-pro")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "base_url": base,
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }
    return ChatOpenAI(**kwargs)


@dataclass
class LLMResult:
    content: str
    reasoning: str = ""
    raw: Any = None


def _delta_field(delta: Any, name: str) -> str:
    if delta is None:
        return ""
    val = getattr(delta, name, None)
    if val:
        return str(val)
    extra = getattr(delta, "model_extra", None) or {}
    if isinstance(extra, dict) and extra.get(name):
        return str(extra[name])
    try:
        dumped = delta.model_dump()
        return str(dumped.get(name) or "")
    except Exception:
        return ""


def _message_reasoning(msg: Any) -> str:
    reasoning = getattr(msg, "reasoning_content", None) or ""
    if not reasoning and getattr(msg, "model_extra", None):
        reasoning = str(msg.model_extra.get("reasoning_content") or "")
    if not reasoning:
        try:
            reasoning = str(msg.model_dump().get("reasoning_content") or "")
        except Exception:
            reasoning = ""
    return reasoning or ""


def invoke_llm(
    *,
    system: str,
    user: str,
    temperature: float = 0.0,
    trace_kind: str = "llm",
    trace_title: str = "LLM",
    stream_content: bool = False,
) -> LLMResult:
    """Call chat API.

    - Default: non-stream for classify/extract/memory (progress lines elsewhere).
    - stream_content=True: stream final reply text (default UX).
    - verbose: also stream reasoning; headers for each step.
    """
    from openai import OpenAI

    from app.agent.trace import (
        add_trace,
        is_verbose,
        mark_streamed,
        progress,
        stream_print,
    )

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
    )
    model = os.environ.get("OPENAI_MODEL", "deepseek-v4-pro")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    verbose = is_verbose()
    use_stream = verbose or stream_content

    if not use_stream:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=messages,
        )
        msg = resp.choices[0].message
        content = msg.content or ""
        reasoning = _message_reasoning(msg)
        add_trace(
            trace_kind,
            trace_title,
            detail=content,
            reasoning=reasoning,
            model=model,
            temperature=temperature,
        )
        return LLMResult(content=content, reasoning=reasoning, raw=resp)

    # --- streaming ---
    show_reasoning = verbose
    show_content = stream_content
    if verbose:
        stream_print(f"\n>>> [{trace_kind}] {trace_title} · 思考\n")
    elif stream_content:
        progress("正在回复…")

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    content_header_printed = False

    stream = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        r = _delta_field(delta, "reasoning_content")
        if r:
            reasoning_parts.append(r)
            if show_reasoning:
                stream_print(r)
                mark_streamed()
        c = delta.content or ""
        if c:
            content_parts.append(c)
            if show_content:
                if verbose and not content_header_printed:
                    stream_print(f"\n>>> [{trace_kind}] {trace_title} · 输出\n")
                    content_header_printed = True
                stream_print(c)
                mark_streamed()

    if show_content or show_reasoning:
        stream_print("\n")

    content = "".join(content_parts)
    reasoning = "".join(reasoning_parts)
    add_trace(
        trace_kind,
        trace_title,
        detail=content,
        reasoning=reasoning,
        streamed=bool(show_content or show_reasoning),
        model=model,
        temperature=temperature,
    )
    return LLMResult(content=content, reasoning=reasoning, raw=None)
