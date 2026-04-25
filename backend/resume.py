"""
resume.py — AI-powered resume tailoring endpoints.

- POST /api/resume/analyze: Extracts text, sends to Groq LLM, returns diff + ATS scores
- POST /api/resume/download: Applies changes directly on the PDF (preserves formatting)
- GET  /api/resume/keywords: Extracts top ATS keywords from a job description
"""

import io
import json
import logging
import os
import re
from collections import Counter
from typing import Optional

import httpx
import fitz  # PyMuPDF
import pdfplumber
from fastapi import APIRouter, File, Form, UploadFile, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger("resume")

router = APIRouter(prefix="/api/resume", tags=["resume"])

# ---------------------------------------------------------------------------
# Groq API config (free tier — no billing required)
# Uses Llama 3.3 70B via Groq's OpenAI-compatible endpoint
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
GROQ_URL: str = "https://api.groq.com/openai/v1/chat/completions"


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call Groq (Llama 3.3 70B) via their OpenAI-compatible REST API."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in environment")

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------
def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract all text from a PDF using pdfplumber."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Keyword extraction & ATS scoring
# ---------------------------------------------------------------------------
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "must", "this", "that", "these", "those", "it", "its", "we", "you",
    "they", "them", "their", "our", "your", "my", "he", "she", "his",
    "her", "i", "me", "us", "not", "no", "all", "each", "every", "any",
    "some", "such", "than", "too", "very", "just", "about", "also",
    "into", "over", "after", "before", "between", "under", "above",
    "up", "down", "out", "off", "through", "during", "including",
    "the", "etc", "eg", "ie", "via", "per", "re", "vs",
    # Job posting filler
    "role", "position", "team", "company", "work", "working",
    "experience", "years", "ability", "strong", "skills",
    "required", "preferred", "responsibilities", "qualifications",
    "looking", "join", "opportunity", "will", "including",
}


def _extract_keywords(text: str, top_n: int = 20) -> list[str]:
    """Extract the most relevant ATS keywords from text."""
    words = re.findall(r"[a-zA-Z+#.]+(?:\s[a-zA-Z+#.]+)?", text.lower())
    filtered = [w.strip() for w in words if w.strip() not in STOP_WORDS and len(w.strip()) > 2]

    bigrams = []
    word_list = text.lower().split()
    for i in range(len(word_list) - 1):
        w1, w2 = word_list[i].strip(",.;:()"), word_list[i + 1].strip(",.;:()")
        if w1 not in STOP_WORDS and w2 not in STOP_WORDS and len(w1) > 2 and len(w2) > 2:
            bigrams.append(f"{w1} {w2}")

    all_terms = filtered + bigrams
    counts = Counter(all_terms)
    return [term for term, _ in counts.most_common(top_n)]


def _calculate_ats_score(resume_text: str, keywords: list[str]) -> tuple[int, list[str], list[str]]:
    """Calculate ATS match score. Returns (score, matched, missing)."""
    resume_lower = resume_text.lower()
    matched = [kw for kw in keywords if kw.lower() in resume_lower]
    missing = [kw for kw in keywords if kw.lower() not in resume_lower]
    score = int((len(matched) / max(len(keywords), 1)) * 100)
    return score, matched, missing


# ---------------------------------------------------------------------------
# ENDPOINT 1: Analyze resume against job description
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a surgical resume optimizer.
You will receive a resume and a job description.
Your job is to identify 3-6 bullet points in the resume that are most relevant to the job description and rewrite them to better match the ATS keywords in the job description.

Rules:
- ONLY rewrite bullet points under experience or projects sections
- Do NOT touch education, contact info, skills section, or section headers
- Do NOT add new bullet points
- Do NOT change the meaning or fabricate experience
- Keep rewrites to similar length as originals
- Prioritize inserting exact keywords from the job description naturally

Return ONLY a JSON array, no other text:
[
  {
    "original": "exact original bullet text",
    "replacement": "rewritten bullet text",
    "reason": "why this change improves ATS score"
  }
]"""


@router.post("/analyze")
async def analyze_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    """
    Analyze a resume against a job description.
    Returns AI-suggested changes and ATS score before/after.
    """
    # 1. Extract text from PDF
    file_bytes = await resume.read()
    resume_text = _extract_pdf_text(file_bytes)
    if not resume_text.strip():
        return {"error": "Could not extract text from the uploaded PDF."}

    # 2. Extract keywords from job description
    keywords = _extract_keywords(job_description, top_n=20)

    # 3. Calculate ATS score BEFORE
    ats_before, matched_before, missing_before = _calculate_ats_score(resume_text, keywords)

    # 4. Send to Groq (Llama 3.3 70B — free)
    try:
        raw = await _call_llm(
            SYSTEM_PROMPT,
            f"RESUME:\n{resume_text}\n\n---\n\nJOB DESCRIPTION:\n{job_description}",
        )

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        changes = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"Groq returned invalid JSON: {raw[:500]}")
        changes = []
    except Exception as exc:
        logger.error(f"Groq API error: {exc}")
        return {"error": f"AI processing failed: {str(exc)}"}

    # 5. Calculate ATS score AFTER (simulate applying changes)
    modified_text = resume_text
    for change in changes:
        original = change.get("original", "")
        replacement = change.get("replacement", "")
        if original:
            modified_text = modified_text.replace(original, replacement)

    ats_after, matched_after, missing_after = _calculate_ats_score(modified_text, keywords)

    return {
        "changes": changes,
        "ats_before": ats_before,
        "ats_after": ats_after,
        "keywords_matched": matched_after,
        "keywords_missing": missing_after,
    }


# ---------------------------------------------------------------------------
# ENDPOINT 2: Download tailored resume as PDF (preserves original formatting)
# ---------------------------------------------------------------------------
def _detect_font_size(page: fitz.Page, rect: fitz.Rect) -> float:
    """Detect the font size of text within a given rectangle."""
    blocks = page.get_text("dict", clip=rect).get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("size"):
                    return span["size"]
    return 10.0  # fallback


def _detect_font_name(page: fitz.Page, rect: fitz.Rect) -> str:
    """Detect the font name of text within a given rectangle."""
    blocks = page.get_text("dict", clip=rect).get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("font"):
                    return span["font"]
    return "helv"  # fallback (Helvetica)


def _detect_font_color(page: fitz.Page, rect: fitz.Rect) -> tuple:
    """Detect the font color of text within a given rectangle."""
    blocks = page.get_text("dict", clip=rect).get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                c = span.get("color", 0)
                if isinstance(c, int):
                    # Convert integer color to RGB tuple (0-1 range)
                    r = ((c >> 16) & 0xFF) / 255.0
                    g = ((c >> 8) & 0xFF) / 255.0
                    b = (c & 0xFF) / 255.0
                    return (r, g, b)
    return (0, 0, 0)  # fallback to black


@router.post("/download")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """
    Apply AI-suggested changes directly on the original PDF.
    Preserves all formatting, layout, fonts, and structure.
    Works best with single-column PDF resumes.
    """
    # 1. Read the original PDF
    file_bytes = await resume.read()

    # 2. Parse changes
    try:
        change_list = json.loads(changes)
    except json.JSONDecodeError:
        return {"error": "Invalid changes JSON"}

    # 3. Open with PyMuPDF and apply replacements
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    for page in doc:
        for change in change_list:
            original = change.get("original", "")
            replacement = change.get("replacement", "")
            if not original or not replacement:
                continue

            # Search using first 60 chars (handles line-wrapped text)
            search_text = original[:60]
            areas = page.search_for(search_text)

            if not areas:
                # Try shorter snippet for better matching
                search_text = original[:30]
                areas = page.search_for(search_text)

            for rect in areas:
                # Detect original text properties
                font_size = _detect_font_size(page, rect)
                font_color = _detect_font_color(page, rect)

                # Expand rect slightly to cover full text area
                # (search_for may only cover partial text)
                expanded = fitz.Rect(
                    rect.x0,
                    rect.y0 - 1,
                    page.rect.width - rect.x0,  # extend to right margin
                    rect.y1 + 1,
                )

                # White out original text
                page.draw_rect(expanded, color=(1, 1, 1), fill=(1, 1, 1))

                # Insert replacement text at the same position
                # Use a text writer for better control
                text_point = fitz.Point(rect.x0, rect.y0 + font_size * 0.85)
                page.insert_text(
                    text_point,
                    replacement,
                    fontsize=font_size,
                    color=font_color,
                )

    # 4. Save to buffer and return as PDF
    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=tailored_resume.pdf"},
    )


# ---------------------------------------------------------------------------
# ENDPOINT 3: Extract keywords from job description
# ---------------------------------------------------------------------------
@router.get("/keywords")
async def get_keywords(
    job_description: str = Query(..., description="The job description to extract keywords from"),
):
    """Extract top 20 ATS keywords from a job description."""
    keywords = _extract_keywords(job_description, top_n=20)
    return {"keywords": keywords, "count": len(keywords)}
