from __future__ import annotations

import io
import logging
import os
import sys

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_agent.api.alert_routes import router as alert_router
from job_agent.api.job_routes import router as job_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"))],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="QuestAI Job Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(job_router)
app.include_router(alert_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "QuestAI Job Agent - use POST /api/jobs/search (multipart query+resume) or POST /api/jobs/search-json"}

# Also mount shopping for unified dev if desired (optional)
try:
    from shopping_agent.api.shopping_routes import router as shopping_router

    app.include_router(shopping_router)
    logger.info("Mounted shopping routes alongside job routes")
except Exception as e:
    logger.info(f"Shopping routes not mounted: {e}")
