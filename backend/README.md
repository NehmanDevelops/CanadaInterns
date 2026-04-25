# Canada Interns — Backend

FastAPI backend that crawls Greenhouse and Lever ATS boards for Canadian internships and serves them via REST API.

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Fill in your Supabase URL and key

# 4. Run the SQL migration in your Supabase SQL Editor
# See migrations/001_create_jobs_table.sql

# 5. Start the server
uvicorn main:app --reload --port 8000
```

## Architecture

- **crawler.py** — Async crawler using `httpx`. Hits Greenhouse + Lever public APIs, filters to Canadian intern/co-op roles, upserts into Supabase.
- **main.py** — FastAPI server. Runs the crawler on startup and every 10 minutes via APScheduler.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/jobs` | All jobs, optional `?location=` and `?field=` filters |
| GET | `/api/jobs/latest` | 25 most recently discovered jobs |
| GET | `/api/jobs/stats` | Total counts by ATS platform |

## Companies Crawled

**Greenhouse:** Shopify, Wealthsimple, Clearco, Koho, Nuvei, Trulioo, Clio, Hootsuite, FreshBooks, Absorb LMS, Borealis AI

**Lever:** 1Password, BenchSci, Properly, Dialogue, Snapcommerce, Relay
