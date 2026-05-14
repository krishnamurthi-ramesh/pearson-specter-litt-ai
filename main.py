"""
main.py
=======
FastAPI application entry point for the Pearson Specter Litt
Document Intelligence System.

Run with:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import os
import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.logger import get_logger
from src.exceptions import (
    PSLError,
    IngestionError,
    VectorStorageError,
    DocumentNotFoundError,
    InferenceError
)

# ── Logging ─────────────────────────────────────────────────────────────
logger = get_logger("server.main")

# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pearson Specter Litt — Document Intelligence",
    description=(
        "AI-powered document processing, grounded retrieval, draft generation, "
        "and improvement-from-edits system for legal workflows."
    ),
    version="1.0.0",
)

# CORS (allow the UI to call the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api")


# ── Global Enterprise Exception Handlers ─────────────────────────────────

@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
    logger.warning(f"Document not found error intercepted: {exc.message}")
    return JSONResponse(
        status_code=404,
        content={"error": "ResourceNotFound", "message": exc.message, "details": exc.details}
    )


@app.exception_handler(IngestionError)
async def ingestion_error_handler(request: Request, exc: IngestionError):
    logger.error(f"Ingestion processing failure: {exc.message}")
    return JSONResponse(
        status_code=400,
        content={"error": "IngestionFailure", "message": exc.message, "details": exc.details}
    )


@app.exception_handler(InferenceError)
async def inference_error_handler(request: Request, exc: InferenceError):
    logger.critical(f"Inference runtime server unavailable: {exc.message}")
    return JSONResponse(
        status_code=503,
        content={"error": "InferenceUnavailable", "message": "The local LLM server (Ollama) is offline or unreachable.", "details": str(exc.details)}
    )


@app.exception_handler(PSLError)
async def psl_base_error_handler(request: Request, exc: PSLError):
    logger.error(f"Unhandled internal platform domain exception: {exc.message}")
    return JSONResponse(
        status_code=500,
        content={"error": "InternalPlatformError", "message": exc.message, "details": str(exc.details)}
    )


# Serve static UI files
ui_dir = os.path.join(os.path.dirname(__file__), "ui")
if os.path.isdir(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/")
    def serve_ui():
        return FileResponse(os.path.join(ui_dir, "index.html"))


# ── Startup ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    # Ensure data directories exist
    for d in ["./data/chroma_db", "./data/uploads"]:
        os.makedirs(d, exist_ok=True)
    logger.info("Pearson Specter Litt - Document Intelligence Engine Initialized Successfully")

