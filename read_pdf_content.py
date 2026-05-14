import fitz
import sys

def read_pdf():
    filepath = "AI Engineer - Assessment.pdf"
    try:
        doc = fitz.open(filepath)
        print(f"--- PDF CONTENT OF {filepath} ---")
        for i, page in enumerate(doc):
            print(f"\n=== PAGE {i+1} ===")
            print(page.get_text())
        doc.close()
    except Exception as e:
        print(f"Failed to read PDF: {e}", file=sys.stderr)

if __name__ == "__main__":
    read_pdf()
