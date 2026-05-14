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
from contextlib import asynccontextmanager

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
    InferenceError,
)

# ── Logging ─────────────────────────────────────────────────────────────
logger = get_logger("server.main")


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    for d in ["./data/chroma_db", "./data/uploads"]:
        os.makedirs(d, exist_ok=True)
    logger.info("Pearson Specter Litt - Document Intelligence Engine Initialized Successfully")
    yield
    # Shutdown (nothing to tear down currently)


# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pearson Specter Litt — Document Intelligence",
    description=(
        "AI-powered document processing, grounded retrieval, draft generation, "
        "and improvement-from-edits system for legal workflows."
    ),
    version="1.0.0",
    lifespan=lifespan,
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


# ── Global Exception Handlers ────────────────────────────────────────────

@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
    logger.warning("Document not found: %s", exc.message)
    return JSONResponse(
        status_code=404,
        content={"error": "ResourceNotFound", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(IngestionError)
async def ingestion_error_handler(request: Request, exc: IngestionError):
    logger.error("Ingestion failure: %s", exc.message)
    return JSONResponse(
        status_code=400,
        content={"error": "IngestionFailure", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(InferenceError)
async def inference_error_handler(request: Request, exc: InferenceError):
    logger.critical("Inference server unavailable: %s", exc.message)
    return JSONResponse(
        status_code=503,
        content={
            "error": "InferenceUnavailable",
            "message": "The local LLM server (Ollama) is offline or unreachable.",
            "details": str(exc.details),
        },
    )


@app.exception_handler(PSLError)
async def psl_base_error_handler(request: Request, exc: PSLError):
    logger.error("Internal platform error: %s", exc.message)
    return JSONResponse(
        status_code=500,
        content={"error": "InternalPlatformError", "message": exc.message, "details": str(exc.details)},
    )


# ── Static UI ────────────────────────────────────────────────────────────
ui_dir = os.path.join(os.path.dirname(__file__), "ui")
if os.path.isdir(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_ui():
        return FileResponse(os.path.join(ui_dir, "index.html"))
