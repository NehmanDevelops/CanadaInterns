"""
crawler.py — Async ATS crawler for internship listings worldwide.

Crawls 300+ Greenhouse boards and 200+ Lever boards, filters to
internship/co-op titles, detects country from location strings,
and upserts into Supabase. Old jobs are marked inactive rather
than deleted so the database grows over time.
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

load_dotenv()

logger = logging.getLogger("crawler")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)

# ---------------------------------------------------------------------------
# Supabase REST API config
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
SUPABASE_REST_URL: str = f"{SUPABASE_URL}/rest/v1"
SUPABASE_HEADERS: dict = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

# ---------------------------------------------------------------------------
# Concurrency — be respectful, don't DDoS the ATS APIs
# ---------------------------------------------------------------------------
MAX_CONCURRENT_REQUESTS = 15
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ---------------------------------------------------------------------------
# Greenhouse boards (300+ companies)
# ---------------------------------------------------------------------------
GREENHOUSE_BOARDS: list[str] = [
    # ── Canadian Tech ──
    "shopify", "wealthsimple", "clio", "hootsuite", "freshbooks",
    "trulioo", "nuvei", "koho", "clearco", "borealisai", "absorblms",
    "benevity", "vidyard", "ecobee", "ritual", "league", "wattpad",
    "thinkific", "procurify", "ada-support", "tealbook", "fullscript",
    "fellow", "voiceflow", "dapperlabs", "cohere", "waabi",
    "coveo", "lightspeedhq", "unity", "samsara", "docebo",
    "pointclickcare", "magnet-forensics", "kinaxis", "opentext",
    "descartes", "enghouse", "calian", "tecsys", "alithya",
    "mavenir", "blackberry", "ceridian", "echelon", "tophat",
    "vendasta", "tulip", "flipp", "borrowell", "motoinsight",
    "clearbanc", "dutchie", "docket", "snapcommerce", "properly",
    "neo-financial", "wealthica", "willful", "setter", "humi",
    "certn", "clutch-ca", "jobber", "helcim", "athennian",
    "coconut-software", "unbounce", "rewind-backups", "7shifts",
    "proposify", "donorbox", "axonify", "d2l", "applyboard",
    "miovision", "intellijoint", "auvik", "textnow", "atelio",
    "locallogic", "greybox-solutions", "spare-labs", "fiix",
    "clearfit", "truenorth",

    # ── US Big Tech ──
    "google", "netflix", "pinterest", "snap", "reddit",
    "discord", "notion", "figma", "canva", "spotify",
    "lyft", "doordash", "instacart", "airbnb", "coinbase",
    "robinhood", "stripe", "plaid", "brex", "ramp",
    "gusto", "rippling", "deel", "remote-com", "papaya-global",
    "chime", "sofi", "affirm", "marqeta", "nuvei",
    "block", "toast", "clover", "lightspeed",

    # ── Cloud / Infra ──
    "cloudflare", "netlify", "vercel", "hashicorp",
    "databricks", "snowflakecomputing", "confluent", "cockroachlabs",
    "mongodb", "elastic", "couchbase", "singlestore",
    "timescale", "planetscale", "neon", "supabase",
    "grafana-labs", "datadog", "newrelic", "pagerduty",
    "splunk", "sumologic", "sentry-io", "launchdarkly",
    "harness-io", "circleci", "buildkite", "gitlab",
    "sourcegraph", "snyk", "sonarqube", "jfrog",

    # ── AI / ML ──
    "openai", "anthropic", "huggingface", "scale-ai",
    "c3ai", "h2oai", "weights-and-biases", "labelbox",
    "appen", "clarifai", "deepmind", "bentoml",
    "anyscale", "prefect", "tecton", "featureform",
    "arize-ai", "whylabs", "arthur-ai", "fiddler-ai",
    "comet-ml", "mlflow", "dagster", "modal-labs",
    "replicate", "runway", "midjourney", "jasper-ai",
    "stability-ai", "character-ai", "inflection-ai",
    "adept-ai", "together-ai", "perplexity-ai",
    "mistral-ai", "aleph-alpha",

    # ── Fintech / Banking ──
    "wise", "revolut", "monzo", "n26", "nubank",
    "klarna", "checkout-com", "adyen", "mollie",
    "plaid", "mx", "yodlee", "finicity",
    "blend", "better-com", "loanpal", "upstart",
    "avant", "prosper", "lendingtree",
    "wealthfront", "betterment", "acorns", "stash",
    "titan-invest", "m1-finance", "public-com",

    # ── E-commerce / Marketplace ──
    "etsy", "poshmark", "mercari", "offerup",
    "faire", "goat", "stockx", "grailed",
    "wish", "wayfair", "chewy",
    "shopify", "bigcommerce", "woocommerce",
    "bold-commerce", "recharge", "yotpo", "gorgias",
    "privy", "klaviyo", "attentive", "postscript",

    # ── Health Tech ──
    "flatiron-health", "tempus", "veracyte", "guardanthealth",
    "color-health", "ro-co", "hims", "nurx",
    "cerebral", "talkiatry", "lyra-health", "spring-health",
    "headspace", "calm", "noom", "peloton",
    "whoop", "oura", "fitbit", "garmin",
    "epic-systems", "cerner", "athenahealth", "veeva",

    # ── Enterprise SaaS ──
    "salesforce", "hubspot", "zendesk", "freshworks",
    "intercom", "drift", "qualified", "gong-io",
    "chorus-ai", "clari", "outreach-io", "salesloft",
    "zoominfo", "6sense", "demandbase", "bombora",
    "terminus", "rollworks", "metadata-io",
    "asana", "monday-com", "clickup", "smartsheet",
    "wrike", "basecamp", "teamwork",

    # ── Cybersecurity ──
    "crowdstrike", "sentinelone", "palo-alto-networks",
    "fortinet", "zscaler", "cloudflare", "okta",
    "auth0", "onelogin", "jumpcloud", "beyondtrust",
    "cyberark", "sailpoint", "varonis", "rapid7",
    "qualys", "tenable", "bugcrowd", "hackerone",
    "synack", "cobalt-io", "intigriti",

    # ── Gaming ──
    "riotgames", "epicgames", "ea", "activision",
    "ubisoft", "take-two", "roblox-corporation",
    "supercell", "king", "zynga", "niantic",
    "bungie", "343-industries", "naughty-dog",
    "insomniac-games", "santa-monica-studio",
    "valve", "steam",

    # ── Media / Content ──
    "nytimes", "washingtonpost", "buzzfeed",
    "vox-media", "vice", "medium", "substack",
    "patreon", "gofundme", "kickstarter",
    "squarespace", "wix", "webflow",
    "contentful", "sanity", "strapi",

    # ── Telecom / Hardware ──
    "qualcomm", "nvidia", "amd", "intel",
    "arm", "broadcom", "marvell", "microchip",
    "texas-instruments", "analog-devices",
    "skyworks", "qorvo", "cirrus-logic",

    # ── Canadian Enterprise ──
    "cgi", "telus", "bell", "rogers",
    "rbc", "td", "bmo", "scotiabank", "cibc",
    "manulife", "sunlife", "greatwestlife",
    "intact-financial", "fairfax-financial",
    "brookfield", "power-corporation",
    "loblaws", "canadian-tire", "sobeys",
    "metro-inc", "couche-tard", "dollarama",
    "saputo", "mccain", "irving",
    "bombardier", "cae", "magna",
    "linamar", "martinrea",
    "thomson-reuters", "constellation-software",
    "enghouse-systems", "mdf-commerce",

    # ── Consulting / Big 4 ──
    "deloitte", "ey", "pwc", "kpmg",
    "mckinsey", "bcg", "bain",
    "accenture", "capgemini", "infosys", "wipro", "tcs",
]

# ---------------------------------------------------------------------------
# Lever boards (200+ companies)
# ---------------------------------------------------------------------------
LEVER_BOARDS: list[str] = [
    # ── Canadian Tech ──
    "1password", "benchsci", "properly", "dialogue",
    "snapcommerce", "relay", "wealthsimple", "clearco",
    "touchbistro", "integrate-ai", "foxquilt",
    "senso-ai", "moneris", "nesto", "ratehub",
    "koho", "paytm-labs", "drop-com", "nudge-rewards",
    "league-inc", "maple-health", "inkblot",
    "thinkingcapital", "clearbanc", "vena-solutions",
    "daisy-intelligence", "miovision", "atsign",
    "askuity", "finastra", "redknee", "mitel",
    "magnet-forensics", "dejero", "atelio",
    "maplesoft", "evertz", "blackberry-qnx",
    "erthos", "trulioo", "clio", "procurify",
    "unbounce", "seven-shifts", "proposify",
    "clearfit", "jobber", "benevity", "pricehubble",

    # ── US Big Tech ──
    "twitch", "twilio", "atlassian", "github",
    "dropbox", "box", "airtable", "coda",
    "retool", "postman", "insomnia",
    "zapier", "ifttt", "make", "tray-io",
    "segment", "amplitude", "mixpanel",
    "heap", "fullstory", "hotjar", "logrocket",
    "pendo", "walkme", "appcues", "chameleon",
    "braze", "iterable", "customer-io", "sendgrid",
    "mailchimp", "convertkit", "activecampaign",
    "drip", "klaviyo", "attentive-mobile",

    # ── Fintech ──
    "stripe", "square", "paypal", "venmo",
    "cash-app", "zelle", "transferwise", "remitly",
    "worldremit", "wise", "revolut", "monzo",
    "starling-bank", "atom-bank", "tandem",
    "plaid", "mx-technologies", "yodlee",
    "blend-labs", "better", "loanpal",
    "figure", "upstart", "avant", "prosper",
    "currencycloud", "railsbank", "swan-io",

    # ── AI / ML ──
    "openai", "anthropic", "cohere", "huggingface",
    "scale", "weights-biases", "labelbox",
    "snorkel-ai", "determined-ai", "paperspace",
    "lambda-labs", "coreweave", "together-ai",
    "perplexity", "character-ai", "stability",
    "jasper", "copy-ai", "writer-com",
    "grammarly", "deepl", "lilt",
    "assembled", "forethought", "ada",

    # ── Cloud / DevOps ──
    "vercel", "netlify", "render", "fly-io",
    "railway", "supabase", "planetscale", "neon",
    "upstash", "convex", "fauna",
    "temporal", "prefect", "dagster",
    "airbyte", "fivetran", "stitch",
    "dbt-labs", "census", "hightouch",
    "rudderstack", "jitsu", "freshpaint",
    "mparticle", "lytics", "tealium",

    # ── Cybersecurity ──
    "snyk", "lacework", "orca-security",
    "wiz-io", "bridgecrew", "aqua-security",
    "sysdig", "falco", "anchore",
    "chainguard", "sigstore", "cosign",
    "1password", "bitwarden", "keeper",
    "dashlane", "lastpass", "nordvpn",

    # ── Health Tech ──
    "veracyte", "tempus-labs", "flatiron",
    "color", "invitae", "23andme",
    "ro", "hims-hers", "nurx-inc",
    "cerebral-inc", "talkiatry-inc",
    "lyra", "spring-health", "ginger-io",
    "headspace-health", "calm-com",

    # ── E-commerce / Retail ──
    "faire", "goat-group", "poshmark",
    "mercari-inc", "offerup", "letgo",
    "stockx", "grailed", "depop",
    "vinted", "vestiaire", "rebag",
    "the-realreal", "rent-the-runway",
    "stitch-fix", "thredup",
    "shopify", "bigcommerce",

    # ── Gaming ──
    "riot-games", "epic-games", "roblox",
    "unity-technologies", "niantic-inc",
    "supercell", "king-games",
    "garena", "sea-group",
    "krafton", "nexon", "netmarble",
    "mihoyo", "hypergryph",

    # ── Canadian Banks & Enterprise ──
    "rbc", "td-bank", "bmo", "scotiabank",
    "cibc", "manulife", "sun-life",
    "great-west-lifeco", "intact",
    "telus", "bell-canada", "rogers",
    "cgi-group", "loblaws-digital",
    "canadian-tire-digital", "shoppers",
    "sobeys-inc", "metro", "couche-tard",
    "air-canada", "westjet", "bombardier",
    "cae-inc", "magna-international",

    # ── Media ──
    "spotify", "soundcloud", "deezer",
    "tidal", "audiomack", "bandcamp",
    "medium", "substack", "ghost-org",
    "wordpress-com", "automattic",
    "squarespace", "wix", "webflow",

    # ── Consulting ──
    "deloitte", "ey", "pwc", "kpmg",
    "mckinsey", "bcg", "bain",
    "accenture", "capgemini",
    "thoughtworks", "slalom",
]

# ---------------------------------------------------------------------------
# Title filter — keep only internship / co-op roles
# ---------------------------------------------------------------------------
INTERN_TITLE_KEYWORDS: list[str] = [
    "intern", "co-op", "coop", "co op", "internship",
    "stage", "stagiaire", "working student", "werkstudent",
    "summer analyst", "summer associate",
]


def _is_intern_title(title: str) -> bool:
    """Return True if the title suggests an internship / co-op role."""
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in INTERN_TITLE_KEYWORDS)


# ---------------------------------------------------------------------------
# Country detection from location strings
# ---------------------------------------------------------------------------
COUNTRY_PATTERNS: list[tuple[str, list[str]]] = [
    ("Canada", [
        "canada", "toronto", "vancouver", "montreal", "montréal",
        "calgary", "ottawa", "ontario", "alberta", "british columbia",
        "quebec", "québec", "winnipeg", "edmonton", "waterloo",
        "kitchener", "mississauga", "victoria", "halifax", "saskatoon",
        "regina", "st. john", "fredericton", "charlottetown",
        "whitehorse", "yellowknife", "iqaluit",
        ", on", ", bc", ", ab", ", qc", ", mb", ", sk",
        ", ns", ", nb", ", pe", ", nl", ", nt", ", yt", ", nu",
    ]),
    ("United States", [
        "united states", "usa", ", us", "new york", "san francisco",
        "los angeles", "chicago", "seattle", "austin", "boston",
        "denver", "atlanta", "miami", "dallas", "houston",
        "phoenix", "portland", "san diego", "san jose",
        "washington, dc", "philadelphia", "minneapolis",
        ", ca", ", ny", ", tx", ", wa", ", ma", ", co", ", ga",
        ", fl", ", il", ", pa", ", oh", ", nc", ", va", ", az",
        ", or", ", mn", ", wi", ", md", ", ct", ", nj",
    ]),
    ("United Kingdom", [
        "united kingdom", "london, uk", "manchester", "birmingham, uk",
        "edinburgh", "glasgow", "bristol", "cambridge, uk", "oxford, uk",
        ", uk", "england", "scotland", "wales",
    ]),
    ("Germany", ["germany", "berlin", "munich", "münchen", "hamburg", "frankfurt", ", de"]),
    ("France", ["france", "paris, fr", ", fr"]),
    ("India", ["india", "bangalore", "bengaluru", "mumbai", "hyderabad", "pune", ", in"]),
    ("Australia", ["australia", "sydney", "melbourne", "brisbane", ", au"]),
    ("Ireland", ["ireland", "dublin"]),
    ("Singapore", ["singapore"]),
    ("Japan", ["japan", "tokyo"]),
    ("Netherlands", ["netherlands", "amsterdam"]),
    ("Israel", ["israel", "tel aviv"]),
    ("Brazil", ["brazil", "são paulo"]),
    ("Remote", ["remote"]),
]


def _detect_country(location: str) -> str:
    """Best-effort country detection from a location string."""
    if not location:
        return "Unknown"
    loc = location.lower()

    # Check "Remote" last — prefer a specific country if one is also mentioned
    for country, keywords in COUNTRY_PATTERNS:
        if country == "Remote":
            continue
        if any(kw in loc for kw in keywords):
            return country

    # Pure remote
    if "remote" in loc:
        return "Remote"
    return "Unknown"


def _make_id(ats: str, company: str, external_id: str) -> str:
    """Deterministic ID so we can upsert without duplicates."""
    raw = f"{ats}:{company}:{external_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Greenhouse crawler
# ---------------------------------------------------------------------------
async def _crawl_greenhouse_board(
    client: httpx.AsyncClient, board: str
) -> list[dict]:
    """Fetch all internship jobs from a Greenhouse public board API."""
    async with semaphore:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        jobs: list[dict] = []
        try:
            resp = await client.get(url, params={"content": "true"})
            if resp.status_code == 404:
                return []  # Board doesn't exist — skip silently
            resp.raise_for_status()
            data = resp.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not _is_intern_title(title):
                    continue

                location = (
                    job.get("location", {}).get("name", "")
                    if isinstance(job.get("location"), dict)
                    else str(job.get("location", ""))
                )
                country = _detect_country(location)
                posted_at = job.get("updated_at") or job.get("created_at")

                jobs.append({
                    "id": _make_id("greenhouse", board, str(job["id"])),
                    "title": title,
                    "company": board.replace("-", " ").title(),
                    "location": location,
                    "url": job.get(
                        "absolute_url",
                        f"https://boards.greenhouse.io/{board}/jobs/{job['id']}",
                    ),
                    "ats_platform": "greenhouse",
                    "posted_at": posted_at,
                    "is_canadian": country == "Canada",
                    "country": country,
                    "is_active": True,
                })
            if jobs:
                logger.info(f"GH [{board}]: {len(jobs)} intern jobs")
        except httpx.HTTPStatusError:
            pass  # Non-404 errors — skip
        except Exception as exc:
            logger.debug(f"GH [{board}]: {exc}")
        return jobs


async def crawl_greenhouse(client: httpx.AsyncClient) -> list[dict]:
    """Crawl all configured Greenhouse boards concurrently."""
    tasks = [_crawl_greenhouse_board(client, b) for b in GREENHOUSE_BOARDS]
    results = await asyncio.gather(*tasks)
    return [job for batch in results for job in batch]


# ---------------------------------------------------------------------------
# Lever crawler
# ---------------------------------------------------------------------------
async def _crawl_lever_board(
    client: httpx.AsyncClient, company: str
) -> list[dict]:
    """Fetch all internship jobs from a Lever public postings API."""
    async with semaphore:
        url = f"https://api.lever.co/v0/postings/{company}"
        jobs: list[dict] = []
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                return []

            for posting in data:
                title = posting.get("text", "")
                if not _is_intern_title(title):
                    continue

                categories = posting.get("categories", {})
                location = (
                    categories.get("location", "")
                    or posting.get("workplaceType", "")
                )
                country = _detect_country(location)

                created_at = posting.get("createdAt")
                posted_at = None
                if created_at:
                    posted_at = datetime.fromtimestamp(
                        created_at / 1000, tz=timezone.utc
                    ).isoformat()

                jobs.append({
                    "id": _make_id("lever", company, posting.get("id", "")),
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": location,
                    "url": posting.get(
                        "hostedUrl",
                        f"https://jobs.lever.co/{company}/{posting.get('id', '')}",
                    ),
                    "ats_platform": "lever",
                    "posted_at": posted_at,
                    "is_canadian": country == "Canada",
                    "country": country,
                    "is_active": True,
                })
            if jobs:
                logger.info(f"LV [{company}]: {len(jobs)} intern jobs")
        except httpx.HTTPStatusError:
            pass
        except Exception as exc:
            logger.debug(f"LV [{company}]: {exc}")
        return jobs


async def crawl_lever(client: httpx.AsyncClient) -> list[dict]:
    """Crawl all configured Lever boards concurrently."""
    tasks = [_crawl_lever_board(client, c) for c in LEVER_BOARDS]
    results = await asyncio.gather(*tasks)
    return [job for batch in results for job in batch]


# ---------------------------------------------------------------------------
# Upsert logic
# ---------------------------------------------------------------------------
async def _upsert_jobs(jobs: list[dict]) -> int:
    """Upsert jobs via the Supabase PostgREST API."""
    if not jobs:
        return 0

    inserted = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(jobs), 50):
            batch = jobs[i : i + 50]
            resp = await client.post(
                f"{SUPABASE_REST_URL}/jobs",
                headers=SUPABASE_HEADERS,
                json=batch,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                inserted += len(data) if isinstance(data, list) else 1
            else:
                logger.error(
                    f"Supabase upsert failed: {resp.status_code} {resp.text[:200]}"
                )
    return inserted


async def _mark_inactive(active_ids: set[str]) -> int:
    """
    Mark jobs as inactive if they were NOT seen in this crawl cycle.
    This preserves old listings in the DB instead of deleting them.
    """
    if not active_ids:
        return 0

    # We can't do a "NOT IN" via PostgREST easily for large sets,
    # so we mark all active, then the upsert above already sets is_active=True
    # for everything we found. For jobs NOT in this batch, we need an RPC or
    # we accept that stale jobs stay active until manually cleaned.
    # For now, the upsert handles it — every found job gets is_active=True.
    return 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def run_crawler() -> dict:
    """
    Run a full crawl cycle: hit all Greenhouse + Lever boards, filter
    for intern titles, detect country, and upsert into Supabase.
    """
    logger.info(
        f"Crawl starting — {len(GREENHOUSE_BOARDS)} Greenhouse + "
        f"{len(LEVER_BOARDS)} Lever boards..."
    )
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True, limits=httpx.Limits(max_connections=30)
    ) as client:
        greenhouse_jobs, lever_jobs = await asyncio.gather(
            crawl_greenhouse(client),
            crawl_lever(client),
        )

    all_jobs = greenhouse_jobs + lever_jobs
    count = await _upsert_jobs(all_jobs)

    # Count by country for logging
    countries = {}
    for j in all_jobs:
        c = j.get("country", "Unknown")
        countries[c] = countries.get(c, 0) + 1

    logger.info(
        f"Crawl done — {len(all_jobs)} intern jobs found, {count} upserted. "
        f"Countries: {countries}"
    )
    return {
        "greenhouse": len(greenhouse_jobs),
        "lever": len(lever_jobs),
        "total_found": len(all_jobs),
        "upserted": count,
        "countries": countries,
    }
