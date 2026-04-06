"""
conftest.py — Pytest fixtures shared across all test modules.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import create_app
from app.schemas.models import (
    PredictionLabel, PredictionResult, SeverityLevel
)


def _make_mock_lstm():
    """Return a fully mocked LSTMService for testing without GPU/model files."""
    mock = MagicMock()
    mock.is_loaded = True
    mock.model_info = {
        "architecture": "LSTM", "num_features": 115,
        "hidden_size": 128, "num_layers": 2,
        "total_params": 189313, "trainable_params": 189313,
        "device": "cpu", "checkpoint_path": "mock",
        "anomaly_threshold": 0.5,
    }
    mock.predict.return_value = PredictionResult(
        label=PredictionLabel.NORMAL,
        probability=0.12,
        severity=SeverityLevel.LOW,
        threshold=0.5,
        is_anomaly=False,
        inference_ms=1.23,
    )
    mock.predict_batch.return_value = [mock.predict.return_value]
    return mock


@pytest.fixture(scope="session")
def app():
    """Create a test FastAPI app with mocked services."""
    test_app = create_app()

    mock_lstm = _make_mock_lstm()
    mock_rag  = MagicMock()
    mock_rag.is_ready = True
    mock_rag.query    = MagicMock(
        return_value=("Test answer from RAG.", ["network_attacks.md"])
    )

    test_app.state.lstm_service = mock_lstm
    test_app.state.rag_service  = mock_rag
    return test_app


@pytest.fixture(scope="session")
def client(app):
    """HTTP test client wrapping the test app."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def normal_features() -> dict:
    """Sample normal-traffic feature dict."""
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
