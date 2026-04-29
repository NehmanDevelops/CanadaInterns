"""
resume.py — AI-powered resume tailoring endpoints.

- POST /api/resume/analyze:  Extracts text, sends to Groq LLM, returns diff + ATS scores
- POST /api/resume/download: Custom PDF-to-PDF tailoring (PyMuPDF insert_textbox)
- POST /api/resume/tailor:   Alias for /download
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
# PDF text extraction (plain text for AI analysis)
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
    file_bytes = await resume.read()
    resume_text = _extract_pdf_text(file_bytes)
    if not resume_text.strip():
        return {"error": "Could not extract text from the uploaded PDF."}

    keywords = _extract_keywords(job_description, top_n=20)
    ats_before, matched_before, missing_before = _calculate_ats_score(resume_text, keywords)

    try:
        raw = await _call_llm(
            SYSTEM_PROMPT,
            f"RESUME:\n{resume_text}\n\n---\n\nJOB DESCRIPTION:\n{job_description}",
        )
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
# PDF-to-PDF tailoring engine (custom PyMuPDF approach)
# ---------------------------------------------------------------------------

# Map common PDF font names to fitz built-in fonts
FONT_MAP = {
    "times": "tiro", "timesnewroman": "tiro", "timesnewromanps": "tiro",
    "times-roman": "tiro", "tiro": "tiro", "cambria": "tiro",
    "garamond": "tiro", "georgia": "tiro", "palatino": "tiro",
    "bookantiqua": "tiro", "baskerville": "tiro",
    "helvetica": "helv", "arial": "helv", "arialmt": "helv",
    "helv": "helv", "calibri": "helv", "verdana": "helv",
    "tahoma": "helv", "segoeui": "helv", "roboto": "helv",
    "inter": "helv", "lato": "helv", "opensans": "helv",
    "montserrat": "helv", "poppins": "helv",
    "courier": "cour", "couriernew": "cour", "cour": "cour",
}

SERIF_HINTS = {"times", "roman", "serif", "garamond", "georgia", "cambria",
               "palatino", "book", "antiqua", "tiro", "caslon", "baskerville"}


def _map_font(pdf_font_name: str) -> str:
    """Map a PDF font name to closest fitz built-in font."""
    clean = re.sub(r"[\s\-_,]+", "", pdf_font_name.lower())
    clean = re.sub(r"(bold|italic|oblique|regular|medium|light|condensed|"
                   r"semibold|extrabold|thin|black|mt|ps|it|bi|bo)", "", clean).strip()

    if clean in FONT_MAP:
        return FONT_MAP[clean]
    for hint in SERIF_HINTS:
        if hint in clean:
            logger.info(f"Font '{pdf_font_name}' → tiro (serif match)")
            return "tiro"
    logger.info(f"Font '{pdf_font_name}' → helv (sans-serif fallback)")
    return "helv"


def _int_to_rgb(color_int: int) -> tuple:
    """Convert integer color to (r, g, b) tuple in 0-1 range."""
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return (r, g, b)


def _get_font_suffix(flags: int) -> str:
    """Get bold/italic suffix from span flags."""
    is_bold = bool(flags & (1 << 4))
    is_italic = bool(flags & (1 << 1))
    if is_bold and is_italic:
        return "bi"
    elif is_bold:
        return "bo"
    elif is_italic:
        return "it"
    return ""


def _build_span_index(page) -> list[dict]:
    """Extract all text spans from a page with their full properties."""
    spans = []
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:  # text blocks only
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                spans.append({
                    "text": text,
                    "bbox": span["bbox"],  # (x0, y0, x1, y1)
                    "font": span.get("font", "Helvetica"),
                    "size": span.get("size", 10.0),
                    "color": span.get("color", 0),
                    "flags": span.get("flags", 0),
                    "origin": span.get("origin", (span["bbox"][0], span["bbox"][3])),
                })
    return spans


def _find_spans_for_text(spans: list[dict], search_text: str) -> list[dict]:
    """
    Find the sequence of consecutive spans whose combined text
    contains the search_text. Returns the matched spans.
    """
    search_clean = search_text.strip()
    if not search_clean:
        return []

    # Try to find a window of spans whose concatenated text contains search_text
    for i in range(len(spans)):
        concat = ""
        window = []
        for j in range(i, min(i + 15, len(spans))):
            concat += spans[j]["text"]
            window.append(spans[j])

            # Normalize whitespace for comparison
            concat_norm = re.sub(r"\s+", " ", concat.strip())
            search_norm = re.sub(r"\s+", " ", search_clean)

            if search_norm[:50] in concat_norm or concat_norm in search_norm:
                # Verify enough overlap
                if len(concat_norm) >= min(len(search_norm), 20):
                    return window

    return []


def _compute_bounding_rect(spans: list[dict]) -> fitz.Rect:
    """Compute the bounding rectangle of a list of spans."""
    x0 = min(s["bbox"][0] for s in spans)
    y0 = min(s["bbox"][1] for s in spans)
    x1 = max(s["bbox"][2] for s in spans)
    y1 = max(s["bbox"][3] for s in spans)
    return fitz.Rect(x0, y0, x1, y1)


def tailor_pdf(pdf_bytes: bytes, changes: list[dict]) -> bytes:
    """
    Core PDF tailoring function.
    Opens the original PDF, finds each original text, whites it out,
    and inserts the replacement text at the exact same position
    using insert_textbox for proper wrapping.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page in doc:
        # Build full span index for this page
        all_spans = _build_span_index(page)

        for change in changes:
            original = change.get("original", "").strip()
            replacement = change.get("replacement", "").strip()
            if not original or not replacement:
                continue

            # Find spans matching original text
            matched = _find_spans_for_text(all_spans, original)

            if not matched:
                # Try with shorter text
                matched = _find_spans_for_text(all_spans, original[:40])

            if not matched:
                logger.warning(f"Could not find text in PDF: '{original[:50]}...'")
                continue

            # Extract font properties from first matched span
            ref = matched[0]
            font_name_raw = ref["font"]
            font_size = ref["size"]
            color_int = ref["color"]
            flags = ref["flags"]

            font_base = _map_font(font_name_raw)
            suffix = _get_font_suffix(flags)
            font_name = font_base + suffix if suffix else font_base

            color = _int_to_rgb(color_int) if isinstance(color_int, int) else (0, 0, 0)

            # Compute bounding rect of all matched spans
            bounds = _compute_bounding_rect(matched)

            # Extend to right margin (bullets often span full width)
            right_margin = page.rect.width - bounds.x0
            text_rect = fitz.Rect(
                bounds.x0,
                bounds.y0,
                min(bounds.x0 + right_margin, page.rect.width - 30),
                bounds.y1,
            )

            # --- White out all matched span areas ---
            for span in matched:
                bbox = span["bbox"]
                whiteout = fitz.Rect(
                    bbox[0] - 0.5,
                    bbox[1] - 0.5,
                    page.rect.width - 30,  # extend to right margin
                    bbox[3] + 0.5,
                )
                page.draw_rect(whiteout, color=(1, 1, 1), fill=(1, 1, 1))

            # --- Insert replacement text ---
            # Use insert_textbox for automatic word wrapping within bounds
            adjusted_size = font_size

            # Try fitting text, reduce size if needed (max -1pt)
            for attempt in range(3):
                rc = page.insert_textbox(
                    text_rect,
                    replacement,
                    fontname=font_name,
                    fontsize=adjusted_size,
                    color=color,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
                if rc >= 0:
                    # Text fit successfully
                    break
                else:
                    # rc < 0 means text didn't fit, reduce size
                    adjusted_size -= 0.5
                    # White out again (previous attempt left partial text)
                    for span in matched:
                        bbox = span["bbox"]
                        page.draw_rect(
                            fitz.Rect(bbox[0] - 0.5, bbox[1] - 0.5,
                                      page.rect.width - 30, bbox[3] + 0.5),
                            color=(1, 1, 1), fill=(1, 1, 1),
                        )

    result = doc.tobytes()
    doc.close()
    return result


# ---------------------------------------------------------------------------
# ENDPOINT 2: Download / Tailor — Custom PDF-to-PDF
# ---------------------------------------------------------------------------
@router.post("/download")
@router.post("/tailor")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """
    Custom PDF-to-PDF tailoring. Finds original bullet text in the PDF,
    whites it out, and inserts replacement text at exact same coordinates
    with matching font, size, and color. Returns modified PDF.
    """
    file_bytes = await resume.read()

    try:
        change_list = json.loads(changes)
    except json.JSONDecodeError:
        return {"error": "Invalid changes JSON"}

    try:
        pdf_bytes = tailor_pdf(file_bytes, change_list)
    except Exception as exc:
        logger.error(f"PDF tailoring failed: {exc}", exc_info=True)
        return {"error": f"PDF tailoring failed: {str(exc)}"}

    buffer = io.BytesIO(pdf_bytes)
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
