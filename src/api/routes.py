"""
routes.py
=========
FastAPI route definitions for the Document Intelligence System.
"""

from __future__ import annotations

import os
import json
import shutil
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from ..document_processor.ingestion import ingest_document, ProcessedDocument
from ..document_processor.preprocessor import clean_text, detect_sections, compute_quality_score
from ..document_processor.structured_extractor import extract_structured_data
from ..retrieval.chunker import chunk_document_pages, chunk_text
from ..retrieval.vector_store import VectorStore
from ..generation.drafter import generate_draft
from ..generation.grounding import verify_grounding
from ..generation.agent_refiner import run_self_correction
from ..feedback.edit_tracker import save_edit, get_edits, compute_diff
from ..feedback.pattern_extractor import extract_patterns, get_learned_patterns
from ..feedback.improver import build_feedback_instructions, compute_improvement_metrics

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-initialised singletons
_vector_store: VectorStore | None = None
_doc_cache: dict[str, dict] = {}  # in-memory cache of processed docs
_draft_cache: dict[str, dict] = {}  # cache of generated drafts


def _get_vs() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# -----------------------------------------------------------------------
# Request / Response models
# -----------------------------------------------------------------------

class GenerateDraftRequest(BaseModel):
    doc_id: str
    draft_type: str = "case_summary"
    query: str = "Summarise the key facts and findings from this document"

class EditDraftRequest(BaseModel):
    doc_id: str
    draft_type: str = "case_summary"
    original_text: str
    edited_text: str

class DiffRequest(BaseModel):
    original: str
    edited: str


# -----------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "vector_store_count": _get_vs().count(),
    }


# -----------------------------------------------------------------------
# -----------------------------------------------------------------------
# Document Processing & External Corpora Ingestion
# -----------------------------------------------------------------------

@router.post("/huggingface/import")
async def import_hf_dataset(item_index: int = 0):
    """Import a real Congressional Bill from Hugging Face dataset directly into pipeline."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise HTTPException(500, "Hugging Face 'datasets' library not installed on server.")

    try:
        dataset = load_dataset("billsum", split="test")
        if item_index >= len(dataset):
            item_index = 0
        sample = dataset[item_index]
    except Exception as e:
        raise HTTPException(503, f"Failed to stream Hugging Face Hub: {str(e)}")

    title = sample.get("title", f"HF_Bill_{item_index + 1}")
    text = sample.get("text", "")
    doc_id = f"hf_bill_{item_index + 1}"
    
    # Normalise and ingest
    cleaned = clean_text(text)
    structured = extract_structured_data(cleaned)
    sections = detect_sections(cleaned)
    quality = compute_quality_score(cleaned)
    
    # Vector Indexing
    vs = _get_vs()
    chunks = chunk_text(cleaned, doc_id=doc_id)
    vs.add_chunks(chunks)

    result = {
        "doc_id": doc_id,
        "filename": f"hf_bill_{item_index + 1}.txt",
        "file_type": "text",
        "ocr_used": False,
        "confidence": 1.0,
        "quality_score": float(f"{quality:.4f}"),
        "text_length": len(cleaned),
        "num_pages": 1,
        "num_chunks": len(chunks),
        "sections": [{"title": s["title"], "length": len(s["body"])} for s in sections],
        "structured_data": structured,
        "cleaned_text": cleaned[:2000] + ("..." if len(cleaned) > 2000 else ""),
    }
    _doc_cache[doc_id] = {**result, "full_text": cleaned, "structured": structured}

    return result



@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload, ingest, and index a document."""
    upload_dir = os.getenv("UPLOAD_DIR", "./data/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Save uploaded file
    filepath = os.path.join(upload_dir, file.filename)
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # 1. Ingest (OCR / text extraction)
    doc = ingest_document(filepath)

    # 2. Clean text
    cleaned = clean_text(doc.raw_text)

    # 3. Extract structured data
    structured = extract_structured_data(cleaned)

    # 4. Detect sections
    sections = detect_sections(cleaned)

    # 5. Quality score
    quality = compute_quality_score(cleaned)

    # 6. Chunk and index
    vs = _get_vs()
    if doc.pages:
        chunks = chunk_document_pages(doc.pages, doc.doc_id)
    else:
        chunks = chunk_text(cleaned, doc.doc_id)
    vs.add_chunks(chunks)

    # Cache
    result = {
        "doc_id": doc.doc_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "ocr_used": doc.ocr_used,
        "confidence": doc.confidence,
        "quality_score": quality,
        "text_length": len(cleaned),
        "num_pages": len(doc.pages),
        "num_chunks": len(chunks),
        "sections": [{"title": s["title"], "length": len(s["body"])} for s in sections],
        "structured_data": structured,
        "cleaned_text": cleaned[:2000] + ("..." if len(cleaned) > 2000 else ""),
    }
    _doc_cache[doc.doc_id] = {**result, "full_text": cleaned, "structured": structured}

    return result


@router.get("/documents/{doc_id}")
def get_document(doc_id: str):
    """Get details of a processed document."""
    if doc_id in _doc_cache:
        data = {k: v for k, v in _doc_cache[doc_id].items() if k != "full_text"}
        return data
    raise HTTPException(404, f"Document '{doc_id}' not found in cache")


@router.get("/documents")
def list_documents():
    """List all indexed documents."""
    vs = _get_vs()
    doc_ids = vs.list_documents()
    return {"documents": doc_ids, "count": len(doc_ids)}


# -----------------------------------------------------------------------
# Retrieval
# -----------------------------------------------------------------------

@router.get("/retrieve")
def retrieve(query: str, doc_id: Optional[str] = None, n: int = 5):
    """Semantic search over indexed documents."""
    vs = _get_vs()
    results = vs.query(query, n_results=n, doc_id_filter=doc_id)
    return {"query": query, "results": results, "count": len(results)}


# -----------------------------------------------------------------------
# Draft Generation
# -----------------------------------------------------------------------

@router.post("/drafts/generate")
def generate(req: GenerateDraftRequest):
    """Generate a grounded draft from a processed document."""
    vs = _get_vs()

    # Retrieve evidence
    evidence = vs.query(req.query, n_results=8, doc_id_filter=req.doc_id)
    if not evidence:
        raise HTTPException(404, f"No indexed content found for doc_id='{req.doc_id}'")

    # Get structured data from cache or empty
    structured = {}
    if req.doc_id in _doc_cache:
        structured = _doc_cache[req.doc_id].get("structured", {})

    # Build feedback instructions (if any edits exist)
    feedback = build_feedback_instructions(draft_type=req.draft_type, auto_extract=True)

    # Generate
    draft = generate_draft(
        evidence=evidence,
        structured_data=structured,
        draft_type=req.draft_type,
        feedback_instructions=feedback,
    )

    # Verify grounding
    grounding = verify_grounding(draft["draft_text"], evidence)
    
    # --- CRITICAL BEYOND-RAG UPGRADE: Autonomous Agentic Self-Correction Loop ---
    # Evaluates if any statements are ungrounded (< 0.40) and forces a corrective re-drafting sequence
    self_correction_run = run_self_correction(
        original_draft=draft["draft_text"],
        grounding_report=grounding,
        evidence=evidence,
        draft_type=req.draft_type
    )
    
    if self_correction_run.get("corrected"):
        # Re-ground the refined text
        draft["draft_text"] = self_correction_run["refined_text"]
        grounding = verify_grounding(draft["draft_text"], evidence)
        draft["agentic_self_correction_applied"] = True
        draft["agentic_remediation_logs"] = self_correction_run["remediation_logs"]
    else:
        draft["agentic_self_correction_applied"] = False
        draft["agentic_remediation_logs"] = []

    draft["grounding_report"] = grounding

    # Cache
    draft_key = f"{req.doc_id}_{req.draft_type}"
    _draft_cache[draft_key] = draft

    return draft


# -----------------------------------------------------------------------
# Feedback / Edits
# -----------------------------------------------------------------------

@router.post("/drafts/edit")
def submit_edit(req: EditDraftRequest):
    """Submit an operator edit and trigger pattern learning."""
    edit_id = save_edit(
        doc_id=req.doc_id,
        draft_type=req.draft_type,
        original_text=req.original_text,
        edited_text=req.edited_text,
    )

    # Extract patterns from all edits
    patterns = extract_patterns(draft_type=req.draft_type)

    # Compute diff for response
    diff = compute_diff(req.original_text, req.edited_text)

    return {
        "edit_id": edit_id,
        "diff": diff,
        "patterns_extracted": len(patterns),
        "message": "Edit saved. Patterns will be applied to future drafts.",
    }


@router.post("/drafts/diff")
def compute_diff_endpoint(req: DiffRequest):
    """Compute a structured diff between two texts."""
    return compute_diff(req.original, req.edited)


@router.get("/feedback/patterns")
def get_patterns():
    """View all learned patterns from operator edits."""
    patterns = get_learned_patterns()
    metrics = compute_improvement_metrics()
    return {
        "patterns": patterns,
        "metrics": metrics,
    }


@router.get("/feedback/edits")
def list_edits(doc_id: Optional[str] = None, limit: int = 20):
    """List recent operator edits."""
    edits = get_edits(doc_id=doc_id, limit=limit)
    # Don't send full texts in list view
    for e in edits:
        e["original_text"] = e["original_text"][:200] + "..."
        e["edited_text"] = e["edited_text"][:200] + "..."
    return {"edits": edits, "count": len(edits)}
