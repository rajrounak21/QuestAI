from __future__ import annotations

import logging
import os
import sys
import io
from typing import Any

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from travel_agent.agent.flight_agent import run_flight_search
from travel_agent.agent.hotel_agent import run_hotel_search
from travel_agent.agent.trip_agent import run_trip_planner, run_trip_chat, get_trip, delete_trip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"))],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="QuestAI Travel Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FlightSearchQuery(BaseModel):
    query: str


class HotelSearchQuery(BaseModel):
    query: str


@app.post("/api/travel/flights/search")
async def search_flights(body: FlightSearchQuery) -> dict[str, Any]:
    logger.info(f"Flight search request: {body.query}")

    result = run_flight_search(body.query)

    if result.get("error"):
        return {
            "flights": [],
            "total_results": 0,
            "error": result["error"],
        }

    if result.get("follow_up_question"):
        return {
            "flights": [],
            "total_results": 0,
            "follow_up_question": result["follow_up_question"],
        }

    return {
        "flights": result["flights"],
        "total_results": result["total_results"],
        "progress_steps": result.get("progress_steps", []),
    }


@app.post("/api/travel/hotels/search")
async def search_hotels(body: HotelSearchQuery) -> dict[str, Any]:
    logger.info(f"Hotel search request: {body.query}")

    result = run_hotel_search(body.query)

    if result.get("error"):
        return {
            "hotels": [],
            "total_results": 0,
            "error": result["error"],
        }

    if result.get("follow_up_question"):
        return {
            "hotels": [],
            "total_results": 0,
            "follow_up_question": result["follow_up_question"],
        }

    return {
        "hotels": result["hotels"],
        "total_results": result["total_results"],
        "progress_steps": result.get("progress_steps", []),
    }


class TripPlanQuery(BaseModel):
    query: str
    session_id: str | None = None


class TripChatQuery(BaseModel):
    message: str


@app.post("/api/travel/trips/plan")
async def plan_trip(body: TripPlanQuery) -> dict[str, Any]:
    logger.info(f"Trip plan request: {body.query}")

    result = run_trip_planner(body.query, session_id=body.session_id)

    return {
        "trip": result["trip"],
        "message": result["message"],
        "error": result.get("error"),
        "clarifying_questions": result.get("clarifying_questions", []),
        "progress_steps": result.get("progress_steps", []),
    }


@app.post("/api/travel/trips/{session_id}/chat")
async def trip_chat(session_id: str, body: TripChatQuery) -> dict[str, Any]:
    logger.info(f"Trip chat request: {session_id} - {body.message}")

    result = run_trip_chat(session_id, body.message)

    return {
        "trip": result["trip"],
        "message": result["message"],
        "error": result.get("error"),
        "clarifying_questions": result.get("clarifying_questions", []),
        "progress_steps": result.get("progress_steps", []),
    }


@app.get("/api/travel/trips/{session_id}")
async def get_trip_session(session_id: str) -> dict[str, Any]:
    trip = get_trip(session_id)
    if not trip:
        return {"error": "Trip not found"}
    return {"trip": trip}


@app.delete("/api/travel/trips/{session_id}")
async def delete_trip_session(session_id: str) -> dict[str, Any]:
    deleted = delete_trip(session_id)
    return {"deleted": deleted}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
