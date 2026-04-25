"""
crawler.py — Async Greenhouse + Lever ATS crawler for Canadian internships.

Hits public ATS APIs directly (no third-party job boards), filters to
Canadian locations and intern/co-op titles, then upserts into Supabase.
"""

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger("crawler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# Company boards to crawl
# ---------------------------------------------------------------------------
GREENHOUSE_BOARDS: list[str] = [
    "shopify",
    "wealthsimple",
    "clearco",
    "koho",
    "nuvei",
    "trulioo",
    "clio",
    "hootsuite",
    "freshbooks",
    "absorblms",
    "borealisai",
]

LEVER_BOARDS: list[str] = [
    "1password",
    "benchsci",
    "properly",
    "dialogue",
    "snapcommerce",
    "relay",
]

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
CANADIAN_LOCATION_KEYWORDS: list[str] = [
    "toronto", "vancouver", "montreal", "montréal", "calgary", "ottawa",
    "ontario", "alberta", "british columbia", "quebec", "québec",
    "remote canada", "canada", "winnipeg", "edmonton", "waterloo",
    "kitchener", "mississauga", "victoria", "halifax",
    # Province codes
    ", on", ", bc", ", ab", ", qc", ", mb", ", sk", ", ns", ", nb", ", pe", ", nl",
]

INTERN_TITLE_KEYWORDS: list[str] = [
    "intern", "co-op", "coop", "co op", "internship", "stage", "stagiaire",
]


def _is_canadian(location: str) -> bool:
    """Return True if the location string looks Canadian."""
    if not location:
        return False
    loc = location.lower()
    return any(kw in loc for kw in CANADIAN_LOCATION_KEYWORDS)


def _is_intern_title(title: str) -> bool:
    """Return True if the title suggests an internship / co-op role."""
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in INTERN_TITLE_KEYWORDS)


def _make_id(ats: str, company: str, external_id: str) -> str:
    """Deterministic ID so we can upsert without duplicates."""
    raw = f"{ats}:{company}:{external_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Greenhouse crawler
# ---------------------------------------------------------------------------
async def _crawl_greenhouse_board(client: httpx.AsyncClient, board: str) -> list[dict]:
    """Fetch all jobs from a Greenhouse public board API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    jobs: list[dict] = []
    try:
        resp = await client.get(url, params={"content": "true"})
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            location = job.get("location", {}).get("name", "") if isinstance(job.get("location"), dict) else str(job.get("location", ""))
            title = job.get("title", "")

            if not _is_canadian(location) or not _is_intern_title(title):
                continue

            posted_at = job.get("updated_at") or job.get("created_at")
            jobs.append({
                "id": _make_id("greenhouse", board, str(job["id"])),
                "title": title,
                "company": board.replace("-", " ").title(),
                "location": location,
                "url": job.get("absolute_url", f"https://boards.greenhouse.io/{board}/jobs/{job['id']}"),
                "ats_platform": "greenhouse",
                "posted_at": posted_at,
                "is_canadian": True,
            })
        logger.info(f"Greenhouse [{board}]: found {len(jobs)} Canadian intern jobs")
    except httpx.HTTPStatusError as exc:
        logger.warning(f"Greenhouse [{board}]: HTTP {exc.response.status_code}")
    except Exception as exc:
        logger.warning(f"Greenhouse [{board}]: {exc}")
    return jobs


async def crawl_greenhouse(client: httpx.AsyncClient) -> list[dict]:
    """Crawl all configured Greenhouse boards concurrently."""
    tasks = [_crawl_greenhouse_board(client, board) for board in GREENHOUSE_BOARDS]
    results = await asyncio.gather(*tasks)
    return [job for batch in results for job in batch]


# ---------------------------------------------------------------------------
# Lever crawler
# ---------------------------------------------------------------------------
async def _crawl_lever_board(client: httpx.AsyncClient, company: str) -> list[dict]:
    """Fetch all jobs from a Lever public postings API."""
    url = f"https://api.lever.co/v0/postings/{company}"
    jobs: list[dict] = []
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        for posting in data:
            categories = posting.get("categories", {})
            location = categories.get("location", "") or posting.get("workplaceType", "")
            title = posting.get("text", "")

            if not _is_canadian(location) or not _is_intern_title(title):
                continue

            created_at = posting.get("createdAt")
            posted_at = None
            if created_at:
                # Lever returns epoch-ms
                posted_at = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()

            jobs.append({
                "id": _make_id("lever", company, posting.get("id", "")),
                "title": title,
                "company": company.replace("-", " ").title(),
                "location": location,
                "url": posting.get("hostedUrl", f"https://jobs.lever.co/{company}/{posting.get('id', '')}"),
                "ats_platform": "lever",
                "posted_at": posted_at,
                "is_canadian": True,
            })
        logger.info(f"Lever [{company}]: found {len(jobs)} Canadian intern jobs")
    except httpx.HTTPStatusError as exc:
        logger.warning(f"Lever [{company}]: HTTP {exc.response.status_code}")
    except Exception as exc:
        logger.warning(f"Lever [{company}]: {exc}")
    return jobs


async def crawl_lever(client: httpx.AsyncClient) -> list[dict]:
    """Crawl all configured Lever boards concurrently."""
    tasks = [_crawl_lever_board(client, company) for company in LEVER_BOARDS]
    results = await asyncio.gather(*tasks)
    return [job for batch in results for job in batch]


# ---------------------------------------------------------------------------
# Upsert logic
# ---------------------------------------------------------------------------
def _upsert_jobs(jobs: list[dict]) -> int:
    """
    Upsert jobs into Supabase.
    Uses the deterministic `id` as the conflict target so duplicates are
    updated rather than inserted again.  `first_seen` is only set on the
    first insert (default now()).
    """
    if not jobs:
        return 0

    inserted = 0
    # Batch in chunks of 50 to stay within Supabase limits
    for i in range(0, len(jobs), 50):
        batch = jobs[i : i + 50]
        # On conflict, update everything EXCEPT first_seen so the original
        # discovery timestamp is preserved.
        result = (
            supabase.table("jobs")
            .upsert(
                batch,
                on_conflict="id",
                ignore_duplicates=False,
            )
            .execute()
        )
        inserted += len(result.data) if result.data else 0
    return inserted


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def run_crawler() -> dict:
    """
    Run a full crawl cycle: hit all Greenhouse + Lever boards, filter,
    and upsert into Supabase.  Returns a summary dict.
    """
    logger.info("Crawl cycle starting...")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        greenhouse_jobs, lever_jobs = await asyncio.gather(
            crawl_greenhouse(client),
            crawl_lever(client),
        )

    all_jobs = greenhouse_jobs + lever_jobs
    count = _upsert_jobs(all_jobs)
    logger.info(f"Crawl cycle done — {len(all_jobs)} jobs found, {count} upserted")
    return {
        "greenhouse": len(greenhouse_jobs),
        "lever": len(lever_jobs),
        "total_found": len(all_jobs),
        "upserted": count,
    }
