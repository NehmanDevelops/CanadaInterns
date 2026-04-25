"""
main.py — FastAPI server for Canada Interns.

- Runs the ATS crawler on startup and every 10 minutes via APScheduler.
- Exposes /api/jobs and /api/jobs/latest endpoints.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

from crawler import run_crawler

load_dotenv()

logger = logging.getLogger("server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# Supabase client (reused across requests)
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()


async def _scheduled_crawl():
    """Wrapper so APScheduler can invoke the async crawler."""
    try:
        result = await run_crawler()
        logger.info(f"Scheduled crawl result: {result}")
    except Exception as exc:
        logger.error(f"Scheduled crawl failed: {exc}")


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: run crawler immediately, then schedule every 10 min
    logger.info("Running initial crawl on startup...")
    try:
        result = await run_crawler()
        logger.info(f"Initial crawl result: {result}")
    except Exception as exc:
        logger.error(f"Initial crawl failed: {exc}")

    scheduler.add_job(_scheduled_crawl, "interval", minutes=10, id="crawl_job")
    scheduler.start()
    logger.info("Scheduler started — crawling every 10 minutes")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Canada Interns API",
    description="Backend for the Canada Interns internship discovery platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "Canada Interns backend is running."}


@app.get("/api/jobs")
async def get_jobs(
    location: Optional[str] = Query(None, description="Filter by location (case-insensitive substring match)"),
    field: Optional[str] = Query(None, description="Filter by title keyword / field"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Return jobs with optional location and field (title keyword) filters.
    Results are ordered by first_seen descending (newest discoveries first).
    """
    query = supabase.table("jobs").select("*").order("first_seen", desc=True)

    if location:
        query = query.ilike("location", f"%{location}%")
    if field:
        query = query.ilike("title", f"%{field}%")

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return {"jobs": result.data, "count": len(result.data)}


@app.get("/api/jobs/latest")
async def get_latest_jobs():
    """Return the 25 most recently discovered jobs."""
    result = (
        supabase.table("jobs")
        .select("*")
        .order("first_seen", desc=True)
        .limit(25)
        .execute()
    )
    return {"jobs": result.data, "count": len(result.data)}


@app.get("/api/jobs/stats")
async def get_stats():
    """Quick stats for the dashboard."""
    total = supabase.table("jobs").select("id", count="exact").execute()
    greenhouse = (
        supabase.table("jobs")
        .select("id", count="exact")
        .eq("ats_platform", "greenhouse")
        .execute()
    )
    lever = (
        supabase.table("jobs")
        .select("id", count="exact")
        .eq("ats_platform", "lever")
        .execute()
    )
    return {
        "total_jobs": total.count,
        "greenhouse_jobs": greenhouse.count,
        "lever_jobs": lever.count,
    }
