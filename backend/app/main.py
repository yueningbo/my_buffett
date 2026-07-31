from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load backend/.env (DeepSeek / OpenAI-compatible keys) before agent imports read env.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.api.routes import router

app = FastAPI(title="my_buffett", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "my_buffett", "docs": "/docs"}
