"""
ingestion.py
============
Document ingestion pipeline. Accepts messy legal-style documents
(PDFs, scanned images, text files) and extracts usable text content.

Strategies:
  - Native PDFs   → PyMuPDF text extraction (fast, high quality)
  - Scanned PDFs  → pdf2image + Tesseract OCR fallback
  - Images        → Tesseract OCR with preprocessing
  - Text files    → Direct read with encoding detection
"""

from __future__ import annotations

import os
import logging
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import chardet
import fitz  # PyMuPDF

from ..exceptions import OCRExecutionError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclass for the unified processed-document output
# ---------------------------------------------------------------------------

@dataclass
class ProcessedDocument:
    """Standardised output of the ingestion stage."""
    doc_id: str
    filename: str
    raw_text: str
    pages: list[dict] = field(default_factory=list)       # [{page: int, text: str}]
    ocr_used: bool = False
    confidence: float = 1.0                                # 0-1 quality estimate
    file_type: str = "unknown"
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_file_type(filepath: str) -> str:
    """Return a simplified file-type tag."""
    ext = Path(filepath).suffix.lower()
    if ext in (".pdf",):
        return "pdf"
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"):
        return "image"
    if ext in (".txt", ".md", ".csv", ".json", ".html", ".xml", ".rtf"):
        return "text"
    mime, _ = mimetypes.guess_type(filepath)
    if mime and mime.startswith("image/"):
        return "image"
    return "text"  # default fallback


def _read_text_file(filepath: str) -> str:
    """Read a text file with automatic encoding detection."""
    raw = Path(filepath).read_bytes()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    return raw.decode(encoding, errors="replace")


def _extract_pdf_native(filepath: str) -> tuple[str, list[dict], bool]:
    """
    Try native text extraction with PyMuPDF.
    Returns (full_text, pages_list, needs_ocr).
    """
    doc = fitz.open(filepath)
    pages = []
    full_text_parts = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text") or ""
        text = text.strip()
        total_chars += len(text)
        pages.append({"page": page_num + 1, "text": text})
        full_text_parts.append(text)

    doc.close()

    # Heuristic: if very little text was extracted, likely a scanned PDF
    needs_ocr = total_chars < 50 * len(pages)  # <50 chars/page avg
    full_text = "\n\n".join(full_text_parts)
    return full_text, pages, needs_ocr


def _extract_pdf_ocr(filepath: str) -> tuple[str, list[dict]]:
    """
    OCR fallback for scanned PDFs.
    Uses pdf2image to rasterise + Tesseract for recognition.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        logger.warning("OCR dependencies not installed: %s", exc)
        return "", []

    # Check for TESSERACT_CMD env var
    tess_cmd = os.getenv("TESSERACT_CMD")
    if tess_cmd and os.path.exists(tess_cmd):
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    try:
        images = convert_from_path(filepath, dpi=300)
    except Exception as exc:
        logger.error("pdf2image failed (is poppler installed?): %s", exc)
        return "", []

    pages = []
    full_text_parts = []
    try:
        for idx, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang="eng")
            text = text.strip()
            pages.append({"page": idx + 1, "text": text})
            full_text_parts.append(text)
    except Exception as exc:
        logger.error("OCR execution failed (is Tesseract installed?): %s", exc)
        raise OCRExecutionError(
            "Tesseract OCR engine failed. Please ensure Tesseract-OCR is installed "
            "on the host system and either on the system PATH or defined in TESSERACT_CMD in .env.",
            details=str(exc)
        ) from exc

    return "\n\n".join(full_text_parts), pages


def _extract_image_ocr(filepath: str) -> str:
    """OCR an image file."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter
    except ImportError as exc:
        logger.warning("OCR dependencies not installed: %s", exc)
        return ""

    tess_cmd = os.getenv("TESSERACT_CMD")
    if tess_cmd and os.path.exists(tess_cmd):
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    img = Image.open(filepath)
    # Light preprocessing — convert to grayscale, sharpen
    img = img.convert("L").filter(ImageFilter.SHARPEN)
    try:
        text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception as exc:
        logger.error("OCR execution failed on image: %s", exc)
        raise OCRExecutionError(
            "Tesseract OCR engine failed or is not installed on the host system. "
            "Please install Tesseract-OCR and add it to system PATH or configure TESSERACT_CMD in .env.",
            details=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def ingest_document(filepath: str, doc_id: Optional[str] = None) -> ProcessedDocument:
    """
    Ingest a single document and return a ProcessedDocument.

    Parameters
    ----------
    filepath : str
        Path to the document file.
    doc_id : str, optional
        Custom identifier; defaults to the filename stem.

    Returns
    -------
    ProcessedDocument
    """
    filepath = str(Path(filepath).resolve())
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Document not found: {filepath}")

    fname = Path(filepath).name
    doc_id = doc_id or Path(filepath).stem
    ftype = _detect_file_type(filepath)

    logger.info("Ingesting [%s] type=%s  → %s", doc_id, ftype, fname)

    raw_text = ""
    pages: list[dict] = []
    ocr_used = False
    confidence = 1.0

    # ----- PDF -----
    if ftype == "pdf":
        raw_text, pages, needs_ocr = _extract_pdf_native(filepath)
        if needs_ocr:
            logger.info("Native extraction sparse — falling back to OCR")
            raw_text, pages = _extract_pdf_ocr(filepath)
            ocr_used = True
            confidence = 0.75  # OCR text is less reliable

    # ----- Image -----
    elif ftype == "image":
        raw_text = _extract_image_ocr(filepath)
        pages = [{"page": 1, "text": raw_text}]
        ocr_used = True
        confidence = 0.70

    # ----- Text -----
    else:
        raw_text = _read_text_file(filepath)
        pages = [{"page": 1, "text": raw_text}]

    # Quality estimate refinement
    if raw_text:
        # Penalise for excessive garbage characters
        garbage_ratio = sum(1 for c in raw_text if c in "□■●◆◇▲▼►◄") / max(len(raw_text), 1)
        confidence = max(0.0, confidence - garbage_ratio * 5)

    return ProcessedDocument(
        doc_id=doc_id,
        filename=fname,
        raw_text=raw_text,
        pages=pages,
        ocr_used=ocr_used,
        confidence=round(confidence, 3),
        file_type=ftype,
        metadata={"source_path": filepath, "file_size_bytes": os.path.getsize(filepath)},
    )
