"""Verify a failed trip run persists its turn.

The bug this guards: fail_trip() only $set the status. The user's message was
never pushed to `conversation`, so the frontend's optimistic bubble never got
cleared ("sending…" forever) and the error rendered under the PREVIOUS
message instead of the turn that failed.

Runs entirely against a throwaway session id and cleans up after itself.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database.collections import get_trip_sessions_collection  # noqa: E402
from backend.database.trip_sessions import (  # noqa: E402
    complete_trip,
    fail_trip,
    get_trip_doc,
    insert_new_trip,
)

UID = "verify-failed-trip-user"


def main() -> int:
    sid = f"verify-{uuid.uuid4().hex[:12]}"
    failures: list[str] = []

    try:
        insert_new_trip(UID, sid, "5-day trip from Mumbai to Bali for 2 people")
        col = get_trip_sessions_collection()

        print("=== 1. a successful turn IS recorded ===")
        complete_trip(
            UID, sid, status="ready", trip={"destination": "Bali"},
            message="Your Bali trip is ready!", user_text="make the budget 2000",
        )
        convo = get_trip_doc(UID, sid).get("conversation") or []
        if len(convo) != 1 or convo[0].get("user") != "make the budget 2000":
            failures.append(f"success turn not persisted: {convo}")
        else:
            print(f"  {len(convo)} turn(s), last user text present  OK")

        print("\n=== 2. a FAILED run must also record its turn ===")
        fail_trip(
            UID, sid,
            "Something went wrong while planning that change. Please try again.",
            user_text="7 days now",
        )
        doc = get_trip_doc(UID, sid)
        convo = doc.get("conversation") or []

        if doc.get("status") != "failed":
            failures.append(f"status is {doc.get('status')}, expected failed")
        else:
            print("  status = failed  OK")

        if len(convo) != 2:
            failures.append(f"failed turn NOT persisted (convo={len(convo)}, expected 2)")
        else:
            print(f"  {len(convo)} turns, failed turn is last  OK")

        if convo[-1].get("user") != "7 days now":
            failures.append(f"failed turn holds wrong text: {convo[-1].get('user')!r}")
        else:
            print("  failed turn carries the user's own message  OK")

        print("\n=== 3. the frontend echo can now resolve ===")
        # This mirrors TripThread.jsx: the echo clears when the server text
        # appears in the conversation.
        echo = "7 days now"
        echoed_back = any(t.get("user") == echo for t in convo)
        if not echoed_back:
            failures.append("echo would never clear - 'sending...' would stick")
        else:
            print("  echo text found in conversation -> bubble clears  OK")

        print("\n=== 4. the error renders on the RIGHT turn ===")
        is_last_failed = convo[-1] is convo[-1] and doc.get("status") == "failed"
        if not is_last_failed:
            failures.append("last turn is not the failed one")
        else:
            print("  isLast && status==failed -> 'Try again' on the failed turn  OK")

        print("\n=== 5. failed run clears pending preview/kind ===")
        complete_trip(
            UID, sid, status="awaiting_input", trip={"destination": "Bali"},
            message="pick a return", user_text="x",
            pending_preview={"origin": "DEL"}, awaiting_kind="confirm",
        )
        fail_trip(UID, sid, "boom", user_text="7 days now")
        doc = get_trip_doc(UID, sid)
        if doc.get("pending_preview") is not None or doc.get("awaiting_kind") is not None:
            failures.append("stale pending_preview/awaiting_kind left behind")
        else:
            print("  pending_preview and awaiting_kind cleared  OK")

        print("\n=== 6. old 3-arg call still works (heal_stale) ===")
        fail_trip(UID, sid, "Trip run stopped unexpectedly. Please try again.")
        doc = get_trip_doc(UID, sid)
        if doc.get("status") != "failed" or not doc.get("error"):
            failures.append("3-arg fail_trip broke")
        else:
            print(f"  status={doc['status']}  OK")

        print("\n=== 7. error message is truncated like before ===")
        fail_trip(UID, sid, "x" * 900)
        doc = get_trip_doc(UID, sid)
        if len(doc.get("error") or "") != 500:
            failures.append(f"error not truncated: {len(doc.get('error') or '')}")
        else:
            print("  capped at 500 chars  OK")

    finally:
        get_trip_sessions_collection().delete_many({"user_id": UID, "session_id": sid})
        print(f"\ncleaned test session {sid}")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL FAILED-RUN CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())