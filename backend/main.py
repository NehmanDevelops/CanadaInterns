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
import httpx

from crawler import run_crawler

load_dotenv()

logger = logging.getLogger("server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# Supabase REST API config
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
SUPABASE_REST: str = f"{SUPABASE_URL}/rest/v1"
SB_HEADERS: dict = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

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
    version="0.2.0",
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
    location: Optional[str] = Query(None, description="Filter by location substring"),
    field: Optional[str] = Query(None, description="Filter by title keyword"),
    country: Optional[str] = Query(None, description="Filter by country (e.g. Canada)"),
    active_only: bool = Query(True, description="Only show active listings"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Return jobs with optional filters.
    Results ordered by first_seen descending (newest discoveries first).
    """
    url = f"{SUPABASE_REST}/jobs?select=*&order=posted_at.desc.nullslast&offset={offset}&limit={limit}"
    if location:
        url += f"&location=ilike.*{location}*"
    if field:
        url += f"&title=ilike.*{field}*"
    if country:
        url += f"&country=eq.{country}"
    if active_only:
        url += "&is_active=eq.true"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=SB_HEADERS)
        data = resp.json() if resp.status_code == 200 else []
    return {"jobs": data, "count": len(data)}


@app.get("/api/jobs/latest")
async def get_latest_jobs(
    country: Optional[str] = Query(None, description="Filter by country"),
):
    """Return the 25 most recently discovered jobs."""
    url = f"{SUPABASE_REST}/jobs?select=*&order=posted_at.desc.nullslast&limit=25&is_active=eq.true"
    if country:
        url += f"&country=eq.{country}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=SB_HEADERS)
        data = resp.json() if resp.status_code == 200 else []
    return {"jobs": data, "count": len(data)}


@app.get("/api/jobs/stats")
async def get_stats():
    """Quick stats for the dashboard."""
    headers = {**SB_HEADERS, "Prefer": "count=exact"}
    async with httpx.AsyncClient(timeout=10) as client:
        total = await client.head(f"{SUPABASE_REST}/jobs?select=id", headers=headers)
        active = await client.head(f"{SUPABASE_REST}/jobs?select=id&is_active=eq.true", headers=headers)
        canada = await client.head(f"{SUPABASE_REST}/jobs?select=id&country=eq.Canada&is_active=eq.true", headers=headers)
        gh = await client.head(f"{SUPABASE_REST}/jobs?select=id&ats_platform=eq.greenhouse&is_active=eq.true", headers=headers)
        lv = await client.head(f"{SUPABASE_REST}/jobs?select=id&ats_platform=eq.lever&is_active=eq.true", headers=headers)

    def _count(resp):
        return int(resp.headers.get("content-range", "*/0").split("/")[-1])

    return {
        "total_jobs": _count(total),
        "active_jobs": _count(active),
        "canadian_jobs": _count(canada),
        "greenhouse_jobs": _count(gh),
        "lever_jobs": _count(lv),
    }


@app.get("/api/jobs/countries")
async def get_countries():
    """Return distinct countries for filter dropdowns."""
    url = f"{SUPABASE_REST}/jobs?select=country&is_active=eq.true&order=country"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=SB_HEADERS)
        data = resp.json() if resp.status_code == 200 else []
    # Deduplicate
    countries = sorted(set(item["country"] for item in data if item.get("country")))
    return {"countries": countries}
