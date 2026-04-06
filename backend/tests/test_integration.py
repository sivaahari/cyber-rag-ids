"""
test_integration.py
-------------------
Full end-to-end integration tests covering:
  1. Upload CSV  → batch LSTM inference → report saved
  2. Predict single → anomaly → chat with anomaly context
  3. WebSocket live-stream protocol
  4. Report CRUD lifecycle (create via upload → list → view → delete)

All tests use the mocked services from conftest.py (no Ollama needed).
Marked tests with @pytest.mark.integration require live backend.
"""

import io
import json
import csv
import time
import pytest

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.schemas.models import (
    PredictionLabel, PredictionResult, SeverityLevel
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_kdd_csv_bytes(n_rows: int = 10) -> bytes:
    """Generate a minimal NSL-KDD style CSV in memory."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Write header:
    writer.writerow([
        "duration", "protocol_type", "service", "flag",
        "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
        "hot", "num_failed_logins", "logged_in", "num_compromised",
        "root_shell", "su_attempted", "num_root", "num_file_creations",
        "num_shells", "num_access_files", "num_outbound_cmds",
        "is_host_login", "is_guest_login", "count", "srv_count",
        "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
        "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
        "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
        "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
        "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
        "dst_host_srv_serror_rate", "dst_host_rerror_rate",
        "dst_host_srv_rerror_rate", "label",
    ])

    for i in range(n_rows):
        is_attack = (i % 3 == 0)
        writer.writerow([
            0, "tcp", "http", "SF" if not is_attack else "S0",
            181 if not is_attack else 0,
            5450 if not is_attack else 0,
            0, 0, 0, 0, 0,
            1 if not is_attack else 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            8, 8,
            0.95 if is_attack else 0.0,   # serror_rate
            0.95 if is_attack else 0.0,
            0.0, 0.0,
            0.1 if is_attack else 1.0,
            0.9 if is_attack else 0.0,
            0.0, 255 if is_attack else 9,
            255 if is_attack else 9,
            0.1 if is_attack else 1.0,
            0.9 if is_attack else 0.0,
            0.0, 0.0,
            0.9 if is_attack else 0.0,
            0.9 if is_attack else 0.0,
            0.0, 0.0,
            "neptune" if is_attack else "normal",
        ])

    return buf.getvalue().encode()


# ─── CSV Upload Integration ───────────────────────────────────────────────────

class TestCSVUploadIntegration:
    """Test the full CSV upload → inference → report pipeline."""

    def test_upload_csv_success(self, client):
        """Upload a valid CSV, get batch inference results."""
        csv_bytes = _make_kdd_csv_bytes(10)
        resp = client.post(
            "/upload/csv",
            files={"file": ("test_traffic.csv", csv_bytes, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "upload_id"      in data
        assert "filename"       in data
        assert "rows_processed" in data
        assert "anomaly_count"  in data
        assert "normal_count"   in data
        assert "anomaly_rate"   in data
        assert "results"        in data
        assert "processing_ms"  in data
        assert data["filename"]     == "test_traffic.csv"
        assert data["file_type"]    == "csv"

    def test_upload_csv_wrong_extension(self, client):
        """Upload a .txt file as CSV — should be rejected."""
        resp = client.post(
            "/upload/csv",
            files={"file": ("traffic.txt", b"col1,col2\n1,2", "text/plain")},
        )
        assert resp.status_code == 415

    def test_upload_csv_empty_file(self, client):
        """Empty CSV should return an error."""
        resp = client.post(
            "/upload/csv",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp.status_code in (422, 500)

    def test_upload_generates_report(self, client, tmp_path, monkeypatch):
        """After CSV upload, a report JSON should be saved."""
        import app.api.routes.upload as upload_module

        reports: list = []

        def fake_save(report_id, filename, file_type, results, settings):
            reports.append({
                "report_id": report_id,
                "filename":  filename,
                "total":     len(results),
            })

        monkeypatch.setattr(upload_module, "_save_report", fake_save)

        csv_bytes = _make_kdd_csv_bytes(5)
        resp = client.post(
            "/upload/csv",
            files={"file": ("test.csv", csv_bytes, "text/csv")},
        )
        assert resp.status_code == 200
        assert len(reports) == 1
        assert reports[0]["filename"] == "test.csv"

    def test_upload_csv_with_header_row(self, client):
        """CSV with explicit header row should parse correctly."""
        csv_bytes = _make_kdd_csv_bytes(5)
        resp = client.post(
            "/upload/csv",
            files={"file": ("with_header.csv", csv_bytes, "text/csv")},
        )
        assert resp.status_code == 200


# ─── Predict → Chat Flow ──────────────────────────────────────────────────────

class TestPredictToChatFlow:
    """
    Test the primary user workflow:
    Predict single flow → anomaly detected → send to RAG advisor.
    """

    def test_predict_then_chat_with_context(self, client, normal_features, attack_features):
        """
        Full flow:
        1. POST /predict with attack-like features
        2. Use result as prediction_context for POST /chat
        """
        # Step 1: predict
        predict_resp = client.post(
            "/predict",
            json={"features": normal_features, "threshold": 0.5},
        )
        assert predict_resp.status_code == 200
        prediction = predict_resp.json()

        # Step 2: chat with prediction context
        chat_resp = client.post(
            "/chat",
            json={
                "question": "What does this detection mean and how should I respond?",
                "history":  [],
                "prediction_context": prediction,
            },
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert len(chat_data["answer"]) > 10
        assert "model_used" in chat_data

    def test_multi_turn_conversation(self, client):
        """Test that history is correctly passed through multiple turns."""
        history = []

        questions = [
            "What is a SYN flood attack?",
            "How do I detect it in network flows?",
            "What are the immediate containment steps?",
        ]

        for question in questions:
            resp = client.post(
                "/chat",
                json={"question": question, "history": history},
            )
            assert resp.status_code == 200
            data = resp.json()

            # Add to history for next turn:
            history.append({"role": "user",      "content": question})
            history.append({"role": "assistant", "content": data["answer"]})

        assert len(history) == 6   # 3 turns × 2 messages

    def test_batch_then_chat(self, client, normal_features):
        """Upload a batch, get summary, ask about worst anomaly."""
        # Step 1: batch predict
        batch_resp = client.post(
            "/predict/batch",
            json={
                "flows":     [normal_features] * 5,
                "threshold": 0.5,
            },
        )
        assert batch_resp.status_code == 200
        batch_data = batch_resp.json()
        assert batch_data["total"] == 5

        # Step 2: ask about the results
        chat_resp = client.post(
            "/chat",
            json={
                "question": (
                    f"I analysed {batch_data['total']} flows and found "
                    f"{batch_data['anomaly_count']} anomalies. "
                    f"What should I investigate first?"
                ),
                "history": [],
            },
        )
        assert chat_resp.status_code == 200


# ─── WebSocket Integration ────────────────────────────────────────────────────

class TestWebSocketIntegration:
    """Test the /ws/live-stream WebSocket protocol."""

    def test_websocket_connect_and_ping(self, client):
        """Connect to WS, send ping, receive pong."""
        with client.websocket_connect("/ws/live-stream") as ws:
            # Should receive welcome message immediately:
            welcome = json.loads(ws.receive_text())
            assert welcome["event"] == "connected"
            assert "lstm_ready" in welcome["payload"]

            # Send ping:
            ws.send_text(json.dumps({"type": "ping"}))
            pong = json.loads(ws.receive_text())
            assert pong["event"] == "pong"

    def test_websocket_predict_valid_flow(self, client, normal_features):
        """Send a valid flow for prediction over WebSocket."""
        with client.websocket_connect("/ws/live-stream") as ws:
            ws.receive_text()   # consume welcome

            ws.send_text(json.dumps({
                "type":     "predict",
                "features": normal_features,
            }))

            result = json.loads(ws.receive_text())
            assert result["event"] == "prediction"
            assert "label"       in result["payload"]
            assert "probability" in result["payload"]
            assert "severity"    in result["payload"]

    def test_websocket_invalid_json(self, client):
        """Send malformed JSON — should get error event."""
        with client.websocket_connect("/ws/live-stream") as ws:
            ws.receive_text()   # consume welcome
            ws.send_text("not valid json{{{")
            error = json.loads(ws.receive_text())
            assert error["event"] == "error"

    def test_websocket_unknown_type(self, client):
        """Unknown message type should return error."""
        with client.websocket_connect("/ws/live-stream") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({"type": "unknown_command"}))
            error = json.loads(ws.receive_text())
            assert error["event"] == "error"

    def test_websocket_missing_features(self, client):
        """Predict without features field → error."""
        with client.websocket_connect("/ws/live-stream") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({"type": "predict"}))
            error = json.loads(ws.receive_text())
            assert error["event"] == "error"

    def test_websocket_multiple_predictions(self, client, normal_features):
        """Send 3 flows consecutively, get 3 prediction events."""
        with client.websocket_connect("/ws/live-stream") as ws:
            ws.receive_text()   # welcome

            for _ in range(3):
                ws.send_text(json.dumps({
                    "type":     "predict",
                    "features": normal_features,
                }))

            results = [json.loads(ws.receive_text()) for _ in range(3)]
            for r in results:
                assert r["event"] == "prediction"


# ─── Report CRUD ──────────────────────────────────────────────────────────────

class TestReportCRUD:
    """Test the full report lifecycle: create → list → view → delete."""

    def test_list_reports_empty(self, client, tmp_path, monkeypatch):
        """Empty reports directory returns empty list."""
        import app.api.routes.reports as reports_module
        monkeypatch.setattr(
            reports_module, "_get_reports_dir",
            lambda: tmp_path / "reports",
        )
        resp = client.get("/reports")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_report_not_found(self, client, tmp_path, monkeypatch):
        """GET /reports/nonexistent → 404."""
        import app.api.routes.reports as reports_module
        monkeypatch.setattr(
            reports_module, "_get_reports_dir",
            lambda: tmp_path / "reports",
        )
        resp = client.get("/reports/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_report_not_found(self, client, tmp_path, monkeypatch):
        """DELETE /reports/nonexistent → 404."""
        import app.api.routes.reports as reports_module
        monkeypatch.setattr(
            reports_module, "_get_reports_dir",
            lambda: tmp_path / "reports",
        )
        resp = client.delete("/reports/nonexistent-id")
        assert resp.status_code == 404

    def test_full_report_lifecycle(self, client, tmp_path, monkeypatch):
        """Create report file manually → list → view → delete."""
        import app.api.routes.reports as reports_module
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr(
            reports_module, "_get_reports_dir",
            lambda: reports_dir,
        )

        # Create a fake report:
        rid = "test-report-abc"
        report_data = {
            "report_id":    rid,
            "filename":     "test.csv",
            "file_type":    "csv",
            "total_flows":  10,
            "anomaly_count": 3,
            "results":      [],
        }
        (reports_dir / f"{rid}.json").write_text(
            json.dumps(report_data)
        )

        # List:
        resp = client.get("/reports")
        assert resp.status_code == 200
        summaries = resp.json()
        assert len(summaries) == 1
        assert summaries[0]["report_id"] == rid

        # View:
        resp = client.get(f"/reports/{rid}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["report_id"]    == rid
        assert detail["total_flows"]  == 10
        assert detail["anomaly_count"] == 3

        # Delete:
        resp = client.delete(f"/reports/{rid}")
        assert resp.status_code == 204

        # Confirm gone:
        resp = client.get(f"/reports/{rid}")
        assert resp.status_code == 404
