# Canada Interns Backend

## Stack
- FastAPI (Python)
- OpenAI GPT-4o integration
- Supabase (Postgres)
- python-docx, PyMuPDF
- JSearch API (RapidAPI)

## Setup
1. Create a Python virtual environment and activate it
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in API keys
4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## Features
- Internship aggregation (JSearch/scraping)
- Resume tailoring endpoint
- ATS scoring
- Diff preview for resumes
