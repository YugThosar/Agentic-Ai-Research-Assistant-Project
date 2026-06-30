"""
Integration tests for the APKS API.
Uses httpx.TestClient to test without spinning up a real server.
Run with: pytest tests/ -v
"""
import json
import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


class TestDocuments:
    def test_list_documents_empty(self, client):
        r = client.get("/api/documents")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upload_txt(self, client):
        content = b"This is a test document about neural networks and transformers."
        file = io.BytesIO(content)
        r = client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", file, "text/plain")},
            data={"chunking_strategy": "fixed"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["filename"] == "test.txt"
        assert data["status"] in ("queued", "processing", "completed")
        return data["id"]

    def test_upload_unsupported_type(self, client):
        file = io.BytesIO(b"<html></html>")
        r = client.post(
            "/api/documents/upload",
            files={"file": ("index.html", file, "text/html")},
        )
        assert r.status_code == 400

    def test_get_document_not_found(self, client):
        r = client.get("/api/documents/nonexistent-id")
        assert r.status_code == 404

    def test_delete_document_not_found(self, client):
        r = client.delete("/api/documents/nonexistent-id")
        assert r.status_code == 404


class TestConversations:
    def test_list_conversations_empty(self, client):
        r = client.get("/api/conversations")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_conversation_not_found(self, client):
        r = client.get("/api/conversations/fake-id")
        assert r.status_code == 404


class TestMemory:
    def test_list_memory(self, client):
        r = client.get("/api/memory")
        assert r.status_code == 200

    def test_create_and_read_memory(self, client):
        payload = {"category": "semantic", "key": "test_topic", "value": "neural_networks"}
        r = client.post("/api/memory/update", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["key"] == "test_topic"

        r2 = client.get("/api/memory?category=semantic")
        assert any(m["key"] == "test_topic" for m in r2.json())

    def test_delete_memory(self, client):
        payload = {"category": "working", "key": "temp_key", "value": "temp_val"}
        r = client.post("/api/memory/update", json=payload)
        mem_id = r.json()["id"]

        r2 = client.delete(f"/api/memory/{mem_id}")
        assert r2.status_code == 200


class TestGraph:
    def test_get_graph(self, client):
        r = client.get("/api/graph")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "edges" in data

    def test_search_graph(self, client):
        r = client.get("/api/graph/search?query=test")
        assert r.status_code == 200
        assert "results" in r.json()


class TestEvaluation:
    def test_get_report(self, client):
        r = client.get("/api/evaluation/reports")
        assert r.status_code == 200
        data = r.json()
        assert "total_evaluations" in data

    def test_submit_feedback_invalid(self, client):
        r = client.post("/api/evaluation/feedback", json={"message_id": "fake-id", "feedback": "thumbs_up"})
        assert r.status_code == 404


class TestDashboard:
    def test_get_stats(self, client):
        r = client.get("/api/dashboard/stats")
        assert r.status_code == 200
        data = r.json()
        assert "documents" in data
        assert "chunks" in data
        assert "conversations" in data
        assert "knowledge_graph" in data


class TestIngestionComponents:
    """Unit tests for chunking and embedding utilities."""

    def test_fixed_chunker(self):
        from backend.ingestion.chunker import Chunker
        text = "A" * 1200
        chunks = Chunker.fixed_chunk(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 550

    def test_recursive_chunker(self):
        from backend.ingestion.chunker import Chunker
        text = "Sentence one.\n\nSentence two.\n\nSentence three.\n\nSentence four."
        chunks = Chunker.recursive_chunk(text, chunk_size=40, overlap=5)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_embedder_returns_vector(self):
        from backend.ingestion.embedder import Embedder
        vec = Embedder.get_embedding("hello world")
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert isinstance(vec[0], float)

    def test_embedder_deterministic_fallback(self):
        from backend.ingestion.embedder import Embedder
        v1 = Embedder._fallback_embed("test sentence")
        v2 = Embedder._fallback_embed("test sentence")
        assert v1 == v2
