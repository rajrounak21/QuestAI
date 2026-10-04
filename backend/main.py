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
from backend.agents.shopping.api.router import router as shopping_router
from backend.agents.job.api.router import router as jobs_router
from backend.agents.job.api.alerts_router import router as job_alerts_router
from backend.agents.travel.flights.api.router import router as flights_router
from backend.agents.travel.hotels.api.router import router as hotels_router
from backend.agents.travel.trips.api.router import router as trips_router
from backend.agents.assistant.api.router import router as assistant_router
from backend.agents.router.api.router import router as agent_router
from backend.database.collections import ensure_research_indexes, ensure_shopping_indexes, ensure_flight_indexes, ensure_hotel_indexes, ensure_trip_indexes, ensure_job_indexes

app = FastAPI(title="QuestAI API", version="0.1.0")

_cors_origins = {
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    config.FRONTEND_URL,
}
_cors_origins.update(
    origin.strip()
    for origin in config.EXTRA_CORS_ORIGINS.split(",")
    if origin.strip()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Required for Authlib OAuth flow (stores state/nonce)
app.add_middleware(SessionMiddleware, secret_key=config.JWT_SECRET_KEY)

app.include_router(auth_router)
app.include_router(research_router)
app.include_router(shopping_router)
app.include_router(flights_router)
app.include_router(hotels_router)
app.include_router(trips_router)
# Universal layer: the intent router and the conversational Assistant. Mounted
# before the dynamic /{session_id} routers are irrelevant here because these
# own distinct first path segments (/api/agent, /api/assistant).
app.include_router(agent_router)
app.include_router(assistant_router)
# job_alerts_router must be mounted BEFORE jobs_router: jobs_router owns
# GET /api/jobs/{session_id}, and "/api/jobs/alerts" has the same segment count,
# so mounting jobs first would swallow it and 401 the alert list.
app.include_router(job_alerts_router)
app.include_router(jobs_router)


@app.on_event("startup")
def _ensure_indexes():
    try:
        ensure_research_indexes()
    except Exception:
        pass  # DB unreachable at boot; routes will surface errors per-request
    try:
        ensure_shopping_indexes()
    except Exception:
        pass
    try:
        ensure_flight_indexes()
    except Exception:
        pass
    try:
        ensure_hotel_indexes()
    except Exception:
        pass
    try:
        ensure_trip_indexes()
    except Exception:
        pass
    try:
        ensure_job_indexes()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "services": ["auth", "research", "shopping", "flights", "hotels", "trips", "jobs", "job-alerts", "agent-router", "assistant"]}


@app.get("/")
def root():
    return {"message": "QuestAI API — POST /api/auth/signup or /api/auth/login, research at /api/research/run, shopping at /api/shopping/search, flights at /api/flights/search, hotels at /api/hotels/search, docs at /docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=config.AUTH_PORT, reload=True)
