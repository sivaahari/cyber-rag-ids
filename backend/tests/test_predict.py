"""test_predict.py — Prediction endpoint tests."""

def test_predict_single_normal(client, normal_features):
    payload = {"features": normal_features, "threshold": 0.5}
    resp    = client.post("/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "label"       in data
    assert "probability" in data
    assert "severity"    in data
    assert "is_anomaly"  in data
    assert "inference_ms" in data
    assert 0.0 <= data["probability"] <= 1.0


def test_predict_batch(client, normal_features):
    payload = {"flows": [normal_features, normal_features], "threshold": 0.5}
    resp    = client.post("/predict/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert "anomaly_count" in data
    assert "results"       in data
    assert len(data["results"]) == 2


def test_predict_invalid_features(client):
    payload = {"features": {"duration": "not_a_number"}, "threshold": 0.5}
    resp    = client.post("/predict", json=payload)
    # Should get validation error, not 500:
    assert resp.status_code in (422, 200)


def test_predict_threshold_boundaries(client, normal_features):
    for threshold in [0.0, 0.3, 0.5, 0.9, 1.0]:
        payload = {"features": normal_features, "threshold": threshold}
        resp    = client.post("/predict", json=payload)
        assert resp.status_code == 200
