"""
resume.py — AI-powered resume tailoring endpoints.

- POST /api/resume/analyze:  Extracts text, sends to Groq LLM, returns diff + ATS scores
- POST /api/resume/download: Custom PDF-to-PDF tailoring with detailed results
- POST /api/resume/tailor:   Alias for /download
- GET  /api/resume/keywords: Extracts top ATS keywords from a job description
"""

import base64
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
# Groq API config
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
GROQ_URL: str = "https://api.groq.com/openai/v1/chat/completions"


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
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
    file_bytes = await resume.read()
    resume_text = _extract_pdf_text(file_bytes)
    if not resume_text.strip():
        return {"error": "Could not extract text from the uploaded PDF."}

    keywords = _extract_keywords(job_description, top_n=20)
    ats_before, _, _ = _calculate_ats_score(resume_text, keywords)

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
        orig = change.get("original", "")
        repl = change.get("replacement", "")
        if orig:
            modified_text = modified_text.replace(orig, repl)

    ats_after, matched_after, missing_after = _calculate_ats_score(modified_text, keywords)

    return {
        "changes": changes,
        "ats_before": ats_before,
        "ats_after": ats_after,
        "keywords_matched": matched_after,
        "keywords_missing": missing_after,
    }


# ---------------------------------------------------------------------------
# PDF-to-PDF tailoring engine
# ---------------------------------------------------------------------------
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
    clean = re.sub(r"[\s\-_,]+", "", pdf_font_name.lower())
    clean = re.sub(r"(bold|italic|oblique|regular|medium|light|condensed|"
                   r"semibold|extrabold|thin|black|mt|ps|it|bi|bo)", "", clean).strip()
    if clean in FONT_MAP:
        return FONT_MAP[clean]
    for hint in SERIF_HINTS:
        if hint in clean:
            return "tiro"
    return "helv"


def _int_to_rgb(c: int) -> tuple:
    return (((c >> 16) & 0xFF) / 255.0, ((c >> 8) & 0xFF) / 255.0, (c & 0xFF) / 255.0)


def _get_font_suffix(flags: int) -> str:
    b = bool(flags & (1 << 4))
    i = bool(flags & (1 << 1))
    if b and i: return "bi"
    if b: return "bo"
    if i: return "it"
    return ""


def _build_span_index(page) -> list[dict]:
    spans = []
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                spans.append({
                    "text": text,
                    "bbox": span["bbox"],
                    "font": span.get("font", "Helvetica"),
                    "size": span.get("size", 10.0),
                    "color": span.get("color", 0),
                    "flags": span.get("flags", 0),
                    "origin": span.get("origin", (span["bbox"][0], span["bbox"][3])),
                })
    return spans


def _find_spans_for_text(spans: list[dict], search_text: str) -> list[dict]:
    """Find consecutive spans whose combined text contains search_text."""
    search_clean = search_text.strip()
    if not search_clean:
        return []

    search_norm = re.sub(r"\s+", " ", search_clean)

    for i in range(len(spans)):
        concat = ""
        window = []
        for j in range(i, min(i + 15, len(spans))):
            concat += spans[j]["text"]
            window.append(spans[j])

            concat_norm = re.sub(r"\s+", " ", concat.strip())

            if search_norm[:50] in concat_norm or concat_norm in search_norm:
                if len(concat_norm) >= min(len(search_norm), 20):
                    return window
    return []


def _compute_bounding_rect(spans: list[dict]) -> fitz.Rect:
    x0 = min(s["bbox"][0] for s in spans)
    y0 = min(s["bbox"][1] for s in spans)
    x1 = max(s["bbox"][2] for s in spans)
    y1 = max(s["bbox"][3] for s in spans)
    return fitz.Rect(x0, y0, x1, y1)


def tailor_pdf(pdf_bytes: bytes, changes: list[dict]) -> dict:
    """
    Core PDF tailoring engine with detailed logging.
    Returns dict with pdf_bytes + per-change results.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    applied = []
    failed = []

    for change in changes:
        original = change.get("original", "").strip()
        replacement = change.get("replacement", "").strip()
        if not original or not replacement:
            continue

        logger.info(f"--- Processing change ---")
        logger.info(f"  SEARCH: '{original[:80]}...'")

        found = False
        for page_num, page in enumerate(doc):
            all_spans = _build_span_index(page)
            matched = _find_spans_for_text(all_spans, original)

            if not matched:
                matched = _find_spans_for_text(all_spans, original[:40])
            if not matched:
                continue

            found = True
            ref = matched[0]
            font_base = _map_font(ref["font"])
            suffix = _get_font_suffix(ref["flags"])
            font_name = font_base + suffix if suffix else font_base
            font_size = ref["size"]
            color = _int_to_rgb(ref["color"]) if isinstance(ref["color"], int) else (0, 0, 0)

            bounds = _compute_bounding_rect(matched)
            logger.info(f"  FOUND page {page_num+1} | rect=({bounds.x0:.0f},{bounds.y0:.0f},{bounds.x1:.0f},{bounds.y1:.0f})")
            logger.info(f"  Font: {ref['font']} → {font_name} @ {font_size}pt")
            logger.info(f"  Spans: {len(matched)} | text='{' '.join(s['text'][:15] for s in matched)}'")

            text_rect = fitz.Rect(bounds.x0, bounds.y0, page.rect.width - 30, bounds.y1)

            # White out
            for span in matched:
                b = span["bbox"]
                page.draw_rect(fitz.Rect(b[0]-0.5, b[1]-0.5, page.rect.width-30, b[3]+0.5),
                               color=(1,1,1), fill=(1,1,1))

            # Insert with auto-shrink
            adjusted = font_size
            ok = False
            for _ in range(4):
                rc = page.insert_textbox(text_rect, replacement,
                                         fontname=font_name, fontsize=adjusted,
                                         color=color, align=fitz.TEXT_ALIGN_LEFT)
                if rc >= 0:
                    ok = True
                    logger.info(f"  INSERT OK @ {adjusted}pt (rc={rc:.1f})")
                    break
                adjusted -= 0.5
                # Re-white
                for span in matched:
                    b = span["bbox"]
                    page.draw_rect(fitz.Rect(b[0]-0.5, b[1]-0.5, page.rect.width-30, b[3]+0.5),
                                   color=(1,1,1), fill=(1,1,1))

            if not ok:
                logger.warning(f"  INSERT FAILED even at {adjusted}pt")

            applied.append({
                "original": original[:80],
                "replacement": replacement[:80],
                "page": page_num + 1,
                "success": ok,
            })
            break

        if not found:
            logger.warning(f"  NOT FOUND: '{original[:60]}'")
            failed.append(original)

    logger.info(f"=== SUMMARY: {len(applied)} applied, {len(failed)} failed of {len(changes)} ===")
    for f in failed:
        logger.info(f"  MISS: '{f[:60]}'")

    pdf_out = doc.tobytes()
    doc.close()
    return {
        "pdf_bytes": pdf_out,
        "changes_requested": len(changes),
        "changes_applied": len(applied),
        "applied_changes": applied,
        "failed_changes": failed,
    }


# ---------------------------------------------------------------------------
# ENDPOINT 2: Download / Tailor
# ---------------------------------------------------------------------------
@router.post("/download")
@router.post("/tailor")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """Returns JSON: base64 PDF + metadata about applied/failed changes."""
    file_bytes = await resume.read()

    try:
        change_list = json.loads(changes)
    except json.JSONDecodeError:
        return {"error": "Invalid changes JSON"}

    try:
        result = tailor_pdf(file_bytes, change_list)
    except Exception as exc:
        logger.error(f"PDF tailoring failed: {exc}", exc_info=True)
        return {"error": f"PDF tailoring failed: {str(exc)}"}

    pdf_b64 = base64.b64encode(result["pdf_bytes"]).decode("utf-8")

    return {
        "pdf_base64": pdf_b64,
        "changes_requested": result["changes_requested"],
        "changes_applied": result["changes_applied"],
        "applied_changes": result["applied_changes"],
        "failed_changes": result["failed_changes"],
    }


# ---------------------------------------------------------------------------
# ENDPOINT 3: Extract keywords
# ---------------------------------------------------------------------------
@router.get("/keywords")
async def get_keywords(
    job_description: str = Query(..., description="The job description to extract keywords from"),
):
    keywords = _extract_keywords(job_description, top_n=20)
    return {"keywords": keywords, "count": len(keywords)}
