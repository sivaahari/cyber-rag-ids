"""test_health.py — Health endpoint tests."""

def test_ping(client):
    resp = client.get("/health/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status"   in data
    assert "services" in data
    assert "lstm"     in data["services"]


def test_model_info(client):
    resp = client.get("/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["architecture"] == "LSTM"
    assert data["num_features"] > 0


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "docs" in resp.json()
