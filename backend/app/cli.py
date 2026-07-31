"""Local CLI — long-term mentor with layered memory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.agent.graph import run_turn
from app.agent.trace import set_verbose
from app.domain.models import ChatMessage, ChatResponse, ChatSession
from app.memory import extract_and_store_memories, maybe_compact_session, recall_memories
from app.store.json_store import get_store

HELP = """命令：
  /help                 帮助
  /quit 或 /exit        退出（会话已自动保存）
  /profile              查看长期档案（投资 + 生活财务）
  /thesis [symbol]      论点卡
  /memory [query]       列出或检索情节记忆
  /sessions             列出最近会话
  /new [标题]           开新会话
  /resume <id>          切换到已有会话
  /verbose              开关：流式显示大模型思考过程（默认只流式打正式回复）
直接输入即可续聊；退出后再进会自动回到当前会话。
"""


def _print_response(resp: ChatResponse, *, verbose: bool) -> None:
    print()
    head = f"[{resp.mode}]"
    if resp.symbol:
        head += f" {resp.symbol}"
    if resp.route_reason:
        head += f"  ← {resp.route_reason}"
    print(head)
    if resp.profile_updates:
        print("saved profile:", ", ".join(resp.profile_updates))
    if resp.tool_calls:
        print("tools:", ", ".join(resp.tool_calls))
    if not resp.streamed:
        print("-" * 48)
        print(resp.reply)
    if resp.mode == "company" and resp.review:
        print("-" * 48)
        print(f"审查总览: {resp.review.overall.value}")
        for item in resp.review.items:
            miss = f" 缺[{', '.join(item.missing_info)}]" if item.missing_info else ""
            print(f"  - {item.principle_id}: {item.verdict.value}{miss}")
            print(f"    {item.rationale}")
    if resp.mode == "company" and resp.thesis:
        print("-" * 48)
        print(f"论点卡 {resp.thesis.symbol}: {resp.thesis.thesis}")
        if resp.thesis.open_questions:
            print("待澄清:", "; ".join(resp.thesis.open_questions))
    if verbose and resp.trace and not resp.streamed:
        print("-" * 48)
        print("【思考过程 / 中间步骤】")
        print(resp.trace)
    print()


def _cmd_profile() -> None:
    print(get_store().get_profile().model_dump_json(indent=2))


def _cmd_thesis(symbol: str | None) -> None:
    store = get_store()
    if symbol:
        card = store.get_thesis(symbol)
        if not card:
            print(f"无论点卡: {symbol}")
            return
        print(card.model_dump_json(indent=2))
        return
    cards = store.list_thesis()
    if not cards:
        print("（尚无论点卡）")
        return
    for c in cards:
        overall = c.last_review.overall.value if c.last_review else "-"
        print(f"- {c.symbol} ({c.name or '?'}) review={overall} | {c.thesis[:80]}")


def _cmd_memory(query: str | None) -> None:
    store = get_store()
    if query:
        hits = recall_memories(store, query, k=8)
        if not hits:
            print("（无命中记忆）")
            return
        for m in hits:
            print(f"- [{m.kind}] {m.text}")
        return
    items = store.list_memories()
    if not items:
        print("（尚无情节记忆）")
        return
    for m in items[-30:]:
        print(f"- [{m.kind}] {m.text}")


def _cmd_sessions(current_id: str) -> None:
    sessions = get_store().list_sessions()
    if not sessions:
        print("（尚无会话）")
        return
    for s in sessions[:20]:
        mark = "*" if s.id == current_id else " "
        sum_flag = " summary" if s.summary else ""
        print(
            f"{mark} {s.id}  {s.updated_at.isoformat()}  {s.title!r}  "
            f"({len(s.messages)} msgs{sum_flag})"
        )


def _after_turn(session: ChatSession, user_text: str, resp: ChatResponse) -> ChatSession:
    store = get_store()
    session = store.append_messages(
        session.id,
        [
            ChatMessage(role="user", content=user_text),
            ChatMessage(role="assistant", content=resp.reply, mode=resp.mode),
        ],
    )
    created = extract_and_store_memories(
        store,
        user_text=user_text,
        assistant_text=resp.reply,
        session_id=session.id,
        profile_updates=resp.profile_updates,
        mode=resp.mode,
    )
    if created:
        print(f"saved memories: {len(created)}")
    session = maybe_compact_session(store, session)
    return session


def _run_user_turn(session: ChatSession, line: str) -> tuple[ChatSession, ChatResponse]:
    store = get_store()
    history = session.as_history_dicts(limit=30)
    recalled = recall_memories(store, line, k=5)
    resp = run_turn(
        line,
        history,
        session_summary=session.summary,
        recalled_memories=recalled,
    )
    session = _after_turn(session, line, resp)
    return session, resp


def repl() -> int:
    store = get_store()
    session = store.get_or_create_current_session()
    verbose = False
    set_verbose(False)
    print("my_buffett CLI — 长期价值投资助手（本地）")
    print(f"会话 {session.id}「{session.title}」· 已有 {len(session.messages)} 条消息")
    if session.summary:
        print(f"会话摘要已启用（{len(session.summary)} 字）")
    print(f"情节记忆 {len(store.list_memories())} 条 · 回复默认流式 · /verbose 看思考过程\n")

    while True:
        try:
            line = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已保存，再见。")
            return 0
        if not line:
            continue
        if line in {"/quit", "/exit", "/q"}:
            print("已保存，再见。")
            return 0
        if line in {"/help", "/h", "?"}:
            print(HELP)
            continue
        if line == "/verbose":
            verbose = not verbose
            set_verbose(verbose)
            print(f"verbose = {'ON（思考也流式输出）' if verbose else 'OFF（仅回复流式）'}")
            continue
        if line == "/profile":
            _cmd_profile()
            continue
        if line.startswith("/thesis"):
            parts = line.split(maxsplit=1)
            _cmd_thesis(parts[1].strip() if len(parts) > 1 else None)
            continue
        if line.startswith("/memory"):
            parts = line.split(maxsplit=1)
            _cmd_memory(parts[1].strip() if len(parts) > 1 else None)
            continue
        if line == "/sessions":
            _cmd_sessions(session.id)
            continue
        if line.startswith("/new"):
            parts = line.split(maxsplit=1)
            title = parts[1].strip() if len(parts) > 1 else "新会话"
            session = store.create_session(title=title)
            print(f"已开新会话 {session.id}「{session.title}」")
            continue
        if line.startswith("/resume"):
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                print("用法: /resume <session_id>")
                continue
            sid = parts[1].strip()
            loaded = store.get_session(sid)
            if not loaded:
                print(f"找不到会话: {sid}")
                continue
            store.set_current_session_id(sid)
            session = loaded
            print(f"已切换到 {session.id}「{session.title}」({len(session.messages)} msgs)")
            continue

        try:
            session, resp = _run_user_turn(session, line)
        except Exception as exc:  # noqa: BLE001
            print(f"错误: {exc}", file=sys.stderr)
            continue
        _print_response(resp, verbose=verbose)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="my_buffett long-term local CLI mentor")
    parser.add_argument("message", nargs="?", help="一次性提问（仍写入当前会话）")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="打印大模型思考过程与中间步骤",
    )
    args = parser.parse_args(argv)
    if args.message:
        store = get_store()
        session = store.get_or_create_current_session()
        set_verbose(bool(args.verbose))
        session, resp = _run_user_turn(session, args.message.strip())
        _print_response(resp, verbose=args.verbose)
        return 0
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
