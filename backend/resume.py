"""
resume.py — AI-powered resume tailoring endpoints.

- POST /api/resume/analyze: Extracts text, sends to Gemini, returns diff + ATS scores
- POST /api/resume/download: Applies changes and returns a formatted DOCX
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
import pdfplumber
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fastapi import APIRouter, File, Form, UploadFile, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger("resume")

router = APIRouter(prefix="/api/resume", tags=["resume"])

# ---------------------------------------------------------------------------
# Gemini API config (free tier)
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL: str = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini 2.0 Flash via REST API and return the text response."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract text from Gemini response
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini returned no content")
    return parts[0].get("text", "")


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

    # 4. Send to Gemini 2.0 Flash (free)
    try:
        raw = await _call_gemini(
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
        logger.error(f"Gemini returned invalid JSON: {raw[:500]}")
        changes = []
    except Exception as exc:
        logger.error(f"Gemini API error: {exc}")
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
# ENDPOINT 2: Download tailored resume as DOCX
# ---------------------------------------------------------------------------
@router.post("/download")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """
    Apply AI-suggested changes to a resume and return as a formatted DOCX.
    """
    # 1. Extract text
    file_bytes = await resume.read()
    resume_text = _extract_pdf_text(file_bytes)

    # 2. Parse changes
    try:
        change_list = json.loads(changes)
    except json.JSONDecodeError:
        return {"error": "Invalid changes JSON"}

    # 3. Apply replacements
    modified_text = resume_text
    for change in change_list:
        original = change.get("original", "")
        replacement = change.get("replacement", "")
        if original:
            modified_text = modified_text.replace(original, replacement)

    # 4. Build DOCX
    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    # Set margins (1 inch)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Parse text into structured sections
    lines = modified_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers (all caps or short bold-looking lines)
        is_header = (
            stripped.isupper()
            and len(stripped) < 60
            and len(stripped) > 2
        )

        if is_header:
            para = doc.add_paragraph()
            run = para.add_run(stripped)
            run.bold = True
            run.font.size = Pt(12)
            run.font.name = "Calibri"
            para.space_after = Pt(4)
            para.space_before = Pt(12)
        elif stripped.startswith(("•", "-", "–", "▪", "►", "○")):
            # Bullet point
            clean = stripped.lstrip("•-–▪►○ ")
            para = doc.add_paragraph(clean, style="List Bullet")
            for run in para.runs:
                run.font.name = "Calibri"
                run.font.size = Pt(11)
        else:
            para = doc.add_paragraph(stripped)
            for run in para.runs:
                run.font.name = "Calibri"
                run.font.size = Pt(11)

    # 5. Save to buffer and return
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=tailored_resume.docx"},
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
