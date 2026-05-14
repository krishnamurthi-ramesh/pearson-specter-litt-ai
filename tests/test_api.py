"""
test_api.py
===========
Enterprise-grade API integration testing suite.
Verifies FastAPI router lifecycle, model validation, and endpoint resilience.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)

def test_api_health():
    """Ensure root router health and lifecycle logic executes successfully."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "vector_store_count" in data


def test_api_list_documents():
    """Ensure endpoint lists all tracked documents without execution failure."""
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "count" in data
    assert isinstance(data["documents"], list)


def test_api_retrieve_validation_error():
    """Ensure query validation intercepts missing arguments cleanly."""
    # 'query' param is required — should return 422 Unprocessable Entity
    response = client.get("/api/retrieve")
    assert response.status_code == 422


def test_api_retrieve_success():
    """Ensure retrieval API handles parameters successfully."""
    response = client.get("/api/retrieve?query=agreement&n=2")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert data["query"] == "agreement"


def test_api_diff_computation():
    """Verify that structural text diffs compute successfully over network API."""
    payload = {
        "original": "We agree to provide consulting services.",
        "edited": "We agree to provide specialized consulting services.\nCONFIDENTIAL."
    }
    response = client.post("/api/drafts/diff", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "additions" in data
    assert "edit_distance" in data
    assert "change_ratio" in data
    assert len(data["additions"]) >= 1


def test_api_get_patterns():
    """Verify learning pattern endpoint returns telemetry datasets successfully."""
    response = client.get("/api/feedback/patterns")
    assert response.status_code == 200
    data = response.json()
    assert "patterns" in data
    assert "metrics" in data
    assert isinstance(data["patterns"], list)
    assert "total_edits" in data["metrics"]


def test_api_list_edits():
    """Verify list endpoint returns logged corrective sessions."""
    response = client.get("/api/feedback/edits?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "edits" in data
    assert "count" in data
    assert isinstance(data["edits"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
