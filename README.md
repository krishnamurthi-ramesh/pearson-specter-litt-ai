<div align="center">

# ⚖️ Pearson Specter Litt — Document Intelligence System

**An AI-powered pipeline that ingests messy legal documents, extracts structured data, retrieves grounded evidence, generates cited draft outputs, and learns from operator edits to continuously improve.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/Vector_DB-ChromaDB-orange)](https://www.trychroma.com)
[![Ollama](https://img.shields.io/badge/LLM-Ollama_Mistral_7B-purple)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](Dockerfile)
[![Tests](https://img.shields.io/badge/Tests-40_Passing-brightgreen?logo=pytest)](#testing)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-black?logo=githubactions)](.github/workflows/ci.yml)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Quick Start (Local)](#quick-start-local)
- [Quick Start (Docker)](#quick-start-docker)
- [Environment Configuration](#environment-configuration)
- [API Reference](#api-reference)
- [Demo Bootstrap](#demo-bootstrap)
- [CLI Tool](#cli-tool)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Sample Inputs & Outputs](#sample-inputs--outputs)
- [Evaluation Approach](#evaluation-approach)

---

## Overview

The **Pearson Specter Litt Document Intelligence System** is a production-grade AI pipeline built for legal document workflows. It addresses four core requirements:

| Stage | What it does |
|---|---|
| **1. Document Processing** | Ingests PDFs, scanned images, and text files. Uses PyMuPDF for native extraction with Tesseract OCR fallback for scanned/image documents. Outputs cleaned text, structured fields (parties, dates, amounts, case numbers), and a quality score. |
| **2. Grounded Retrieval** | Chunks processed text, embeds with `all-MiniLM-L6-v2`, and indexes in ChromaDB. Every retrieved chunk carries full provenance (doc ID, page, section) so evidence is fully inspectable. |
| **3. Draft Generation** | Assembles a grounded prompt from ranked evidence + structured data + learned operator preferences and calls a local Ollama LLM. A post-generation grounding verifier checks each sentence against source evidence, flagging unsupported claims. An agentic self-correction loop re-prompts the LLM to fix any ungrounded sentences. |
| **4. Improvement from Edits** | Operator edits are stored in SQLite. A statistical pattern extractor identifies recurring changes (terminology, tone, additions, structure) and injects them as natural-language instructions into future prompts. |

---

## System Architecture

<img width="1432" height="827" alt="image" src="https://github.com/user-attachments/assets/41c7742a-4330-453b-ad58-08cab246d1a7" />


**Technology Stack:**

| Component | Technology | Reason |
|---|---|---|
| API Framework | FastAPI | Auto-docs, async, type validation |
| LLM | Ollama (Mistral 7B) | Local execution — data never leaves the machine |
| Embeddings | all-MiniLM-L6-v2 | Fast, accurate, no API key required |
| Vector DB | ChromaDB | Zero-config, persistent, metadata filtering |
| Text Extraction | PyMuPDF | Fast native PDF parsing |
| OCR | Tesseract | Scanned PDF and image support |
| Feedback Store | SQLite | Lightweight, zero-dependency persistence |
| Frontend | Vanilla HTML/CSS/JS | No build step, works out of the box |

---

## Prerequisites

### Local Setup
- **Python 3.10+**
- **[Ollama](https://ollama.com/)** installed and running with `mistral:7b` pulled
- **Tesseract OCR** *(optional — only needed for scanned PDFs / images)*
  - Windows: [Download installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - Linux/Mac: `sudo apt install tesseract-ocr` / `brew install tesseract`

### Docker Setup
- **Docker** + **Docker Compose** (v2)
- **Ollama** running on the host machine with `mistral:7b` pulled

---

## Quick Start (Local)

```bash
# 1. Clone the repository
git clone https://github.com/krishnamurthi-ramesh/pearson-specter-litt-ai.git
cd pearson-specter-litt-ai

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux

# Edit .env if needed (e.g. set TESSERACT_CMD on Windows)

# 5. Pull and start the Ollama LLM (in a separate terminal)
ollama pull mistral:7b
ollama serve

# 6. Seed the demo database (optional — recommended for first run)
python bootstrap_demo.py

# 7. Start the application
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser — the UI loads automatically.

Interactive API docs are available at **http://localhost:8000/docs**.

---

## Quick Start (Docker)

> **Prerequisite:** Ollama must be running on your **host machine** with `mistral:7b` pulled. The Docker container connects to it via `host.docker.internal`.

```bash
# 1. Clone the repository
git clone https://github.com/krishnamurthi-ramesh/pearson-specter-litt-ai.git
cd pearson-specter-litt-ai

# 2. Build and start
docker compose up --build

# The app will be available at http://localhost:8000
# Data is persisted in a named Docker volume (app-data)
```

To stop:
```bash
docker compose down
```

To stop and remove all data:
```bash
docker compose down -v
```

> **Note:** Tesseract OCR is automatically installed inside the Docker container — no manual setup needed. The `TESSERACT_CMD` environment variable is pre-set to the Linux container path.

---

## Environment Configuration

Copy `.env.example` to `.env` and adjust as needed:

```env
# Ollama LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:7b

# Embedding model (downloaded automatically on first run)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Storage paths
CHROMA_DB_PATH=./data/chroma_db
FEEDBACK_DB_PATH=./data/feedback.db
UPLOAD_DIR=./data/uploads

# Tesseract OCR — Windows path example:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
# Linux / Mac — usually not needed if tesseract is on PATH
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check — returns status and vector store chunk count |
| `POST` | `/api/documents/upload` | Upload & process a document (PDF, image, or text) |
| `GET` | `/api/documents` | List all indexed document IDs |
| `GET` | `/api/documents/{id}` | Get structured data for a processed document |
| `GET` | `/api/retrieve?query=...&n=5` | Semantic search — returns ranked evidence chunks with provenance |
| `POST` | `/api/drafts/generate` | Generate a grounded draft from a processed document |
| `POST` | `/api/drafts/edit` | Submit an operator edit — triggers pattern learning |
| `POST` | `/api/drafts/diff` | Compute a structured diff between two texts |
| `GET` | `/api/feedback/patterns` | View all learned operator preferences |
| `GET` | `/api/feedback/edits` | List edit history |
| `POST` | `/api/huggingface/import` | Import a real legal document from HuggingFace (BillSum dataset) |

### Example: Upload a Document
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample_documents/contract_draft.txt"
```

### Example: Generate a Draft
```bash
curl -X POST http://localhost:8000/api/drafts/generate \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "contract_draft", "draft_type": "case_summary"}'
```

### Example: Submit an Operator Edit
```bash
curl -X POST http://localhost:8000/api/drafts/edit \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "contract_draft",
    "draft_type": "case_summary",
    "original_text": "The claimant filed a motion.",
    "edited_text": "The plaintiff filed a motion.\n\nPRIVILEGED ATTORNEY WORK PRODUCT."
  }'
```

Draft types supported: `case_summary` · `internal_memo` · `document_checklist`

---

## Demo Bootstrap

To instantly prime the system with sample documents and simulated operator edit history (so the improvement loop is pre-warmed on first run):

```bash
python bootstrap_demo.py
```

This will:
1. Index all documents in `sample_documents/` into ChromaDB
2. Inject 3 synthetic operator edit sessions into SQLite
3. Extract initial learned patterns and display them in a table

---

## CLI Tool

A terminal administration utility for interacting with the system without the web UI:

```bash
# Semantic search over indexed documents
python cli.py search "purchase price and closing date"

# Filter by document
python cli.py search "breach of contract" --doc contract_draft --limit 3

# View all learned operator patterns
python cli.py patterns

# Run NLP entity extraction on a file
python cli.py analyze sample_documents/contract_draft.txt
```

---

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Run specific test files
pytest tests/test_processor.py -v    # Document processing
pytest tests/test_feedback.py -v     # Edit tracking & pattern learning
pytest tests/test_retrieval.py -v    # Chunking, embedding, vector store
pytest tests/test_api.py -v          # API endpoint integration tests
```

**Current results:** `40 passed, 0 failed`

| Test File | Tests | Coverage |
|---|---|---|
| `test_processor.py` | 17 | File detection, OCR routing, text cleaning, section detection, quality scoring, structured extraction, end-to-end ingestion |
| `test_feedback.py` | 9 | Diff computation, edit storage, pattern extraction, improvement metrics, feedback instruction building |
| `test_retrieval.py` | 7 | Chunking, embedding, vector store add/query |
| `test_api.py` | 7 | Health, document listing, retrieval validation, diff endpoint, patterns, edit history |

---

## Project Structure

```
pearson-specter-litt-ai/
│
├── main.py                          # FastAPI app entry point (lifespan, routes, exception handlers)
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template
├── Dockerfile                       # Container definition (includes Tesseract & Poppler)
├── docker-compose.yml               # Single-command Docker deployment
├── bootstrap_demo.py                # Demo seeding script
├── cli.py                           # Terminal administration utility
│
├── src/
│   ├── config.py                    # Pydantic-based typed configuration (AppSettings)
│   ├── exceptions.py                # Custom domain exception hierarchy
│   ├── logger.py                    # Structured logging setup
│   │
│   ├── document_processor/
│   │   ├── ingestion.py             # File-type routing, OCR fallback, ProcessedDocument output
│   │   ├── preprocessor.py          # Text cleaning, hyphenation fix, section detection
│   │   └── structured_extractor.py  # Regex extraction: dates, parties, amounts, case numbers
│   │
│   ├── retrieval/
│   │   ├── chunker.py               # Paragraph-aware chunking with overlap and metadata
│   │   ├── embedder.py              # Sentence-transformer embedding wrapper
│   │   └── vector_store.py          # ChromaDB interface: add, query, filter, count
│   │
│   ├── generation/
│   │   ├── drafter.py               # Ollama LLM client + template fallback
│   │   ├── prompts.py               # Grounded prompt templates for each draft type
│   │   ├── grounding.py             # Post-generation sentence-level grounding verification
│   │   └── agent_refiner.py         # Agentic self-correction loop for ungrounded statements
│   │
│   ├── feedback/
│   │   ├── edit_tracker.py          # SQLite edit storage, structured diff computation
│   │   ├── pattern_extractor.py     # Statistical pattern mining from edit history
│   │   └── improver.py              # Build feedback instructions + improvement metrics
│   │
│   └── api/
│       └── routes.py                # All REST API endpoint definitions
│
├── ui/
│   ├── index.html                   # Single-page web UI
│   ├── style.css                    # UI styling
│   └── app.js                       # UI logic and API integration
│
├── sample_documents/                # Synthetic legal inputs for demo
│   ├── contract_draft.txt           # Purchase & sale agreement
│   ├── court_filing.txt             # Civil court complaint
│   ├── settlement_memo.txt          # Settlement negotiation memo
│   └── test_settlement_agreement.png # Scanned image (tests OCR path)
│
├── sample_outputs/                  # Pre-generated pipeline outputs (no setup required to view)
│   ├── extracted_data.json          # Structured extraction output
│   ├── draft_case_summary.json      # Full generated draft with citations & grounding report
│   ├── retrieval_results.json       # Semantic search results with provenance
│   └── learned_patterns.json        # Operator feedback patterns after edit cycles
│
├── tests/
│   ├── test_processor.py
│   ├── test_feedback.py
│   ├── test_retrieval.py
│   └── test_api.py
│
└── .github/
    └── workflows/
        └── ci.yml                   # GitHub Actions CI: install deps, run all tests
```

---

## Sample Inputs & Outputs

### Sample Documents (`sample_documents/`)
Three synthetic legal documents covering the main legal document types encountered in practice:

| File | Type | Contents |
|---|---|---|
| `contract_draft.txt` | Contract | Purchase & Sale Agreement — $3.5M real estate transaction, two parties, closing conditions |
| `court_filing.txt` | Court Filing | Civil complaint with prayer for relief, case number, parties |
| `settlement_memo.txt` | Memo | Internal settlement negotiation memo with amounts and terms |
| `test_settlement_agreement.png` | Scanned Image | Image document to exercise the OCR path |

### Sample Outputs (`sample_outputs/`)
Pre-generated outputs from running the full pipeline on `contract_draft.txt` — reviewable without running the system:

| File | Contents |
|---|---|
| `extracted_data.json` | Structured fields: dates, parties, amounts, case numbers, document type, sections |
| `draft_case_summary.json` | Full generated case summary with `[Source: doc_id, p.N]` citations, grounding score per sentence, evidence used |
| `retrieval_results.json` | Top-5 semantic search results for a sample query, each with doc ID, page, section, and similarity score |
| `learned_patterns.json` | Two patterns extracted after 3 operator edit cycles: terminology (`claimant→plaintiff`) and addition (privilege disclaimer) |

---

## Key Design Decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture overview and [WRITEUP.md](WRITEUP.md) for assumptions and tradeoffs.

---

<div align="center">
Built for the <strong>Pearson Specter Litt AI Engineer Take-Home Assessment</strong><br>
<em>Krishnamurthi Ramesh · kiccha1703@gmail.com · May 2026</em>
</div>
