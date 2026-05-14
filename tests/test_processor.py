"""
test_processor.py
=================
Unit tests for the document processing pipeline.
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.document_processor.ingestion import ingest_document, _detect_file_type
from src.document_processor.preprocessor import clean_text, detect_sections, compute_quality_score
from src.document_processor.structured_extractor import extract_structured_data


# ── File type detection ──
def test_detect_file_type_pdf():
    assert _detect_file_type("report.pdf") == "pdf"

def test_detect_file_type_image():
    assert _detect_file_type("scan.png") == "image"
    assert _detect_file_type("photo.jpg") == "image"

def test_detect_file_type_text():
    assert _detect_file_type("notes.txt") == "text"
    assert _detect_file_type("data.json") == "text"


# ── Text cleaning ──
def test_clean_text_removes_control_chars():
    text = "Hello\x00World\x01!"
    result = clean_text(text)
    assert "\x00" not in result
    assert "\x01" not in result

def test_clean_text_fixes_hyphenation():
    text = "docu-\nment"
    result = clean_text(text)
    assert result == "document"

def test_clean_text_collapses_newlines():
    text = "paragraph1\n\n\n\n\nparagraph2"
    result = clean_text(text)
    assert "\n\n\n" not in result


# ── Section detection ──
def test_detect_sections_finds_headers():
    text = "SECTION 1: Introduction\nSome content here.\n\nSECTION 2: Background\nMore content."
    sections = detect_sections(text)
    assert len(sections) >= 2

def test_detect_sections_fallback():
    text = "Just a simple paragraph with no headings."
    sections = detect_sections(text)
    assert len(sections) == 1
    assert sections[0]["title"] == "Full Document"


# ── Quality scoring ──
def test_quality_score_empty():
    assert compute_quality_score("") == 0.0

def test_quality_score_good_text():
    text = "This is a well-formed sentence with proper English words."
    score = compute_quality_score(text)
    assert score > 0.5

def test_quality_score_garbage():
    text = "##$%^&*()_+==!!@@##$$%%^^&&**"
    score = compute_quality_score(text)
    assert score <= 0.5


# ── Structured extraction ──
def test_extract_dates():
    text = "The agreement was signed on January 15, 2024."
    result = extract_structured_data(text)
    assert len(result["dates"]) >= 1

def test_extract_case_number():
    text = "Case No. 2024-CV-03892 filed in the district court."
    result = extract_structured_data(text)
    assert len(result["case_numbers"]) >= 1

def test_extract_monetary():
    text = "The purchase price is $3,500,000.00."
    result = extract_structured_data(text)
    assert "$3,500,000.00" in result["amounts"]

def test_extract_parties():
    text = "Plaintiff: Greenfield Properties LLC\nDefendant: Harborview Capital Partners"
    result = extract_structured_data(text)
    assert len(result["parties"]) >= 2

def test_document_classification():
    text = "This Agreement is entered into by the parties. The parties agree to the terms and conditions."
    result = extract_structured_data(text)
    assert result["document_type"] == "contract"


# ── Integration: ingest a sample document ──
def test_ingest_text_file():
    sample = os.path.join(os.path.dirname(__file__), "..", "sample_documents", "contract_draft.txt")
    if not os.path.exists(sample):
        pytest.skip("Sample document not available")

    doc = ingest_document(sample)
    assert doc.doc_id == "contract_draft"
    assert len(doc.raw_text) > 100
    assert doc.file_type == "text"
    assert doc.ocr_used is False
    assert doc.confidence == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
