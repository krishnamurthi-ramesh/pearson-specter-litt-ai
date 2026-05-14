"""
exceptions.py
=============
Enterprise Domain-Specific Exception Hierarchy.

Establishes a standardized error baseline for the Pearson Specter Litt platform,
guaranteeing precise error instrumentation and clean HTTP status mapping.
"""

from typing import Optional, Any


class PSLError(Exception):
    """Root Exception for all platform-level failures."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


# --- Ingestion & Document Errors ---

class IngestionError(PSLError):
    """Raised when parsing, reading, or validating raw documents fails."""
    pass


class UnsupportedFileTypeError(IngestionError):
    """Raised when a file extension or MIME type is not supported."""
    pass


class OCRExecutionError(IngestionError):
    """Raised when the OCR subsystem (Tesseract/Poppler) crashes."""
    pass


# --- Retrieval & Database Errors ---

class VectorStorageError(PSLError):
    """Raised when ChromaDB persistence, query, or write mechanics fail."""
    pass


class DocumentNotFoundError(VectorStorageError):
    """Raised when querying metadata for an unindexed resource."""
    pass


# --- Generation & Inference Errors ---

class InferenceError(PSLError):
    """Raised when the local Ollama server is unreachable or times out."""
    pass


class HallucinationWarning(InferenceError):
    """Raised when generated content falls beneath grounding thresholds."""
    pass


# --- Feedback & Database Errors ---

class DatabaseError(PSLError):
    """Raised when SQLite persistence, migration, or read operations fail."""
    pass
