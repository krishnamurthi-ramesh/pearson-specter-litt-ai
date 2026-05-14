"""
cli.py
======
Pearson Specter Litt — Terminal Administration Utility

Allows instant interaction with the underlying RAG, vector indexes, 
and continuous learning telemetry directly from your console.
"""

import os
import sys
import argparse

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.vector_store import VectorStore
from src.feedback.pattern_extractor import get_learned_patterns
from src.document_processor.structured_extractor import extract_structured_data
from src.document_processor.ingestion import ingest_document
from src.document_processor.preprocessor import clean_text

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax
    console = Console()
except ImportError:
    print("Error: 'rich' dependency is not installed. Run 'pip install rich' to use the CLI.")
    sys.exit(1)

def search_command(query: str, doc_filter: str = None, limit: int = 5):
    console.print(f"\n[SEARCH] [bold blue]Executing RAG Semantic Search[/bold blue] for: '[italic]{query}[/italic]'...")
    vs = VectorStore()
    
    try:
        results = vs.query(query, n_results=limit, doc_id_filter=doc_filter)
        
        if not results:
            console.print("[yellow]No matching vector chunks found. Run 'python bootstrap_demo.py' to seed data.[/yellow]")
            return
            
        table = Table(title=f"Semantic Search Hits (Limit: {limit})", show_header=True, header_style="bold cyan")
        table.add_column("Rank", justify="right", style="dim", width=5)
        table.add_column("Source Doc", style="magenta", width=20)
        table.add_column("Page", justify="center", style="yellow", width=6)
        table.add_column("Similarity", justify="right", style="green", width=10)
        table.add_column("Matched Evidence Excerpt", style="white")
        
        for idx, res in enumerate(results, 1):
            excerpt = res["text"][:140].replace("\n", " ") + "..."
            table.add_row(
                str(idx),
                res["doc_id"],
                str(res["page"]),
                f"{res['similarity']:.4f}",
                excerpt
            )
            
        console.print(table)
        console.print("\n")
    except Exception as e:
        console.print(f"[bold red]Error executing vector query:[/bold red] {e}")

def view_patterns():
    console.print("\n[TELEMETRY] [bold yellow]Extracted System Prompt Rules[/bold yellow]...")
    try:
        patterns = get_learned_patterns()
        
        if not patterns:
            console.print("[yellow]No learned prompt directives exist yet. Run bootstrap_demo.py to pre-load simulated data.[/yellow]\n")
            return
            
        table = Table(title="Active Continuously Learned Heuristics", header_style="bold gold3")
        table.add_column("Type", style="bold magenta")
        table.add_column("Extracted Rule Definition", style="white")
        table.add_column("Occurrences", justify="right", style="green")
        table.add_column("Target Transformation", style="cyan")
        
        for p in patterns:
            transform = ""
            if p.get("example_before") or p.get("example_after"):
                transform = f"'{p.get('example_before')}' -> '{p.get('example_after')}'"
            table.add_row(
                p["pattern_type"].upper(),
                p["description"],
                f"{p['frequency']}x",
                transform
            )
            
        console.print(table)
        console.print("\n")
    except Exception as e:
        console.print(f"[bold red]Database connection error:[/bold red] {e}")

def extract_doc_entities(doc_path: str):
    if not os.path.exists(doc_path):
        console.print(f"[bold red]Error:[/bold red] File not found at '{doc_path}'")
        return
        
    console.print(f"\n[ANALYSIS] [bold green]Executing NLP Analysis[/bold green] on target: [cyan]{os.path.basename(doc_path)}[/cyan]...")
    
    try:
        doc = ingest_document(doc_path)
        cleaned = clean_text(doc.raw_text)
        data = extract_structured_data(cleaned)
        
        # Print Meta
        p = Panel.fit(
            f"• [bold]Classification:[/bold] {data['document_type'].upper()}\n"
            f"• [bold]Confidence Indicator:[/bold] {doc.confidence * 100}%\n"
            f"• [bold]Character Length:[/bold] {len(cleaned)}",
            title="Ingestion Metrics",
            border_style="green"
        )
        console.print(p)
        
        # Print Structured Entities
        table = Table(title="Extracted Deterministic Entities")
        table.add_column("Entity Type", style="bold cyan")
        table.add_column("Extracted Values Found", style="white")
        
        for field in ["dates", "case_numbers", "amounts", "parties"]:
            vals = ", ".join(data.get(field, [])) or "[dim]None Detected[/dim]"
            table.add_row(field.replace("_", " ").title(), vals)
            
        console.print(table)
        console.print("\n")
        
    except Exception as e:
        console.print(f"[bold red]Analysis Failure:[/bold red] {e}")

def main():
    parser = argparse.ArgumentParser(description="Pearson Specter Litt System Terminal Controller")
    subparsers = parser.add_subparsers(dest="cmd", required=True, help="Commands")
    
    # Sub: Search
    search_p = subparsers.add_parser("search", help="Semantic search queries")
    search_p.add_argument("query", type=str, help="Natural language search string")
    search_p.add_argument("--doc", type=str, default=None, help="Filter by document name")
    search_p.add_argument("--limit", type=int, default=5, help="Max results limit")
    
    # Sub: Patterns
    subparsers.add_parser("patterns", help="View current dynamic learning rules")
    
    # Sub: Extract
    extract_p = subparsers.add_parser("analyze", help="Run standalone extraction on a file")
    extract_p.add_argument("file", type=str, help="Path to file")
    
    args = parser.parse_args()
    
    if args.cmd == "search":
        search_command(args.query, args.doc, args.limit)
    elif args.cmd == "patterns":
        view_patterns()
    elif args.cmd == "analyze":
        extract_doc_entities(args.file)

if __name__ == "__main__":
    main()
