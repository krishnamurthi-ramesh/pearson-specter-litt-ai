# Pearson Specter Litt — Document Intelligence System

An AI-powered pipeline that ingests messy legal documents, extracts structured data, retrieves grounded evidence, generates draft legal outputs, and **learns from operator edits to improve over time**.

Built with **FastAPI** + **Ollama (Mistral 7B)** + **ChromaDB** + **Sentence-Transformers**.

---

## 🏗️ Architecture at a Glance

```
Documents (PDF/Image/Text)
        │
        ▼
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  1. Document     │────▶│  2. Retrieval    │────▶│  3. Draft      │
│     Processing   │     │     & Grounding  │     │     Generation │
│  (OCR, Extract)  │     │  (ChromaDB, RAG) │     │  (Ollama LLM)  │
└─────────────────┘     └──────────────────┘     └───────┬────────┘
                                                          │
                                                          ▼
                                                 ┌────────────────┐
                                                 │  4. Operator   │
                                                 │     Edits →    │
                                                 │     Learning   │
                                                 │  (SQLite loop) │
                                                 └────────────────┘
```

## ⚡ Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed with `mistral:7b` model pulled
- (Optional) Tesseract OCR for scanned PDFs/images

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/krishnamurthi1703/pearson-specter-litt-ai.git
cd pearson-specter-litt-ai

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download spaCy model (optional, for NER)
# python -m spacy download en_core_web_sm

# 5. Ensure Ollama is running with Mistral
ollama pull mistral:7b
ollama serve                 # if not already running

# 6. Copy environment config
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux

# 7. Run the application
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser.

### Running Tests

```bash
pytest tests/ -v
```

---

## 📦 Project Structure

```
├── main.py                          # FastAPI entry point
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment config template
│
├── src/
│   ├── document_processor/
│   │   ├── ingestion.py             # OCR + text extraction
│   │   ├── structured_extractor.py  # Entity extraction (dates, parties, case #)
│   │   └── preprocessor.py          # Text cleaning & section detection
│   │
│   ├── retrieval/
│   │   ├── chunker.py               # Smart text chunking with overlap
│   │   ├── embedder.py              # Sentence-transformer embeddings
│   │   └── vector_store.py          # ChromaDB vector store
│   │
│   ├── generation/
│   │   ├── drafter.py               # Ollama LLM draft generation
│   │   ├── prompts.py               # Grounded prompt templates
│   │   └── grounding.py             # Post-generation grounding verification
│   │
│   ├── feedback/
│   │   ├── edit_tracker.py          # SQLite edit storage & diffing
│   │   ├── pattern_extractor.py     # Learn patterns from edits
│   │   └── improver.py              # Apply patterns to future drafts
│   │
│   └── api/
│       └── routes.py                # REST API endpoints
│
├── ui/                              # Web UI
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── sample_documents/                # Synthetic legal documents
├── sample_outputs/                  # Pre-generated pipeline outputs
└── tests/                           # Unit tests
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/documents/upload` | Upload & process a document |
| `GET` | `/api/documents` | List all indexed documents |
| `GET` | `/api/documents/{id}` | Get processed document details |
| `GET` | `/api/retrieve?query=...&n=5` | Semantic search |
| `POST` | `/api/drafts/generate` | Generate a grounded draft |
| `POST` | `/api/drafts/edit` | Submit operator edits |
| `GET` | `/api/feedback/patterns` | View learned patterns |
| `GET` | `/api/feedback/edits` | List edit history |

### Example: Generate a Draft

```bash
curl -X POST http://localhost:8000/api/drafts/generate \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "contract_draft", "draft_type": "case_summary"}'
```

---

## 🧪 Evaluation Approach

### Document Processing
- Tested with 3 synthetic legal documents of varying formats
- Extraction quality verified by comparing structured output against known entities
- OCR fallback tested with image-based inputs

### Retrieval Quality
- Semantic search tested with targeted queries
- Verified that the most relevant chunks rank highest
- Evidence traceability confirmed (each chunk carries source doc, page, section)

### Draft Quality
- Grounding verification: automated check that sentences map to evidence
- Citation coverage: drafts include `[Source: doc_id, p.X]` references
- Anti-hallucination: system prompt enforces evidence-only generation

### Improvement Loop
- Simulated operator edits to verify pattern extraction
- Confirmed that learned patterns (tone, terminology, structure) are injected into future prompts
- Tracked edit distance over time to measure improvement

---

## 📖 Key Design Decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture overview and [WRITEUP.md](WRITEUP.md) for assumptions and tradeoffs.
