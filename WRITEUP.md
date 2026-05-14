# Assumptions, Tradeoffs, and Design Rationale

## Assumptions

### 1. Document Format
- Input documents are legal-style text: contracts, motions, memos, complaints
- Files may be native PDFs, scanned PDFs, images, or plain text
- OCR quality is "good enough" for Tesseract with basic preprocessing (no handwriting recognition needed for demo)

### 2. Operator Workflow
- A human operator reviews generated drafts and edits them
- Edits are submitted back to the system for learning
- The system does not need to learn in real-time during a single session — pattern extraction runs on each edit submission

### 3. Scale
- This is a demo/prototype system, not a production deployment
- Expected document count: dozens to low hundreds
- ChromaDB is sufficient; a production system would use Qdrant, Pinecone, or Weaviate

### 4. Privacy
- Legal documents are sensitive → Ollama runs locally, no data leaves the machine
- No cloud LLM APIs are used

---

## Key Tradeoffs

### 1. Ollama (Local) vs. Cloud LLMs

**Chose:** Ollama with Mistral 7B (local)

**Why:**
- Legal documents are confidential — sending them to OpenAI/Anthropic is a non-starter in many firms
- Mistral 7B provides good generation quality for structured outputs
- Zero cost, no API key management
- Deterministic execution

**Tradeoff:** Lower output quality compared to GPT-4 or Claude. The drafts are functional but not as polished as what a 70B+ model would produce.

### 2. Regex vs. LLM for Structured Extraction

**Chose:** Regex patterns with optional spaCy NER

**Why:**
- Deterministic and fast
- No LLM latency for simple extractions (dates, case numbers, amounts)
- Predictable output format
- Easy to unit test

**Tradeoff:** Less flexible than LLM-based extraction. Novel entity types would require new regex patterns. A production system might use a fine-tuned NER model.

### 3. ChromaDB vs. FAISS vs. Postgres pgvector

**Chose:** ChromaDB

**Why:**
- Zero configuration, persistent, works out of the box
- Metadata filtering built-in
- Good enough for prototype scale
- Simpler API than FAISS

**Tradeoff:** Not as performant as FAISS for large collections (100K+ chunks). Production would use a managed vector DB.

### 4. Sentence-Level Grounding vs. Claim-Level

**Chose:** Sentence-level grounding verification

**Why:**
- Simpler to implement and explain
- Each sentence is checked against all evidence chunks via semantic similarity
- Provides a clear "grounding score" metric

**Tradeoff:** Some sentences (like section headers or transitions) don't need grounding but may get flagged. A more sophisticated approach would parse the draft into claims and verify each individually.

### 5. Pattern Learning: Statistical vs. LLM-Based

**Chose:** Statistical pattern extraction (Counter-based)

**Why:**
- Fast, interpretable, no additional LLM calls
- Patterns are stored as simple rules that can be inspected
- Frequency-based: only patterns seen 2+ times are promoted

**Tradeoff:** Cannot learn complex stylistic preferences that require semantic understanding. A more advanced system would use the LLM to summarise edit patterns in natural language.

---

## What I'd Improve With More Time

1. **Fine-tuned NER model** for legal entity extraction (parties, jurisdiction, statute references)
2. **Multi-document reasoning** — cross-reference facts across multiple uploaded documents
3. **Active learning UI** — let operators explicitly approve/reject patterns
4. **Streaming generation** — SSE/WebSocket for real-time draft output
5. **Document versioning** — track how a document evolves through the drafting process
6. **A/B testing framework** — compare drafts with/without feedback injection to quantify improvement
7. **Production vector DB** (Qdrant or Weaviate) for better scalability
8. **Authentication** — role-based access for operators vs. reviewers vs. admins
