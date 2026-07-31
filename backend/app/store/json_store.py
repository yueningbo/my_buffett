from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from app.domain.models import InvestorProfile, ReviewResult, ThesisCard, utc_now


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self.profile_path = self.root / "profile.json"
        self.thesis_dir = self.root / "thesis"
        self.reviews_dir = self.root / "reviews"
        self.thesis_dir.mkdir(exist_ok=True)
        self.reviews_dir.mkdir(exist_ok=True)

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
