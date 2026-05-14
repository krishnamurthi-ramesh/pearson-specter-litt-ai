"""
prompts.py
==========
Prompt templates for grounded legal draft generation.
Each template enforces citation of source evidence and discourages hallucination.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are a senior legal assistant at Pearson Specter Litt.
Your role is to generate grounded draft outputs from provided source documents.

CRITICAL RULES:
1. ONLY use information from the provided EVIDENCE sections below.
2. For every factual claim, cite the source using [Source: <doc_id>, p.<page>].
3. If the evidence is insufficient, explicitly state "Insufficient evidence" rather than guessing.
4. Use formal legal language appropriate for internal memos and case summaries.
5. Structure your output with clear headings and numbered points.
6. Never fabricate dates, names, case numbers, or monetary amounts."""


CASE_SUMMARY_TEMPLATE = """TASK: Generate a Case Fact Summary based on the provided evidence.

STRUCTURED DATA EXTRACTED:
{structured_data}

RELEVANT EVIDENCE:
{evidence_blocks}

{feedback_instructions}

Generate a comprehensive Case Fact Summary with the following sections:
1. CASE OVERVIEW — Brief summary of the matter
2. PARTIES INVOLVED — All identified parties and their roles
3. KEY FACTS — Chronological list of material facts (with citations)
4. RELEVANT DATES — Timeline of significant dates
5. FINANCIAL DETAILS — Any monetary amounts or financial terms
6. OPEN ISSUES — Anything unclear or requiring further investigation

Remember: Every factual statement MUST cite its source evidence."""


INTERNAL_MEMO_TEMPLATE = """TASK: Generate an Internal Memorandum based on the provided evidence.

STRUCTURED DATA EXTRACTED:
{structured_data}

RELEVANT EVIDENCE:
{evidence_blocks}

{feedback_instructions}

Generate a professional internal memorandum with:
- TO: [Senior Partner]
- FROM: [Legal Assistant]
- DATE: [Current Date]
- RE: [Subject from evidence]

SECTIONS:
1. PURPOSE — Why this memo is being prepared
2. BACKGROUND — Relevant context from source documents (with citations)
3. KEY FINDINGS — Material facts and observations
4. ANALYSIS — Brief analysis of the situation based on evidence
5. RECOMMENDATIONS — Suggested next steps
6. ATTACHMENTS REFERENCED — List of source documents consulted

Remember: Every factual statement MUST cite its source evidence."""


DOCUMENT_CHECKLIST_TEMPLATE = """TASK: Generate a Document Checklist based on the provided evidence.

STRUCTURED DATA EXTRACTED:
{structured_data}

RELEVANT EVIDENCE:
{evidence_blocks}

{feedback_instructions}

Generate a comprehensive document checklist with:
1. DOCUMENTS RECEIVED — List all documents provided with status
2. MISSING INFORMATION — Identify gaps in the documentation
3. ACTION ITEMS — Steps needed to complete the file
4. DEADLINES — Any dates or time-sensitive items
5. VERIFICATION NEEDED — Items requiring confirmation

Remember: Only list items that are supported by the evidence."""


def get_template(draft_type: str) -> str:
    """Return the appropriate prompt template for a given draft type."""
    templates = {
        "case_summary": CASE_SUMMARY_TEMPLATE,
        "internal_memo": INTERNAL_MEMO_TEMPLATE,
        "document_checklist": DOCUMENT_CHECKLIST_TEMPLATE,
    }
    return templates.get(draft_type, CASE_SUMMARY_TEMPLATE)


def format_evidence_blocks(evidence: list[dict]) -> str:
    """Format retrieved evidence chunks into a labelled block for the prompt."""
    if not evidence:
        return "[No evidence retrieved]"

    blocks = []
    for i, e in enumerate(evidence, 1):
        source = f"[Source: {e.get('doc_id', 'unknown')}, p.{e.get('page', '?')}]"
        sim = e.get("similarity", 0)
        blocks.append(
            f"--- Evidence {i} {source} (relevance: {sim:.2f}) ---\n{e['text']}"
        )
    return "\n\n".join(blocks)


def format_structured_data(structured: dict) -> str:
    """Format structured extraction results for inclusion in the prompt."""
    lines = []
    for key, val in structured.items():
        if isinstance(val, list):
            if val:
                lines.append(f"- {key}: {', '.join(str(v) for v in val)}")
        else:
            lines.append(f"- {key}: {val}")
    return "\n".join(lines) if lines else "[No structured data extracted]"
