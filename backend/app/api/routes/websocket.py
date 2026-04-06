"""
websocket.py
------------
WS /ws/live-stream

Real-time anomaly stream:
  Client connects → sends JSON rows one at a time →
  Server runs LSTM inference immediately →
  Broadcasts result back as JSON.

Message formats:
  Client → Server:
    { "type": "predict", "features": { ...NetworkFlowFeatures... } }
    { "type": "ping" }

  Server → Client:
    { "event": "prediction", "payload": { ...PredictionResult... } }
    { "event": "error",      "payload": { "message": "..." } }
    { "event": "pong",       "payload": {} }
    { "event": "summary",    "payload": { "total": N, "anomalies": M } }
"""

import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.schemas.models import NetworkFlowFeatures, WSMessage

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/live-stream")
async def live_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time packet-by-packet anomaly detection.
    Maintains a session counter and sends a summary on disconnect.
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"WebSocket connected: client={client_id}")

    lstm_svc = getattr(websocket.app.state, "lstm_service", None)

    total_received = 0
    total_anomaly  = 0

    # Send welcome message:
    await _send(websocket, "connected", {
        "message":    "Live anomaly stream ready",
        "lstm_ready": lstm_svc.is_loaded if lstm_svc else False,
        "timestamp":  datetime.utcnow().isoformat(),
    })

    try:
        while True:
            # ── Receive message from client ───────────────────────
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, "error", {"message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── Ping / Pong ───────────────────────────────────────
            if msg_type == "ping":
                await _send(websocket, "pong", {})
                continue

            # ── Predict ───────────────────────────────────────────
            if msg_type == "predict":
                if not lstm_svc or not lstm_svc.is_loaded:
                    await _send(websocket, "error", {
                        "message": "LSTM model is not loaded"
                    })
                    continue

                features_dict = msg.get("features", {})
                try:
                    features = NetworkFlowFeatures(**features_dict)
                except Exception as e:
                    await _send(websocket, "error", {
                        "message": f"Invalid features: {e}"
                    })
                    continue

                # Run inference:
                try:
                    result = lstm_svc.predict(features)
                    total_received += 1
                    if result.is_anomaly:
                        total_anomaly += 1

                    await _send(websocket, "prediction", result.model_dump(mode="json"))

                except Exception as e:
                    logger.error(f"WebSocket inference error: {e}")
                    await _send(websocket, "error", {
                        "message": f"Inference failed: {str(e)}"
                    })
                continue

            # ── Unknown type ──────────────────────────────────────
            await _send(websocket, "error", {
                "message": f"Unknown message type: '{msg_type}'. "
                           "Use 'predict' or 'ping'."
            })

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected: client={client_id} "
            f"total={total_received} anomalies={total_anomaly}"
        )
    except Exception as e:
        logger.error(f"WebSocket error: client={client_id} error={e}")
        try:
            await _send(websocket, "error", {"message": str(e)})
            await websocket.close()
        except Exception:
            pass


async def _send(websocket: WebSocket, event: str, payload: dict) -> None:
    """Helper to send a structured WSMessage over the websocket."""
    msg = WSMessage(event=event, payload=payload)
    await websocket.send_text(msg.model_dump_json())
