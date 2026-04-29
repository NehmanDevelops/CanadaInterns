"""
resume.py — AI-powered resume tailoring endpoints.

- POST /api/resume/analyze: Extracts text, sends to Groq LLM, returns diff + ATS scores
- POST /api/resume/download: Rebuilds resume as DOCX mirroring PDF, converts to PDF
- GET  /api/resume/keywords: Extracts top ATS keywords from a job description
"""

import io
import json
import logging
import os
import re
import tempfile
import subprocess
from collections import Counter
from pathlib import Path
from typing import Optional

import httpx
import pdfplumber
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
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
# PDF structure extraction (with font info for DOCX rebuild)
# ---------------------------------------------------------------------------
def _extract_pdf_structure(file_bytes: bytes) -> list[dict]:
    """
    Extract structured lines from PDF with font size info.
    Returns list of dicts: {text, font_size, is_bold, x0, x1, top, page}
    """
    lines = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract characters with their properties
            chars = page.chars
            if not chars:
                text = page.extract_text()
                if text:
                    for line_text in text.split("\n"):
                        if line_text.strip():
                            lines.append({
                                "text": line_text.strip(),
                                "font_size": 10.0,
                                "is_bold": False,
                                "x0": 0,
                                "page": page_num,
                            })
                continue

            # Group characters into lines by their top position
            char_lines: dict[float, list] = {}
            for char in chars:
                # Round top to group chars on same line
                top_key = round(char["top"], 1)
                if top_key not in char_lines:
                    char_lines[top_key] = []
                char_lines[top_key].append(char)

            # Sort by vertical position
            for top_key in sorted(char_lines.keys()):
                line_chars = sorted(char_lines[top_key], key=lambda c: c["x0"])
                if not line_chars:
                    continue

                line_text = "".join(c.get("text", "") for c in line_chars).strip()
                if not line_text:
                    continue

                # Get dominant font size for this line
                sizes = [c.get("size", 10.0) for c in line_chars if c.get("text", "").strip()]
                font_size = max(set(sizes), key=sizes.count) if sizes else 10.0

                # Detect bold from font name
                font_names = [c.get("fontname", "") for c in line_chars if c.get("text", "").strip()]
                is_bold = any("bold" in fn.lower() or "heavy" in fn.lower() for fn in font_names)
                is_italic = any("italic" in fn.lower() or "oblique" in fn.lower() for fn in font_names)

                x0 = line_chars[0].get("x0", 0)

                lines.append({
                    "text": line_text,
                    "font_size": round(font_size, 1),
                    "is_bold": is_bold,
                    "is_italic": is_italic,
                    "x0": round(x0, 1),
                    "page": page_num,
                })

    return lines


# ---------------------------------------------------------------------------
# Line classification for resume structure
# ---------------------------------------------------------------------------
BULLET_CHARS = "•\u2022\u2013\u2014\u25aa\u25ba\u25cb\u25e6\u2023\u2043\u00b7"
SECTION_HEADERS = {
    "education", "experience", "work experience", "professional experience",
    "projects", "skills", "technical skills", "certifications", "awards",
    "achievements", "summary", "objective", "interests", "activities",
    "volunteer", "publications", "references", "leadership", "coursework",
    "relevant coursework", "extracurricular", "languages", "honors",
}


def _classify_line(line: dict, max_font_size: float, median_font_size: float) -> str:
    """Classify a line as name, contact, header, job_title, company_date, bullet, or text."""
    text = line["text"]
    size = line["font_size"]
    is_bold = line["is_bold"]

    # NAME: largest font on the page
    if size >= max_font_size - 0.5 and size > median_font_size + 2:
        return "name"

    # CONTACT: has email, phone, or link indicators
    if ("@" in text or re.search(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", text)
            or "linkedin" in text.lower() or "github" in text.lower()
            or "|" in text and len(text.split("|")) >= 2):
        if size <= median_font_size + 1:
            return "contact"

    # SECTION HEADER: all caps, or matches known headers, or bold + larger font
    text_lower = text.lower().strip().rstrip(":")
    if text_lower in SECTION_HEADERS:
        return "header"
    if text.isupper() and len(text) < 40 and len(text) > 1:
        return "header"
    if is_bold and size > median_font_size + 0.5 and len(text) < 50:
        return "header"

    # BULLET: starts with bullet character or dash
    stripped = text.lstrip()
    if stripped and stripped[0] in BULLET_CHARS + "-*":
        return "bullet"

    # JOB TITLE: bold, medium length, not too small
    if is_bold and not text.isupper() and len(text) < 80:
        return "job_title"

    # COMPANY/DATE: contains date patterns or italic
    if re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|present|\d{4})", text.lower()):
        if line.get("is_italic") or not is_bold:
            return "company_date"

    return "text"


# ---------------------------------------------------------------------------
# DOCX builder that mirrors PDF structure
# ---------------------------------------------------------------------------
def _add_bottom_border(paragraph):
    """Add a thin bottom border line under a paragraph (like HR under section headers)."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")  # thin line
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _set_paragraph_spacing(paragraph, before_pt=0, after_pt=0, line_spacing_pt=None):
    """Set exact paragraph spacing."""
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(int(before_pt * 20)))  # twips
    spacing.set(qn("w:after"), str(int(after_pt * 20)))
    if line_spacing_pt is not None:
        spacing.set(qn("w:line"), str(int(line_spacing_pt * 20)))
        spacing.set(qn("w:lineRule"), "exact")
    pPr.append(spacing)


def _build_resume_docx(structured_lines: list[dict], changes: list[dict]) -> Document:
    """
    Build a DOCX document that mirrors the PDF structure.
    Applies AI-suggested bullet replacements during rebuild.
    """
    # Build a replacement map
    replacements = {}
    for change in changes:
        orig = change.get("original", "").strip()
        repl = change.get("replacement", "").strip()
        if orig and repl:
            replacements[orig] = repl

    doc = Document()

    # Page margins matching standard resume
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(10)

    # Calculate font size stats for classification
    all_sizes = [l["font_size"] for l in structured_lines]
    if not all_sizes:
        return doc
    max_font_size = max(all_sizes)
    sorted_sizes = sorted(all_sizes)
    median_font_size = sorted_sizes[len(sorted_sizes) // 2]

    for line in structured_lines:
        line_type = _classify_line(line, max_font_size, median_font_size)
        text = line["text"]

        if line_type == "name":
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(text)
            run.bold = True
            run.font.size = Pt(16)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(0, 0, 0)
            _set_paragraph_spacing(para, before_pt=0, after_pt=2)

        elif line_type == "contact":
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(text)
            run.font.size = Pt(10)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(51, 51, 51)
            _set_paragraph_spacing(para, before_pt=0, after_pt=1)

        elif line_type == "header":
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = para.add_run(text.upper())
            run.bold = True
            run.font.size = Pt(11)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(0, 0, 0)
            _set_paragraph_spacing(para, before_pt=10, after_pt=2)
            _add_bottom_border(para)

        elif line_type == "job_title":
            para = doc.add_paragraph()
            run = para.add_run(text)
            run.bold = True
            run.font.size = Pt(10.5)
            run.font.name = "Calibri"
            _set_paragraph_spacing(para, before_pt=6, after_pt=0)

        elif line_type == "company_date":
            para = doc.add_paragraph()
            run = para.add_run(text)
            run.italic = True
            run.font.size = Pt(10)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(68, 68, 68)
            _set_paragraph_spacing(para, before_pt=0, after_pt=1)

        elif line_type == "bullet":
            # Strip existing bullet char
            clean_text = text.lstrip(BULLET_CHARS + "-* \t")

            # Check if this bullet should be replaced
            final_text = clean_text
            for orig_text, repl_text in replacements.items():
                # Try matching with and without bullet chars
                orig_clean = orig_text.lstrip(BULLET_CHARS + "-* \t")
                if orig_clean in clean_text or clean_text in orig_clean:
                    final_text = repl_text.lstrip(BULLET_CHARS + "-* \t")
                    break

            para = doc.add_paragraph()
            # Add bullet character with hanging indent
            run_bullet = para.add_run("•  ")
            run_bullet.font.size = Pt(10)
            run_bullet.font.name = "Calibri"
            run_text = para.add_run(final_text)
            run_text.font.size = Pt(10)
            run_text.font.name = "Calibri"

            # Set hanging indent (bullet hangs, text aligns)
            pPr = para._p.get_or_add_pPr()
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), "360")    # overall indent
            ind.set(qn("w:hanging"), "180")  # bullet hangs
            pPr.append(ind)

            _set_paragraph_spacing(para, before_pt=1, after_pt=1)

        else:
            # Regular text
            para = doc.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(10)
            run.font.name = "Calibri"
            _set_paragraph_spacing(para, before_pt=1, after_pt=1)

    return doc


# ---------------------------------------------------------------------------
# DOCX to PDF conversion
# ---------------------------------------------------------------------------
def _convert_docx_to_pdf(docx_bytes: bytes) -> Optional[bytes]:
    """
    Convert DOCX to PDF using available tools.
    Tries: docx2pdf (MS Word), LibreOffice, or returns None.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docx_path = Path(tmp_dir) / "resume.docx"
        pdf_path = Path(tmp_dir) / "resume.pdf"

        docx_path.write_bytes(docx_bytes)

        # Try docx2pdf (uses MS Word on Windows)
        try:
            from docx2pdf import convert
            convert(str(docx_path), str(pdf_path))
            if pdf_path.exists():
                return pdf_path.read_bytes()
        except Exception as e:
            logger.warning(f"docx2pdf failed: {e}")

        # Try LibreOffice headless
        for cmd in ["libreoffice", "soffice", r"C:\Program Files\LibreOffice\program\soffice.exe"]:
            try:
                result = subprocess.run(
                    [cmd, "--headless", "--convert-to", "pdf", "--outdir", tmp_dir, str(docx_path)],
                    capture_output=True, timeout=30,
                )
                if pdf_path.exists():
                    return pdf_path.read_bytes()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    return None


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
# ENDPOINT 2: Download tailored resume (PDF or DOCX)
# Extracts PDF structure → rebuilds as DOCX → converts to PDF
# ---------------------------------------------------------------------------
@router.post("/download")
async def download_resume(
    resume: UploadFile = File(...),
    changes: str = Form(...),
):
    """
    Rebuild the resume as a formatted DOCX with AI changes applied,
    then convert to PDF if possible. Falls back to DOCX download.
    """
    # 1. Read the original PDF
    file_bytes = await resume.read()

    # 2. Parse changes
    try:
        change_list = json.loads(changes)
    except json.JSONDecodeError:
        return {"error": "Invalid changes JSON"}

    # 3. Extract structure from PDF
    structured_lines = _extract_pdf_structure(file_bytes)
    if not structured_lines:
        return {"error": "Could not extract structure from PDF"}

    # 4. Build DOCX mirroring the PDF with changes applied
    docx_doc = _build_resume_docx(structured_lines, change_list)

    # 5. Save DOCX to buffer
    docx_buffer = io.BytesIO()
    docx_doc.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    # 6. Try converting DOCX to PDF
    pdf_bytes = _convert_docx_to_pdf(docx_bytes)

    if pdf_bytes:
        # Return as PDF
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=tailored_resume.pdf"},
        )
    else:
        # Fallback: return DOCX
        logger.info("PDF conversion not available, returning DOCX")
        docx_buffer.seek(0)
        return StreamingResponse(
            docx_buffer,
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
