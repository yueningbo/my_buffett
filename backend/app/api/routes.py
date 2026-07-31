from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_turn
from app.domain.models import ChatRequest, ChatResponse, InvestorProfile, ThesisCard
from app.store.json_store import get_store

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message required")
    return run_turn(body.message.strip(), body.history)


@router.get("/profile", response_model=InvestorProfile)
def get_profile() -> InvestorProfile:
    return get_store().get_profile()


@router.put("/profile", response_model=InvestorProfile)
def put_profile(profile: InvestorProfile) -> InvestorProfile:
    return get_store().save_profile(profile)


@router.get("/thesis", response_model=list[ThesisCard])
def list_thesis() -> list[ThesisCard]:
    return get_store().list_thesis()


@router.get("/thesis/{symbol}", response_model=ThesisCard)
def get_thesis(symbol: str) -> ThesisCard:
    card = get_store().get_thesis(symbol)
    if not card:
        raise HTTPException(status_code=404, detail="thesis not found")
    return card
