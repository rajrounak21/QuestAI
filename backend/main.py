from __future__ import annotations

import os
import sys

# Allow running as: uvicorn backend.main:app --port 8000
_project_root = os.path.join(os.path.dirname(__file__), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.auth import config
from backend.auth.routes import router as auth_router
from backend.agents.research.api.router import router as research_router
from backend.database.collections import ensure_research_indexes

app = FastAPI(title="QuestAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Required for Authlib OAuth flow (stores state/nonce)
app.add_middleware(SessionMiddleware, secret_key=config.JWT_SECRET_KEY)

app.include_router(auth_router)
app.include_router(research_router)


@app.on_event("startup")
def _ensure_indexes():
    try:
        ensure_research_indexes()
    except Exception:
        pass  # DB unreachable at boot; routes will surface errors per-request


@app.get("/health")
def health():
    return {"status": "ok", "services": ["auth", "research"]}


@app.get("/")
def root():
    return {"message": "QuestAI API — POST /api/auth/signup or /api/auth/login, research at /api/research/run, docs at /docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=config.AUTH_PORT, reload=True)
