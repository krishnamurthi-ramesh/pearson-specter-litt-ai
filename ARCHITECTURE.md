# Architecture Overview

## System Design Philosophy

The system is designed around four independent, composable stages that form a pipeline. Each stage can be tested, debugged, and improved independently. Data flows forward through the pipeline, and feedback flows backward from operators to improve generation.

---

## Pipeline Stages

### Stage 1: Document Processing

```
Input: Messy file (PDF, scanned image, text)
       ▼
┌──────────────────────────────────────────┐
│  File Type Detection                     │
│  ├─ PDF → PyMuPDF native extraction     │
│  │        → OCR fallback if sparse text  │
│  ├─ Image → Tesseract OCR + preprocess  │
│  └─ Text → chardet encoding detection   │
├──────────────────────────────────────────┤
│  Text Preprocessing                      │
│  ├─ Remove control characters           │
│  ├─ Fix OCR artefacts & hyphenation     │
│  ├─ Normalise whitespace                │
│  └─ Detect sections (headers)           │
├──────────────────────────────────────────┤
│  Structured Extraction                   │
│  ├─ Dates (regex, multiple formats)     │
│  ├─ Case/Reference numbers              │
│  ├─ Party names (Plaintiff/Defendant)   │
│  ├─ Monetary amounts                    │
│  ├─ Document type classification        │
│  └─ Key phrases                         │
└──────────────────────────────────────────┘
Output: ProcessedDocument(raw_text, pages, structured_data, quality_score)
```

**Key decisions:**
- PyMuPDF first, OCR second — avoids unnecessary OCR overhead on digital PDFs
- Quality scoring provides transparency about extraction reliability
- Structured extraction uses regex (fast, deterministic) rather than LLM (expensive, non-deterministic)

---

### Stage 2: Retrieval & Grounding

```
Input: Cleaned text from Stage 1
       ▼
┌──────────────────────────────────────────┐
│  Smart Chunking                          │
│  ├─ Split by paragraph boundaries       │
│  ├─ Target: ~500 tokens per chunk       │
│  ├─ 100-token overlap for continuity    │
│  └─ Preserve metadata (doc, page, sec)  │
├──────────────────────────────────────────┤
│  Embedding                               │
│  └─ all-MiniLM-L6-v2 (384-dim)         │
│     Fast, runs locally, no API needed    │
├──────────────────────────────────────────┤
│  Vector Store (ChromaDB)                 │
│  ├─ Cosine similarity search            │
│  ├─ Metadata filtering (by doc_id)      │
│  └─ Persistent storage on disk          │
└──────────────────────────────────────────┘
Output: Ranked evidence chunks with similarity scores + provenance
```

**Key decisions:**
- `all-MiniLM-L6-v2` chosen for speed and local execution (no API dependency)
- ChromaDB for simplicity and zero-config persistent storage
- Chunk metadata enables evidence inspection (which source, which page)

---

### Stage 3: Draft Generation

```
Input: Evidence chunks + Structured data + Feedback instructions
       ▼
┌──────────────────────────────────────────┐
│  Prompt Assembly                         │
│  ├─ System prompt (anti-hallucination)  │
│  ├─ Structured data summary             │
│  ├─ Numbered evidence blocks w/ source  │
│  ├─ Learned style preferences           │
│  └─ Draft template (case_summary, etc) │
├──────────────────────────────────────────┤
│  LLM Call (Ollama / Mistral 7B)         │
│  ├─ Temperature: 0.3 (factual)         │
│  ├─ Local execution, no data leaves     │
│  └─ Fallback: template-based output     │
├──────────────────────────────────────────┤
│  Grounding Verification                  │
│  ├─ Extract sentences from draft        │
│  ├─ Embed sentences + evidence chunks   │
│  ├─ Compute similarity matrix           │
│  └─ Flag ungrounded statements          │
└──────────────────────────────────────────┘
Output: Draft text + evidence citations + grounding report
```

**Key decisions:**
- Local Ollama avoids cloud dependency and keeps data private (critical for legal)
- Grounding verification post-processes the draft to flag unsupported claims
- Three draft types: case summary, internal memo, document checklist

---

### Stage 4: Improvement from Operator Edits

```
Input: Original draft + Operator's edited version
       ▼
┌──────────────────────────────────────────┐
│  Edit Tracking (SQLite)                  │
│  ├─ Compute structured diff             │
│  │   ├─ Additions                       │
│  │   ├─ Deletions                       │
│  │   └─ Modifications (replacements)   │
│  ├─ Calculate edit distance / ratio     │
│  └─ Store with timestamp + metadata     │
├──────────────────────────────────────────┤
│  Pattern Extraction                      │
│  ├─ Recurring additions → "always add"  │
│  ├─ Recurring deletions → "always remove"│
│  ├─ Term replacements → terminology     │
│  ├─ Length trends → tone preference     │
│  └─ Added headings → structure pref     │
├──────────────────────────────────────────┤
│  Feedback Injection                      │
│  ├─ Build natural-language style guide  │
│  ├─ Inject into LLM system prompt      │
│  └─ Track improvement over time         │
└──────────────────────────────────────────┘
Output: Updated prompts → better future drafts
```

**Key decisions:**
- Real improvement loop, not just version diffing
- Patterns are categorised (tone, terminology, structure, addition, deletion)
- Feedback is injected as natural-language instructions into the LLM prompt
- Improvement is measurable: edit distance should decrease over time

---

## Data Flow Diagram

```
                    ┌─────────┐
                    │  Upload │
                    └────┬────┘
                         │
              ┌──────────▼──────────┐
              │  Document Processor  │
              │  (OCR + Extract)     │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Chunk + Embed +    │
              │  Index (ChromaDB)   │
              └──────────┬──────────┘
                         │
    Query ──────▶ Semantic Search ◀── Metadata Filter
                         │
              ┌──────────▼──────────┐
              │  Evidence Ranked    │
              │  + Structured Data  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐         ┌──────────────┐
              │  LLM Draft Gen      │◀────────│  Feedback    │
              │  (Ollama Mistral)   │         │  Instructions│
              └──────────┬──────────┘         └──────┬───────┘
                         │                           │
              ┌──────────▼──────────┐         ┌──────┴───────┐
              │  Grounding Check    │         │  Pattern     │
              │  + Citation Verify  │         │  Extractor   │
              └──────────┬──────────┘         └──────┬───────┘
                         │                           │
              ┌──────────▼──────────┐         ┌──────┴───────┐
              │  Operator Review    │────────▶│  Edit        │
              │  & Edit             │         │  Tracker     │
              └─────────────────────┘         └──────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Framework | FastAPI | REST endpoints, auto-docs |
| LLM | Ollama (Mistral 7B) | Local, private draft generation |
| Embeddings | all-MiniLM-L6-v2 | Fast semantic encoding |
| Vector DB | ChromaDB | Persistent semantic search |
| Text Extraction | PyMuPDF | PDF text extraction |
| OCR | Tesseract | Scanned document support |
| Feedback Store | SQLite | Edit history & learned patterns |
| Frontend | Vanilla HTML/CSS/JS | Demo UI |
