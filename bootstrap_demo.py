"""
bootstrap_demo.py
=================
The Master Deployment Bootstrapper.

This script instantly primes the environment by performing the following:
1. Scans and automatically ingests all sample legal documents into ChromaDB.
2. Injects synthetic historical operator edits into the SQLite database to pre-warm 
   the Feedback Improvement Loop.
3. Evaluates and extracts active styling patterns so the system is immediately 
   functional and "pre-trained" with historical domain knowledge.
"""

import os
import sys
import time
import json

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.document_processor.ingestion import ingest_document
from src.document_processor.preprocessor import clean_text
from src.retrieval.chunker import chunk_text
from src.retrieval.vector_store import VectorStore
from src.feedback.edit_tracker import save_edit
from src.feedback.pattern_extractor import extract_patterns, get_learned_patterns

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import track
    console = Console()
except ImportError:
    class MockConsole:
        def print(self, *args, **kwargs): print(*args)
        def rule(self, text): print(f"=== {text} ===")
    console = MockConsole() # type: ignore

# Paths
DOCS_DIR = "sample_documents"
DB_DIR = "data"

def setup_folders():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs("data/uploads", exist_ok=True)

def seed_vector_db():
    console.rule("[bold blue]Stage 1: Pre-Warming Vector Database[/bold blue]")
    
    vs = VectorStore()
    existing_docs = vs.list_documents()
    
    sample_files = [
        f for f in os.listdir(DOCS_DIR) 
        if os.path.isfile(os.path.join(DOCS_DIR, f)) and f.endswith('.txt')
    ]
    
    console.print(f"Found {len(sample_files)} sample documents to process.")
    
    for fname in sample_files:
        fpath = os.path.join(DOCS_DIR, fname)
        doc_id = os.path.splitext(fname)[0]
        
        if doc_id in existing_docs:
            console.print(f"[yellow]** Document '{doc_id}' is already indexed. Skipping.[/yellow]")
            continue
            
        console.print(f"Processing: [cyan]{fname}[/cyan]...")
        
        # Ingest
        doc = ingest_document(fpath)
        cleaned = clean_text(doc.raw_text)
        chunks = chunk_text(cleaned, doc_id=doc.doc_id)
        
        # Embed & Write
        count = vs.add_chunks(chunks)
        console.print(f" -> Indexed [green]{count}[/green] chunks for [bold]{doc.doc_id}[/bold].")
        
    console.print(f"[bold green]Vector DB active. Total Chunks: {vs.count()}[/bold green]\n")

def seed_feedback_loop():
    console.rule("[bold magenta]Stage 2: Pre-Warming Operator Feedback Database[/bold magenta]")
    
    synthetic_edits = [
        {
            "doc_id": "historical_ref_101",
            "draft_type": "case_summary",
            "original": "The claimant entered the agreement under terms that were unfavorable.",
            "edited": "The plaintiff entered the agreement under terms that were unfavorable.\n\nPRIVILEGED ATTORNEY WORK PRODUCT."
        },
        {
            "doc_id": "historical_ref_102",
            "draft_type": "case_summary",
            "original": "Review the data concerning the claimant and their representative.",
            "edited": "Review the data concerning the plaintiff and their representative.\n\nPRIVILEGED ATTORNEY WORK PRODUCT."
        },
        {
            "doc_id": "historical_ref_103",
            "draft_type": "case_summary",
            "original": "The claimant demands damages.",
            "edited": "The plaintiff demands damages.\n\nPRIVILEGED ATTORNEY WORK PRODUCT."
        }
    ]
    
    console.print("Injecting historical operator correction cycles to simulate real-world usage...")
    
    for i, edit in enumerate(synthetic_edits):
        edit_id = save_edit(
            doc_id=edit["doc_id"],
            draft_type=edit["draft_type"],
            original_text=edit["original"],
            edited_text=edit["edited"]
        )
        console.print(f"  -> Logged Operator Session #{edit_id} (Simulated)")
        
    console.print("[bold green]Synthesized user interaction state successfully loaded.[/bold green]\n")

def extract_initial_patterns():
    console.rule("[bold yellow]Stage 3: Instantiating Pattern Learner Engine[/bold yellow]")
    
    console.print("Analyzing edit history for recurring patterns...")
    patterns = extract_patterns()
    
    if patterns:
        table = Table(title="Learned Prompt Directive Patterns (Pre-Loaded)")
        table.add_column("Pattern ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Freq", justify="right", style="green")
        
        for i, p in enumerate(patterns, 1):
            table.add_row(str(i), p["pattern_type"].upper(), p["description"], f"{p['frequency']}x")
            
        console.print(table)
    else:
        console.print("[red]No patterns extracted.[/red]")
    
    console.print("\n")

def main():
    banner = """
=======================================================
   PEARSON SPECTER LITT - BOOTSTRAP PRIMING ACTIVE
=======================================================
    """
    console.print(f"[bold green]{banner}[/bold green]")
    
    p = Panel.fit(
        "Pearson Specter Litt System Bootstrapper\n"
        "Authoritative Auto-Priming Strategy Initiated.",
        title="[bold white]BOOTSTRAP START[/bold white]",
        border_style="green"
    )
    console.print(p)
    console.print("\n")
    
    setup_folders()
    
    try:
        seed_vector_db()
        seed_feedback_loop()
        extract_initial_patterns()
        
        success_panel = Panel(
            "[bold green]SUCCESS[/bold green]\n"
            "The entire database, vectors, and learning engine have been fully primed.\n\n"
            "- Run [cyan]python main.py[/cyan] to access the system.\n"
            "- Open [cyan]http://localhost:8000[/cyan] and navigate to [bold]Feedback[/bold]!",
            title="[bold white]DEPLOYMENT READINESS[/bold white]",
            border_style="bold green"
        )
        console.print(success_panel)
        
    except Exception as e:
        console.print(f"\n[bold red]Deployment Error Occurred:[/bold red] {e}")

if __name__ == "__main__":
    main()
