# Canada Interns

Canada Interns is a full-stack web application for discovering Canadian internships and tailoring resumes with AI for better job matching.

## Features
- Internship board with real-time listings (JSearch API or scraping)
- AI-powered resume tailoring (OpenAI GPT-4o)
- Save and track internships
- Clean, editorial Canadian UI
- Supabase Auth/Clerk authentication
- Resume diff and ATS score preview

## Tech Stack
- **Frontend:** Next.js 14 (App Router), Tailwind CSS, Supabase Auth/Clerk
- **Backend:** FastAPI (Python), OpenAI GPT-4o, python-docx, PyMuPDF, Supabase, JSearch API
- **Database:** Supabase (Postgres)

## Monorepo Structure
- `/frontend` — Next.js app
- `/backend` — FastAPI app
- `/seed` — Seed data (10 fake internships)

## Setup
1. Copy `.env.example` to `.env` and fill in your keys
2. See `/frontend/README.md` and `/backend/README.md` for local setup
3. Seed the database with `/seed/seed_internships.sql`

## License
MIT
