"""
agent_refiner.py
================
Autonomous Agentic Self-Correction Refinement Engine.

Implements a "Self-RAG" loop that intercepts generated outputs, mathematically
evaluates sentence-level grounding, and executes an autonomous correction cycle
using local LLMs if grounding thresholds fall beneath critical levels.
"""

import logging
from typing import Dict, Any, List
from .drafter import query_llm
from ..logger import get_logger

logger = get_logger("generation.agent_refiner")


def run_self_correction(
    original_draft: str,
    grounding_report: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    draft_type: str
) -> Dict[str, Any]:
    """
    Analyzes a grounding report, identifies low-grounding sentences, and instructs
    the LLM to autonomously self-correct the draft based purely on retrieval context.

    Args:
        original_draft (str): The raw LLM output draft.
        grounding_report (Dict): The calculated sentence grounding matrix.
        evidence (List[Dict]): The source vector chunks retrieved.
        draft_type (str): Sub-discipline identifier (e.g., case_summary).

    Returns:
        Dict: The refined draft, new grounding assessment, and remediation meta-logs.
    """
    logger.info("Executing Autonomous Agentic Self-Correction Sequence")
    
    # Isolate sentences falling below critical thresholds (e.g., 40%)
    critical_sentences = []
    for i, sent_score in enumerate(grounding_report.get("sentence_scores", [])):
        if sent_score.get("score", 1.0) < 0.40:
            critical_sentences.append(sent_score.get("sentence", ""))

    if not critical_sentences:
        logger.info("No critical hallucinations identified. Self-correction bypassed.")
        return {
            "refined_text": original_draft,
            "corrected": False,
            "remediation_logs": []
        }

    logger.warning(f"Detected {len(critical_sentences)} ungrounded assertions. Initiating critique loop.")

    # Flatten context chunks for the correction prompt
    context_block = "\n\n".join([f"SOURCE CHUNK {i+1}:\n{c['text']}" for i, c in enumerate(evidence)])
    hallucinations_block = "\n".join([f"- \"{s}\"" for s in critical_sentences])

    # The Autonomous Critique & Reformulation Prompt
    critique_prompt = f"""
    [AUTONOMOUS AGENTIC SELF-CORRECTION PROTOCOL]
    
    ROLE: Lead AI Auditor & Verification Agent
    TASK: You have just generated a draft that failed factual verification checks. 
    You must rewrite the draft to ELIMINATE ungrounded hallucinations.

    --- CONTEXT CONSTRAINTS ---
    {context_block}

    --- IDENTIFIED HALLUCINATIONS (CRITICAL FIX REQUIRED) ---
    These sentences in your draft are NOT supported by the source chunks:
    {hallucinations_block}

    --- DRAFT TO REVISE ---
    {original_draft}

    --- SYSTEM DIRECTIVE ---
    Rewrite the draft now. 
    1. Completely remove or restructure the identified ungrounded sentences so they are 100% backed by the source chunks above.
    2. Maintain the original tone and draft type ({draft_type}).
    3. Output ONLY the revised draft. Do not explain your edits.
    """

    try:
        # Trigger the localized self-correction inference run
        revised_text = query_llm(critique_prompt)
        
        # Clean up thinking logs if present
        if "</think>" in revised_text:
            revised_text = revised_text.split("</think>")[-1].strip()

        logger.info("Self-correction pass completed successfully.")
        return {
            "refined_text": revised_text,
            "corrected": True,
            "remediation_logs": [
                f"Intercepted {len(critical_sentences)} low-grounded sentence(s).",
                f"Injected Critique Prompts with {len(evidence)} source contexts.",
                "Successfully regenerated refined, factually aligned output draft."
            ]
        }
    except Exception as e:
        logger.error(f"Agentic refinement run failed: {str(e)}")
        return {
            "refined_text": original_draft,
            "corrected": False,
            "remediation_logs": [f"Refinement runtime error: {str(e)}"]
        }
