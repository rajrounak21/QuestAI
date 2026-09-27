from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from shopping_agent.agent.shopping_agent import run_shopping_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopping", tags=["shopping"])


class ShoppingSearchQuery(BaseModel):
    query: str


@router.post("/search")
async def search_shopping(body: ShoppingSearchQuery) -> dict[str, Any]:
    logger.info(f"Shopping search request: {body.query}")
    result = run_shopping_search(body.query)

    if result.get("error"):
        return {
            "products": [],
            "total_results": 0,
            "error": result["error"],
        }

    if result.get("follow_up_question"):
        return {
            "products": [],
            "total_results": 0,
            "follow_up_question": result["follow_up_question"],
        }

    return {
        "products": result["products"],
        "total_results": result["total_results"],
        "progress_steps": result.get("progress_steps", []),
    }
