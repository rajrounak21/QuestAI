from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.travel.flights.main import run_flight_search
from backend.auth.security import get_current_user
from backend.database.flight_sessions import (
    delete_session,
    get_session_search,
    get_session_with_latest_search,
    insert_search,
    list_session_history,
    list_session_searches,
    upsert_session_on_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flights", tags=["flights"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None


class SearchAgainIn(BaseModel):
    query: str | None = None


class FlightSegIn(BaseModel):
    flight_number: str = Field(min_length=2)
    departure_id: str = Field(min_length=3, max_length=3)
    arrival_id: str = Field(min_length=3, max_length=3)
    date: str = Field(min_length=8)


class BookingOptionsIn(BaseModel):
    booking_token: str | None = None
    departure_token: str | None = None
    outbound_flights: list[FlightSegIn] | None = None
    return_flights: list[FlightSegIn] | None = None
    departure_id: str = Field(min_length=3, max_length=3)
    arrival_id: str = Field(min_length=3, max_length=3)
    outbound_date: str = Field(min_length=8)
    return_date: str | None = None
    trip_type: str = "one_way"
    currency: str = "USD"
    travelers: int = Field(default=1, ge=1, le=9)


def _clean_seg(s: FlightSegIn) -> dict[str, str]:
    return {
        "flight_number": s.flight_number.replace(" ", "").upper(),
        "departure_id": s.departure_id.upper(),
        "arrival_id": s.arrival_id.upper(),
        "date": s.date,
    }


def _book_pair(
    outbound: list[dict[str, str]],
    ret: list[dict[str, str]],
    currency: str,
    travelers: int = 1,
) -> dict[str, Any]:
    """True round-trip booking: pins BOTH legs via selected_flights_json.

    A bare booking_token from a return option only covers that leg (proven
    live: SpiceJet checkout showed DXB→DEL alone). The pair call covers the
    whole itinerary in one booking.
    """
    import json as _json

    from backend.agents.shared.serpapi_client import search as serpapi_search

    payload = {"outbound": outbound}
    if ret:
        payload["return"] = ret
    params: dict[str, Any] = {
        "engine": "google_flights",
        "selected_flights_json": _json.dumps(payload),
        "currency": currency,
        "hl": "en",
    }
    if travelers > 1:
        params["adults"] = str(travelers)
    results = serpapi_search(params)
    return results.data


def _run_and_shape(query: str) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    """Sync SerpApi call (5-8s). Raises HTTPException on agent-level failure."""
    result = run_flight_search(query)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    if result.get("follow_up_question"):
        raise HTTPException(status_code=422, detail=result["follow_up_question"])
    flights = result.get("flights") or []
    return flights, result.get("total_results", len(flights)), result.get("extracted_params")


def _persist(
    user_id: str,
    session_id: str,
    query: str,
    flights: list[dict[str, Any]],
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    upsert_session_on_search(user_id, session_id, query, len(flights), params)
    insert_search(user_id, session_id, query, flights, params)
    return {
        "session_id": session_id,
        "query": query,
        "flights": flights,
        "flight_count": len(flights),
        "params": params,
    }


@router.post("/search")
def search(body: SearchIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    session_id = body.session_id or str(uuid.uuid4())
    logger.info(f"Flight search user={user['id']} session={session_id} q={query[:80]}")
    flights, _, params = _run_and_shape(query)
    return _persist(user["id"], session_id, query, flights, params)


@router.get("/history")
def history(limit: int = 20, user: dict = Depends(get_current_user)):
    items = list_session_history(user["id"], limit=limit)
    for it in items:
        it["_id"] = str(it["_id"])
    return {"items": items}


@router.get("/{session_id}/searches")
def list_searches(
    session_id: str, limit: int = 20, user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Every search run in this session, newest first. No SerpApi cost.

    Declared before /{session_id} so the literal path is not swallowed by it.
    """
    session, _ = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="flight session not found")
    return {"items": list_session_searches(user["id"], session_id, limit=limit)}


@router.get("/{session_id}/searches/{search_id}")
def get_search(
    session_id: str, search_id: str, user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Open one stored search from this session. Mongo only, no SerpApi call.

    Declared after the list route and before /{session_id} so neither of them
    claims the three-segment path.
    """
    doc = get_session_search(user["id"], session_id, search_id)
    if not doc:
        raise HTTPException(status_code=404, detail="search not found in this session")
    doc["_id"] = str(doc["_id"])
    doc["search_id"] = doc["_id"]
    created = doc.get("created_at")
    doc["created_at"] = created.isoformat() if created else ""
    return {"search": doc}


@router.get("/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    session, latest = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="flight session not found")
    session["_id"] = str(session["_id"])
    if latest:
        latest["_id"] = str(latest["_id"])
    return {"session": session, "latest": latest}


@router.post("/{session_id}/search")
def search_again(
    session_id: str, body: SearchAgainIn, user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Fresh SerpApi call for stale prices. Appends a new search doc."""
    session, _ = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="flight session not found")
    query = (body.query or session.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    flights, _, params = _run_and_shape(query)
    return _persist(user["id"], session_id, query, flights, params)


@router.post("/booking-options")
def booking_options(body: BookingOptionsIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """On-demand 'Book with X' options for one selected flight.

    One-way: booking_token -> options (1 extra SerpApi call). Round-trip:
    a bare return-leg booking_token only books THAT leg (proven live), so
    round trips always book via selected_flights_json pinning BOTH legs:
    outbound segments + picked return segments -> pair options covering the
    whole itinerary in one booking. Google never exposes raw airline URLs —
    each option carries a booking_request (Google redirect POST) that lands
    on the provider checkout.
    """
    from backend.agents.travel.tools.google_flights import (
        google_flights_booking_options,
        google_flights_return_options,
    )

    dep_id = body.departure_id.upper()
    arr_id = body.arrival_id.upper()
    token = body.booking_token
    travelers = max(1, body.travelers or 1)
    resolved_return: dict[str, Any] | None = None
    return_options: list[dict[str, Any]] = []

    def seg_date(t: str) -> str:
        return str(t or "").split(" ")[0]

    try:
        if body.outbound_flights and body.return_flights:
            # Explicit pair pick (round-trip return choice): one booking call.
            out = [_clean_seg(s) for s in body.outbound_flights]
            ret = [_clean_seg(s) for s in body.return_flights]
            data = _book_pair(out, ret, body.currency, travelers)
        else:
            if not token and body.departure_token:
                if not body.return_date:
                    raise HTTPException(status_code=422, detail="Return date needed for round-trip booking")
                if not body.outbound_flights:
                    raise HTTPException(
                        status_code=422,
                        detail="This saved flight is missing segment details — search again for live booking",
                    )
                ret = google_flights_return_options(
                    body.departure_token, dep_id, arr_id,
                    body.outbound_date, body.return_date, body.currency,
                    travelers,
                )
                candidates = (ret.get("best_flights") or []) + (ret.get("other_flights") or [])

                def has_segs(c: dict[str, Any]) -> bool:
                    return bool(c.get("flights"))

                candidates = [c for c in candidates if has_segs(c)]
                if not candidates:
                    raise HTTPException(status_code=502, detail="No bookable return found for this flight")
                candidates.sort(key=lambda c: c.get("price", float("inf")))

                def shape_return(c: dict[str, Any]) -> dict[str, Any]:
                    def hhmm(t: str) -> str:
                        parts = str(t or "").split(" ")
                        return parts[1] if len(parts) >= 2 else str(t or "")

                    raw_segs = c.get("flights") or []
                    first = raw_segs[0] if raw_segs else {}
                    last = raw_segs[-1] if raw_segs else {}
                    dep = first.get("departure_airport") or {}
                    arr = last.get("arrival_airport") or {}
                    shaped_segs = [
                        {
                            "flight_number": str(s.get("flight_number", "")).replace(" ", "").upper(),
                            "departure_id": (s.get("departure_airport") or {}).get("id", ""),
                            "arrival_id": (s.get("arrival_airport") or {}).get("id", ""),
                            "date": seg_date((s.get("departure_airport") or {}).get("time", "")),
                        }
                        for s in raw_segs
                    ]
                    return {
                        "price": c.get("price"),
                        "from_code": dep.get("id", ""),
                        "to_code": arr.get("id", ""),
                        "dep_time": hhmm(dep.get("time", "")),
                        "arr_time": hhmm(arr.get("time", "")),
                        "flight_no": first.get("flight_number", ""),
                        "airline": first.get("airline", ""),
                        "segments": shaped_segs,
                        "summary": (
                            f"{dep.get('id', '')} {dep.get('time', '')} → "
                            f"{arr.get('id', '')} {arr.get('time', '')} "
                            f"{first.get('flight_number', '')}".strip()
                        ),
                        "stops": max(0, len(raw_segs) - 1),
                    }

                return_options = [shape_return(c) for c in candidates[:5]]
                # Pair-book outbound + cheapest return in the same call below.
                best = return_options[0]
                data = _book_pair(
                    [_clean_seg(s) for s in (body.outbound_flights or [])],
                    best["segments"],
                    body.currency,
                    travelers,
                )
                resolved_return = {
                    "price": best.get("price"),
                    "summary": best.get("summary"),
                }
            else:
                if not token:
                    raise HTTPException(status_code=422, detail="This flight has no booking token")
                data = google_flights_booking_options(
                    token,
                    dep_id,
                    arr_id,
                    body.outbound_date,
                    return_date=body.return_date,
                    trip_type=body.trip_type,
                    currency=body.currency,
                    travelers=travelers,
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Booking options failed user={user['id']}: {e}")
        raise HTTPException(status_code=502, detail="Booking options temporarily unavailable")

    shaped: list[dict[str, Any]] = []
    for opt in data.get("booking_options", []):
        legs: list[tuple[str, dict[str, Any]]] = []
        if isinstance(opt.get("together"), dict):
            legs = [("together", opt["together"])]
        else:
            for leg in ("departing", "returning"):
                if isinstance(opt.get(leg), dict):
                    legs.append((leg, opt[leg]))
        for leg_name, leg in legs:
            req = leg.get("booking_request") or {}
            shaped.append(
                {
                    "book_with": leg.get("book_with", ""),
                    "airline": bool(leg.get("airline", False)),
                    "price": leg.get("price"),
                    "option_title": leg.get("option_title", ""),
                    "extensions": leg.get("extensions", []) or [],
                    "booking_url": req.get("url", ""),
                    "booking_post_data": req.get("post_data", ""),
                    "leg": leg_name,
                }
            )
    return {"options": shaped, "count": len(shaped), "resolved_return": resolved_return, "return_options": return_options}


@router.delete("/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    deleted = delete_session(user["id"], session_id)
    return {"deleted": deleted, "session_id": session_id}
