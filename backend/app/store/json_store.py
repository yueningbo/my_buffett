from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from threading import Lock

from app.domain.models import (
    ChatMessage,
    ChatSession,
    InvestorProfile,
    MemoryEntry,
    ReviewResult,
    ThesisCard,
    utc_now,
)


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self.profile_path = self.root / "profile.json"
        self.thesis_dir = self.root / "thesis"
        self.reviews_dir = self.root / "reviews"
        self.sessions_dir = self.root / "sessions"
        self.memories_path = self.root / "memories.jsonl"
        self.current_session_path = self.root / "current_session.txt"
        self.thesis_dir.mkdir(exist_ok=True)
        self.reviews_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)

    def get_profile(self) -> InvestorProfile:
        with self._lock:
            if not self.profile_path.exists():
                return InvestorProfile()
            data = json.loads(self.profile_path.read_text(encoding="utf-8"))
            return InvestorProfile.model_validate(data)

    def save_profile(self, profile: InvestorProfile) -> InvestorProfile:
        profile.updated_at = utc_now()
        with self._lock:
            self.profile_path.write_text(
                profile.model_dump_json(indent=2),
                encoding="utf-8",
            )
        return profile

    def get_thesis(self, symbol: str) -> ThesisCard | None:
        path = self.thesis_dir / f"{symbol}.json"
        with self._lock:
            if not path.exists():
                return None
            return ThesisCard.model_validate_json(path.read_text(encoding="utf-8"))

    def list_thesis(self) -> list[ThesisCard]:
        cards: list[ThesisCard] = []
        with self._lock:
            for path in sorted(self.thesis_dir.glob("*.json")):
                cards.append(ThesisCard.model_validate_json(path.read_text(encoding="utf-8")))
        return cards

    def upsert_thesis(self, card: ThesisCard) -> ThesisCard:
        card.updated_at = utc_now()
        path = self.thesis_dir / f"{card.symbol}.json"
        with self._lock:
            path.write_text(card.model_dump_json(indent=2), encoding="utf-8")
        return card

    def save_review(self, review: ReviewResult) -> None:
        ts = review.created_at.strftime("%Y%m%dT%H%M%S")
        path = self.reviews_dir / f"{review.symbol}_{ts}.json"
        with self._lock:
            path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    # --- sessions (long-term chat memory) ---

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def create_session(self, title: str = "默认会话") -> ChatSession:
        session = ChatSession(id=uuid.uuid4().hex[:12], title=title)
        self.save_session(session)
        self.set_current_session_id(session.id)
        return session

    def save_session(self, session: ChatSession) -> ChatSession:
        session.updated_at = utc_now()
        path = self._session_path(session.id)
        with self._lock:
            path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        path = self._session_path(session_id)
        with self._lock:
            if not path.exists():
                return None
            return ChatSession.model_validate_json(path.read_text(encoding="utf-8"))

    def list_sessions(self) -> list[ChatSession]:
        sessions: list[ChatSession] = []
        with self._lock:
            for path in self.sessions_dir.glob("*.json"):
                sessions.append(ChatSession.model_validate_json(path.read_text(encoding="utf-8")))
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def set_current_session_id(self, session_id: str) -> None:
        with self._lock:
            self.current_session_path.write_text(session_id, encoding="utf-8")

    def get_current_session_id(self) -> str | None:
        with self._lock:
            if not self.current_session_path.exists():
                return None
            return self.current_session_path.read_text(encoding="utf-8").strip() or None

    def get_or_create_current_session(self) -> ChatSession:
        sid = self.get_current_session_id()
        if sid:
            session = self.get_session(sid)
            if session:
                return session
        return self.create_session()

    def append_messages(self, session_id: str, messages: list[ChatMessage]) -> ChatSession:
        session = self.get_session(session_id)
        if not session:
            session = ChatSession(id=session_id, title="默认会话")
        session.messages.extend(messages)
        # Soft cap to keep files manageable; older turns remain in truncated file history only.
        if len(session.messages) > 400:
            session.messages = session.messages[-400:]
        if session.title == "默认会话" and messages:
            first_user = next((m for m in session.messages if m.role == "user"), None)
            if first_user:
                session.title = first_user.content.strip()[:24] or session.title
        return self.save_session(session)

    # --- episodic memories ---

    def list_memories(self) -> list[MemoryEntry]:
        with self._lock:
            return self._list_memories_unlocked()

    def _list_memories_unlocked(self) -> list[MemoryEntry]:
        if not self.memories_path.exists():
            return []
        out: list[MemoryEntry] = []
        for line in self.memories_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(MemoryEntry.model_validate_json(line))
        return out

    def add_memory(self, entry: MemoryEntry) -> MemoryEntry:
        with self._lock:
            for m in self._list_memories_unlocked():
                if m.text.strip() == entry.text.strip():
                    return m
            with self.memories_path.open("a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        return entry

    def clear_memories_for_tests(self) -> None:
        with self._lock:
            if self.memories_path.exists():
                self.memories_path.unlink()


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        raw = os.environ.get("MY_BUFFETT_DATA_DIR")
        if raw:
            root = Path(raw)
        else:
            root = Path(__file__).resolve().parents[2] / "data"
        _store = Store(root)
    return _store


def reset_store_for_tests(root: Path) -> Store:
    global _store
    _store = Store(root)
    return _store
