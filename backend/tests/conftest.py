"""
conftest.py — Pytest fixtures shared across all test modules.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import create_app
from app.schemas.models import (
    PredictionLabel,
    PredictionResult,
    SeverityLevel,
)


def _make_mock_lstm():
    """Fully mocked LSTMService — no GPU / model files needed."""
    mock          = MagicMock()
    mock.is_loaded = True
    mock.model_info = {
        "architecture":     "LSTM",
        "num_features":     115,
        "hidden_size":      128,
        "num_layers":       2,
        "total_params":     189313,
        "trainable_params": 189313,
        "device":           "cpu",
        "checkpoint_path":  "mock",
        "anomaly_threshold": 0.5,
    }
    normal_result = PredictionResult(
        label=PredictionLabel.NORMAL,
        probability=0.12,
        severity=SeverityLevel.LOW,
        threshold=0.5,
        is_anomaly=False,
        inference_ms=1.23,
    )
    mock.predict.return_value       = normal_result
    mock.predict_batch.return_value = [normal_result]
    return mock


def _make_mock_rag():
    """Fully mocked RAGService with async query method."""
    mock          = MagicMock()
    mock.is_ready = True

    # query() is async in the real service:
    mock.query = AsyncMock(
        return_value=(
            "## SYN Flood Attack\n\n"
            "A SYN flood is a DoS attack where the attacker sends many TCP SYN "
            "packets to exhaust the server's connection table.\n\n"
            "**Immediate Actions:**\n"
            "1. Enable SYN cookies on your firewall\n"
            "2. Rate-limit SYN packets per source IP\n"
            "3. Contact upstream ISP for BGP blackhole if volumetric\n\n"
            "[Source: network_attacks.md]",
            ["network_attacks.md", "ids_alerts_guide.md"],
        )
    )

    mock.get_collection_stats = AsyncMock(
        return_value={
            "status":          "ready",
            "collection_name": "cyber_knowledge",
            "total_chunks":    87,
            "embed_model":     "nomic-embed-text",
            "llm_model":       "llama3.2",
            "kb_path":         "./rag/knowledge_base",
            "db_path":         "./rag/chroma_db",
        }
    )
    return mock


@pytest.fixture(scope="session")
def app():
    """Create test FastAPI app with all services mocked."""
    test_app = create_app()
    test_app.state.lstm_service = _make_mock_lstm()
    test_app.state.rag_service  = _make_mock_rag()
    return test_app


@pytest.fixture(scope="session")
def client(app):
    """Synchronous test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def normal_features() -> dict:
    """NSL-KDD normal-traffic feature dict."""
    return {
        "duration": 0, "protocol_type": "tcp", "service": "http",
        "flag": "SF", "src_bytes": 181, "dst_bytes": 5450,
        "land": 0, "wrong_fragment": 0, "urgent": 0,
        "hot": 0, "num_failed_logins": 0, "logged_in": 1,
        "num_compromised": 0, "root_shell": 0, "num_root": 0,
        "num_file_creations": 0, "num_shells": 0,
        "num_access_files": 0, "is_guest_login": 0,
        "count": 8, "srv_count": 8,
        "serror_rate": 0.0, "srv_serror_rate": 0.0,
        "rerror_rate": 0.0, "srv_rerror_rate": 0.0,
        "same_srv_rate": 1.0, "diff_srv_rate": 0.0,
        "srv_diff_host_rate": 0.0,
        "dst_host_count": 9, "dst_host_srv_count": 9,
        "dst_host_same_srv_rate": 1.0, "dst_host_diff_srv_rate": 0.0,
        "dst_host_same_src_port_rate": 0.11,
        "dst_host_srv_diff_host_rate": 0.0,
        "dst_host_serror_rate": 0.0, "dst_host_srv_serror_rate": 0.0,
        "dst_host_rerror_rate": 0.0, "dst_host_srv_rerror_rate": 0.0,
    }


@pytest.fixture
def attack_features(normal_features) -> dict:
    """NSL-KDD attack-like feature dict (SYN flood indicators)."""
    return {
        **normal_features,
        "serror_rate":          0.95,
        "dst_host_serror_rate": 0.90,
        "flag":                 "S0",
        "count":                500.0,
        "srv_count":            500.0,
        "logged_in":            0,
        "src_bytes":            0.0,
        "dst_bytes":            0.0,
    }
