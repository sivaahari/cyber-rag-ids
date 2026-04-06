"""
test_rag.py
-----------
Unit and integration tests for the RAG service.

Unit tests use a fully mocked RAG service (no Ollama needed).
Integration tests (marked with @pytest.mark.integration) require
a live Ollama instance and are skipped in CI by default.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.models import (
    ChatMessage,
    ChatRequest,
    PredictionLabel,
    PredictionResult,
    SeverityLevel,
)


# ─── Unit Tests (no Ollama required) ─────────────────────────────────────────

class TestRAGServiceUnit:
    """Tests using mocked RAG — fast, no external dependencies."""

    def test_chat_endpoint_with_mock(self, client):
        """POST /chat returns 200 with mocked RAG service."""
        payload = {
            "question": "What is a SYN flood attack?",
            "history":  [],
        }
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer"      in data
        assert "sources"     in data
        assert "model_used"  in data
        assert "response_ms" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_chat_with_history(self, client):
        """Chat with conversation history included."""
        payload = {
            "question": "How do I contain it?",
            "history":  [
                {"role": "user",      "content": "What is port scanning?"},
                {"role": "assistant", "content": "Port scanning is..."},
            ],
        }
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 200

    def test_chat_with_prediction_context(self, client):
        """Chat includes an anomaly PredictionResult as context."""
        prediction = {
            "prediction_id": "test-123",
            "label":         "ATTACK",
            "probability":   0.92,
            "severity":      "CRITICAL",
            "threshold":     0.5,
            "is_anomaly":    True,
            "inference_ms":  1.5,
            "timestamp":     "2024-01-01T00:00:00",
        }
        payload = {
            "question":           "What should I do about this attack?",
            "history":            [],
            "prediction_context": prediction,
        }
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 200

    def test_chat_empty_question_rejected(self, client):
        """Empty question should fail Pydantic validation."""
        payload = {"question": "", "history": []}
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 422

    def test_chat_question_too_long_rejected(self, client):
        """Question over 4000 chars should be rejected."""
        payload = {"question": "x" * 4001, "history": []}
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 422

    def test_rag_stats_endpoint(self, client):
        """GET /rag-stats returns stats dict."""
        resp = client.get("/rag-stats")
        assert resp.status_code == 200

    def test_invalid_chat_role_rejected(self, client):
        """History with invalid role should fail validation."""
        payload = {
            "question": "What is DDoS?",
            "history":  [{"role": "robot", "content": "test"}],
        }
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 422


class TestPromptBuilding:
    """Unit test the RAG service prompt building logic directly."""

    def _make_service(self):
        """Create a RAGService without initialising Ollama."""
        from app.services.rag_service import RAGService
        svc          = RAGService.__new__(RAGService)
        svc.is_ready = False
        from app.core.config import get_settings
        svc._settings = get_settings()
        return svc

    def test_build_retrieval_query_no_context(self):
        svc    = self._make_service()
        result = svc._build_retrieval_query("What is DDoS?", None)
        assert result == "What is DDoS?"

    def test_build_retrieval_query_with_anomaly(self):
        svc     = self._make_service()
        anomaly = PredictionResult(
            label=PredictionLabel.ATTACK,
            probability=0.95,
            severity=SeverityLevel.CRITICAL,
            threshold=0.5,
            is_anomaly=True,
            inference_ms=2.0,
        )
        result = svc._build_retrieval_query("Explain this alert", anomaly)
        assert "anomaly" in result.lower()
        assert "0.95"    in result

    def test_format_history_empty(self):
        svc    = self._make_service()
        result = svc._format_history([])
        assert result == ""

    def test_format_history_with_messages(self):
        svc = self._make_service()
        history = [
            ChatMessage(role="user",      content="What is SSH brute force?"),
            ChatMessage(role="assistant", content="SSH brute force is..."),
        ]
        result = svc._format_history(history)
        assert "Analyst"     in result
        assert "CyberGuard"  in result
        assert "SSH brute"   in result

    def test_format_anomaly_context(self):
        svc     = self._make_service()
        anomaly = PredictionResult(
            label=PredictionLabel.ATTACK,
            probability=0.87,
            severity=SeverityLevel.HIGH,
            threshold=0.5,
            is_anomaly=True,
            inference_ms=1.5,
        )
        result = svc._format_anomaly_context(anomaly)
        assert "ANOMALY ALERT"    in result
        assert "87.0%"            in result
        assert "HIGH"             in result

    def test_format_anomaly_context_normal_ignored(self):
        svc    = self._make_service()
        normal = PredictionResult(
            label=PredictionLabel.NORMAL,
            probability=0.12,
            severity=SeverityLevel.LOW,
            threshold=0.5,
            is_anomaly=False,
            inference_ms=1.0,
        )
        result = svc._format_anomaly_context(normal)
        assert result == ""

    def test_build_prompt_contains_system(self):
        svc = self._make_service()
        prompt = svc._build_prompt(
            question="What is DDoS?",
            context="DDoS context here",
            history=[],
            prediction_context=None,
        )
        assert "CyberGuard"            in prompt
        assert "SOC"                   in prompt
        assert "DDoS context here"     in prompt
        assert "What is DDoS?"         in prompt

    def test_build_prompt_with_all_sections(self):
        svc = self._make_service()
        history = [
            ChatMessage(role="user",      content="Previous question"),
            ChatMessage(role="assistant", content="Previous answer"),
        ]
        anomaly = PredictionResult(
            label=PredictionLabel.ATTACK,
            probability=0.91,
            severity=SeverityLevel.CRITICAL,
            threshold=0.5,
            is_anomaly=True,
            inference_ms=2.0,
        )
        prompt = svc._build_prompt(
            question="What now?",
            context="Some context",
            history=history,
            prediction_context=anomaly,
        )
        assert "ANOMALY ALERT"   in prompt
        assert "Prior Conversation" in prompt
        assert "Some context"    in prompt
        assert "What now?"       in prompt


# ─── Integration Tests (require live Ollama) ─────────────────────────────────

@pytest.mark.integration
class TestRAGIntegration:
    """
    Full end-to-end RAG tests.
    Run with: pytest tests/test_rag.py -m integration -v
    Requires: ollama serve + llama3.2 + nomic-embed-text
    """

    @pytest.fixture(scope="class")
    async def rag_service(self):
        """Real RAG service with Ollama connection."""
        from app.services.rag_service import RAGService
        svc = RAGService()
        await svc.initialise()
        yield svc
        await svc.close()

    @pytest.mark.asyncio
    async def test_initialise_succeeds(self, rag_service):
        assert rag_service.is_ready is True

    @pytest.mark.asyncio
    async def test_collection_has_chunks(self, rag_service):
        stats = await rag_service.get_collection_stats()
        assert stats["total_chunks"] > 0
        assert stats["status"] == "ready"

    @pytest.mark.asyncio
    async def test_query_basic_question(self, rag_service):
        answer, sources = await rag_service.query(
            question="What is a SYN flood attack and how do I detect it?",
        )
        assert len(answer)   > 50
        assert len(sources)  > 0
        # Answer should mention SYN or TCP:
        assert any(kw in answer.lower() for kw in ["syn", "tcp", "flood", "dos"])

    @pytest.mark.asyncio
    async def test_query_with_anomaly_context(self, rag_service):
        anomaly = PredictionResult(
            label=PredictionLabel.ATTACK,
            probability=0.92,
            severity=SeverityLevel.CRITICAL,
            threshold=0.5,
            is_anomaly=True,
            inference_ms=1.5,
        )
        answer, sources = await rag_service.query(
            question="What immediate steps should I take?",
            prediction_context=anomaly,
        )
        assert len(answer) > 50
        # Should give actionable advice:
        assert any(kw in answer.lower()
                   for kw in ["isolate", "block", "contain", "investigate", "step"])

    @pytest.mark.asyncio
    async def test_query_with_history(self, rag_service):
        history = [
            ChatMessage(role="user",      content="What is port scanning?"),
            ChatMessage(role="assistant", content="Port scanning involves probing ports..."),
        ]
        answer, _ = await rag_service.query(
            question="What tools are used for this?",
            history=history,
        )
        assert len(answer) > 20

    @pytest.mark.asyncio
    async def test_query_returns_relevant_sources(self, rag_service):
        answer, sources = await rag_service.query(
            question="How do I respond to a brute force attack on SSH?"
        )
        known_docs = {
            "network_attacks.md",
            "ids_alerts_guide.md",
            "incident_response.md",
            "ml_ids_explained.md",
            "network_protocols_security.md",
            "threat_intelligence.md",
        }
        for src in sources:
            assert src in known_docs, f"Unknown source: {src}"
