from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth.security import get_current_user
from backend.database.trip_sessions import (
    CONTINUE_BUMP,
    MAX_TRIP_SEARCHES,
    add_cap_extra,
    complete_trip,
    delete_trip_doc,
    fail_trip,
    get_spent,
    get_trip_doc,
    heal_stale,
    insert_new_trip,
    is_stale,
    list_history,
    mark_running,
    set_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])


class PlanIn(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None
    parent_session_id: str | None = None
    confirmed_scope: str | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1)


class SelectIn(BaseModel):
    kind: str = Field(pattern="^(flight|hotel)$")
    item_id: str = Field(min_length=1)


class PlanAccepted(BaseModel):
    session_id: str
    status: str = "running"


def _run_and_persist(
    user_id: str,
    session_id: str,
    raw_query: str,
    confirmed_scope: str | None = None,
) -> None:
    """Blocking graph run in a worker thread. Never raises to the client."""
    import json as _json

    from backend.agents.travel.agent.trip_agent import run_trip_planner
    from backend.database.trip_sessions import build_trip_context

    try:
        doc = get_trip_doc(user_id, session_id)
        if not doc:
            logger.warning(f"Trip doc vanished session={session_id}, aborting run")
            return
        if doc.get("status") == "cancelled":
            return

        # CONTINUE resumes a cap-paused trip with a bigger budget.
        if raw_query.strip().upper() == "CONTINUE" and doc.get("awaiting_kind") == "cap":
            add_cap_extra(user_id, session_id)
            convo = doc.get("conversation") or []
            if convo and convo[-1].get("user"):
                raw_query = convo[-1]["user"]

        pending = (
            doc.get("clarifying_questions") or []
            if doc.get("status") == "awaiting_input"
            else []
        )
        effective_query = raw_query
        if pending:
            convo = doc.get("conversation") or []
            base = convo[-1].get("user") if convo else doc.get("query")
            if base and base not in raw_query:
                effective_query = (
                    f"Original request: {base}\n"
                    f"User provided more details: {raw_query}"
                )
        trip = doc.get("trip") or {}
        if trip.get("destination"):
            recent = [
                {"user": t.get("user", ""), "assistant": t.get("assistant", "")}
                for t in (doc.get("conversation") or [])[-2:]
                if isinstance(t, dict)
            ]
            ctx = build_trip_context(trip, recent)
            effective_query = (
                "Current trip (JSON): "
                f"{_json.dumps(ctx, ensure_ascii=False)}\n"
                f"User message: {effective_query}"
            )

        set_progress(user_id, session_id, "planning", "Understanding your trip")
        result = run_trip_planner(
            effective_query,
            session_id=session_id,
            user_id=user_id,
            pending_questions=pending,
            confirmed_scope=confirmed_scope,
        )

        # Doc may have been deleted mid-run — don't resurrect it.
        if not get_trip_doc(user_id, session_id):
            logger.info(f"Trip deleted mid-run session={session_id}, dropping result")
            return

        clarifying = result.get("clarifying_questions") or []
        if clarifying:
            set_progress(user_id, session_id, "awaiting_input", result.get("message", ""))
            # Never wipe a ready trip with an empty one — keep stored trip
            # when the ask-path returns nothing plannable.
            kept_trip = result.get("trip") or {}
            if not kept_trip.get("destination") and (doc.get("trip") or {}).get("destination"):
                kept_trip = doc.get("trip")
            has_preview = bool(result.get("preview_trip"))
            complete_trip(
                user_id,
                session_id,
                status="awaiting_input",
                trip=kept_trip,
                clarifying_questions=clarifying,
                message=result.get("message", ""),
                user_text=raw_query,
                pending_preview=result.get("preview_trip"),
                awaiting_kind="confirm" if has_preview else None,
            )
            return

        if result.get("cap_paused"):
            spent, extra = get_spent(user_id, session_id)
            limit = MAX_TRIP_SEARCHES + extra
            complete_trip(
                user_id,
                session_id,
                status="awaiting_input",
                trip=result.get("trip"),
                clarifying_questions=[],
                message=(
                    (result.get("message", "") + " "
                     f"Search budget paused ({spent}/{limit} used). "
                     f"Reply CONTINUE for {CONTINUE_BUMP} more, or refine to narrow it.")
                    .strip()
                ),
                user_text=raw_query,
                awaiting_kind="cap",
            )
            return

        if result.get("error"):
            existing_trip = (doc.get("trip") or {}) if doc else {}
            if existing_trip.get("destination"):
                # raw_query is recorded so the optimistic bubble clears and the
                # error renders on THIS turn, not the previous one.
                complete_trip(
                    user_id,
                    session_id,
                    status="ready",
                    trip=existing_trip,
                    clarifying_questions=[],
                    message=(
                        f"Your plan is unchanged - that change was not applied.\n"
                        f"{result['error']}"
                    ).strip(),
                    user_text=raw_query,
                )
                return

            # Nothing planned yet, so there is nothing to protect.
            fail_trip(
                user_id,
                session_id,
                result.get("error") or "Trip planning failed",
                user_text=raw_query,
            )
            return

        set_progress(user_id, session_id, "done", "Trip ready")
        message = result.get("message", "")
        for warn in result.get("warnings") or []:
            message = f"{message}\n{warn}"
        if result.get("warnings"):
            logger.info(f"Trip {session_id} completed with warnings: {result['warnings']}")
        # No silent rewrites: surface what changed on an existing trip.
        old_trip = doc.get("trip") or {}
        new_trip = result.get("trip") or {}
        old_max = (old_trip.get("budget") or {}).get("max_total")
        new_max = (new_trip.get("budget") or {}).get("max_total")
        if old_max is not None and new_max is not None and old_max != new_max:
            message = f"{message}\nBudget updated: ${old_max:g} → ${new_max:g}."
        old_dur = old_trip.get("duration_days")
        new_dur = new_trip.get("duration_days")
        if old_dur is not None and new_dur is not None and old_dur != new_dur:
            message = f"{message}\nTrip length: {old_dur} → {new_dur} days."
        old_dep = old_trip.get("departure_date")
        new_dep = new_trip.get("departure_date")
        if old_dep and new_dep and old_dep != new_dep:
            message = f"{message}\nDates moved: {old_dep} → {new_dep}."
        complete_trip(
            user_id,
            session_id,
            status="ready",
            trip=result.get("trip"),
            clarifying_questions=[],
            message=message,
            user_text=raw_query,
        )
    except Exception as e:
        logger.exception(f"Trip run failed session={session_id}: {e}")
        try:
            fail_trip(
                user_id,
                session_id,
                "Something went wrong while planning that change. Please try again.",
                user_text=raw_query,
            )
        except Exception:
            pass


def _ensure_not_running(user_id: str, session_id: str) -> dict[str, Any]:
    doc = get_trip_doc(user_id, session_id)
    if doc and doc.get("status") == "running":
        if is_stale(doc) or heal_stale(user_id, session_id):
            doc = get_trip_doc(user_id, session_id)
        else:
            raise HTTPException(
                status_code=409,
                detail={"message": "trip already running", "session_id": session_id},
            )
    return doc


@router.post("/plan", status_code=202)
async def plan(body: PlanIn, tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    session_id = body.session_id or str(uuid.uuid4())
    doc = get_trip_doc(user_id, session_id)
    if not doc:
        insert_new_trip(
            user_id, session_id, query,
            parent_session_id=body.parent_session_id,
        )
    else:
        _ensure_not_running(user_id, session_id)
        mark_running(user_id, session_id)

    tasks.add_task(
        asyncio.to_thread, _run_and_persist, user_id, session_id, query,
        body.confirmed_scope,
    )
    return PlanAccepted(session_id=session_id)


@router.post("/{session_id}/chat", status_code=202)
async def chat(session_id: str, body: ChatIn, tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    doc = get_trip_doc(user_id, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="trip not found")
    _ensure_not_running(user_id, session_id)

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")
    mark_running(user_id, session_id, "Working on your update")
    tasks.add_task(asyncio.to_thread, _run_and_persist, user_id, session_id, message)
    return PlanAccepted(session_id=session_id)


@router.post("/{session_id}/select")
def select_option(session_id: str, body: SelectIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Pin a specific flight/hotel as the trip's selection.

    Instant (no LLM, no SerpApi): rewrites selected_* + budget actuals so the
    budget bar re-estimates live.
    """
    from backend.database.collections import get_trip_sessions_collection
    from datetime import datetime, timezone

    user_id = user["id"]
    col = get_trip_sessions_collection()
    doc = col.find_one({"user_id": user_id, "session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="trip not found")
    trip = doc.get("trip") or {}
    if not trip or not trip.get("destination"):
        raise HTTPException(status_code=409, detail="trip has no plan yet")

    if body.kind == "flight":
        items = trip.get("flight_results") or []
        match = next((f for f in items if f.get("id") == body.item_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="flight not in this trip")
        trip["selected_flight"] = match
        budget = trip.get("budget") or {}
        budget["flight_actual"] = match.get("price")
        trip["budget"] = budget
    else:
        items = trip.get("hotel_results") or []
        match = next((h for h in items if h.get("id") == body.item_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="hotel not in this trip")
        trip["selected_hotel"] = match
        budget = trip.get("budget") or {}
        budget["hotel_actual"] = match.get("total_price")
        trip["budget"] = budget

    col.update_one(
        {"user_id": user_id, "session_id": session_id},
        {"$set": {"trip": trip, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"trip": trip, "session_id": session_id}


@router.get("/history")
async def history(limit: int = 20, user: dict = Depends(get_current_user)):
    items = list_history(user["id"], limit=min(limit, 50))
    for it in items:
        it["_id"] = str(it["_id"])
    return {"items": items}


@router.get("/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    heal_stale(user["id"], session_id)
    doc = get_trip_doc(user["id"], session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="trip not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.delete("/{session_id}")
async def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    deleted = delete_trip_doc(user["id"], session_id)
    return {"deleted": deleted, "session_id": session_id}
