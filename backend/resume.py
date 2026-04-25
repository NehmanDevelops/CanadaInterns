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

# Map PDF font names to closest available fitz built-in font
FONT_MAP = {
    "timesnewroman": "tiro",
    "timesnewromanps": "tiro",
    "times": "tiro",
    "times-roman": "tiro",
    "tiro": "tiro",
    "helvetica": "helv",
    "arial": "helv",
    "arialmt": "helv",
    "helv": "helv",
    "courier": "cour",
    "couriernew": "cour",
    "cour": "cour",
    "calibri": "helv",
    "cambria": "tiro",
    "garamond": "tiro",
    "georgia": "tiro",
    "palatino": "tiro",
    "bookantiqua": "tiro",
    "verdana": "helv",
    "tahoma": "helv",
    "trebuchet": "helv",
    "trebuchetms": "helv",
    "segoeui": "helv",
    "roboto": "helv",
    "inter": "helv",
    "lato": "helv",
    "opensans": "helv",
    "sourcesanspro": "helv",
    "montserrat": "helv",
    "poppins": "helv",
    "nunito": "helv",
    "raleway": "helv",
}

# Common serif font name fragments (for fallback detection)
SERIF_HINTS = {"times", "roman", "serif", "garamond", "georgia", "cambria",
               "palatino", "book", "antiqua", "tiro", "caslon", "baskerville"}


def _map_font(pdf_font_name: str) -> str:
    """Map a PDF font name to the closest available fitz built-in font."""
    # Normalize: lowercase, strip spaces/hyphens/dashes
    clean = re.sub(r"[\s\-_,]+", "", pdf_font_name.lower())
    # Remove style suffixes like -Bold, -Italic, -BoldItalic
    clean = re.sub(r"(bold|italic|oblique|regular|medium|light|condensed|semibold|extrabold|thin|black|mt|ps)", "", clean)
    clean = clean.strip()

    if clean in FONT_MAP:
        return FONT_MAP[clean]

    # Check if it looks like a serif font
    for hint in SERIF_HINTS:
        if hint in clean:
            logger.warning(f"Custom font detected: {pdf_font_name}, using closest match (tiro/serif)")
            return "tiro"

    # Default to sans-serif
    logger.warning(f"Custom font detected: {pdf_font_name}, using closest match (helv/sans-serif)")
    return "helv"


def _int_color_to_rgb(color_int: int) -> tuple:
    """Convert an integer color value to an RGB tuple (0-1 range)."""
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return (r, g, b)


def _find_matching_spans(page: fitz.Page, search_text: str) -> list[dict]:
    """
    Find all spans in the page whose text contains part of search_text.
    Returns a list of span dicts with full font properties.
    """
    matched_spans = []
    blocks = page.get_text("dict")["blocks"]

    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                # Check if this span's text is part of the search text
                if span_text.strip() and span_text.strip() in search_text:
                    matched_spans.append({
                        "text": span_text,
                        "font": span.get("font", "Helvetica"),
                        "size": span.get("size", 10.0),
                        "color": span.get("color", 0),
                        "flags": span.get("flags", 0),
                        "origin": span.get("origin", (0, 0)),
                        "bbox": span.get("bbox", (0, 0, 0, 0)),
                    })
    return matched_spans


@router.post("/download")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """
    Apply AI-suggested changes directly on the original PDF.
    Extracts exact font properties from the original text and
    reinserts replacement text with matching font, size, color, and position.
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
        # Pre-extract all text spans with their properties
        all_spans = []
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    all_spans.append(span)

        for change in change_list:
            original = change.get("original", "")
            replacement = change.get("replacement", "")
            if not original or not replacement:
                continue

            # --- Step 1: Find spans that contain the original text ---
            # Build a concatenated text from consecutive spans to find the match
            matched_span_indices = []
            for i, span in enumerate(all_spans):
                span_text = span.get("text", "").strip()
                if not span_text:
                    continue

                # Check if this span starts our search text
                if span_text[:20] in original[:30] and len(span_text) > 3:
                    # Found a potential start — collect consecutive spans
                    concat = ""
                    indices = []
                    for j in range(i, min(i + 8, len(all_spans))):
                        concat += all_spans[j].get("text", "") + " "
                        indices.append(j)
                        # Check if we've accumulated enough text
                        if original[:40] in concat or concat.strip()[:40] in original:
                            matched_span_indices = indices
                            break
                    if matched_span_indices:
                        break

            if not matched_span_indices:
                # Fallback: use search_for with shorter text
                search_text = original[:50]
                areas = page.search_for(search_text)
                if not areas:
                    search_text = original[:25]
                    areas = page.search_for(search_text)
                if not areas:
                    continue

                # Use the first match area and detect font from it
                rect = areas[0]
                clip_spans = []
                for span in all_spans:
                    sbbox = span.get("bbox", (0, 0, 0, 0))
                    srect = fitz.Rect(sbbox)
                    if srect.intersects(rect):
                        clip_spans.append(span)

                if clip_spans:
                    ref_span = clip_spans[0]
                else:
                    # Absolute fallback
                    ref_span = {
                        "font": "Helvetica", "size": 10.0,
                        "color": 0, "flags": 0,
                        "origin": (rect.x0, rect.y0 + 10),
                        "bbox": tuple(rect),
                    }

                # White out all matched areas
                for area in areas:
                    expanded = fitz.Rect(
                        area.x0 - 1, area.y0 - 1,
                        page.rect.width - 36, area.y1 + 1,
                    )
                    page.draw_rect(expanded, color=(1, 1, 1), fill=(1, 1, 1))

                # Also white out any continuation lines
                for cs in clip_spans:
                    cb = cs.get("bbox", (0, 0, 0, 0))
                    page.draw_rect(
                        fitz.Rect(cb[0] - 1, cb[1] - 1, page.rect.width - 36, cb[3] + 1),
                        color=(1, 1, 1), fill=(1, 1, 1),
                    )

                font_size = ref_span["size"]
                font_name = _map_font(ref_span["font"])
                color_val = ref_span["color"]
                font_color = _int_color_to_rgb(color_val) if isinstance(color_val, int) else (0, 0, 0)
                origin = ref_span["origin"]
                ref_bbox = ref_span["bbox"]
                is_bold = bool(ref_span["flags"] & (1 << 4))
                is_italic = bool(ref_span["flags"] & (1 << 1))

                # Apply bold/italic suffix to font
                if is_bold and is_italic:
                    font_name = font_name + "bi"
                elif is_bold:
                    font_name = font_name + "bo"
                elif is_italic:
                    font_name = font_name + "it"

                # Calculate available width for text
                right_margin = page.rect.width - 36
                available_width = right_margin - origin[0]

                # Auto-shrink if replacement is too long
                adjusted_size = font_size
                while adjusted_size > 6:
                    test_length = fitz.get_text_length(replacement, fontname=font_name, fontsize=adjusted_size)
                    if test_length <= available_width:
                        break
                    adjusted_size -= 0.5

                text_point = fitz.Point(origin[0], origin[1])
                page.insert_text(
                    text_point,
                    replacement,
                    fontname=font_name,
                    fontsize=adjusted_size,
                    color=font_color,
                )
                continue

            # --- Step 2: Extract font properties from matched spans ---
            ref_span = all_spans[matched_span_indices[0]]
            font_size = ref_span.get("size", 10.0)
            font_name_raw = ref_span.get("font", "Helvetica")
            font_name = _map_font(font_name_raw)
            color_val = ref_span.get("color", 0)
            font_color = _int_color_to_rgb(color_val) if isinstance(color_val, int) else (0, 0, 0)
            origin = ref_span.get("origin", (0, 0))
            is_bold = bool(ref_span.get("flags", 0) & (1 << 4))
            is_italic = bool(ref_span.get("flags", 0) & (1 << 1))

            # Apply bold/italic suffix
            if is_bold and is_italic:
                font_name = font_name + "bi"
            elif is_bold:
                font_name = font_name + "bo"
            elif is_italic:
                font_name = font_name + "it"

            # --- Step 3: White out all matched span areas ---
            for idx in matched_span_indices:
                span = all_spans[idx]
                bbox = span.get("bbox", (0, 0, 0, 0))
                whiteout = fitz.Rect(
                    bbox[0] - 1,
                    bbox[1] - 1,
                    page.rect.width - 36,  # extend to right margin
                    bbox[3] + 1,
                )
                page.draw_rect(whiteout, color=(1, 1, 1), fill=(1, 1, 1))

            # --- Step 4: Insert replacement at exact same position ---
            right_margin = page.rect.width - 36
            available_width = right_margin - origin[0]

            # Auto-shrink fontsize if replacement is longer
            adjusted_size = font_size
            while adjusted_size > 6:
                test_length = fitz.get_text_length(replacement, fontname=font_name, fontsize=adjusted_size)
                if test_length <= available_width:
                    break
                adjusted_size -= 0.5

            text_point = fitz.Point(origin[0], origin[1])
            page.insert_text(
                text_point,
                replacement,
                fontname=font_name,
                fontsize=adjusted_size,
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
