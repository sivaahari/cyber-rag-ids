"""
health.py
---------
GET /health         — full health check (LSTM + RAG + Ollama)
GET /health/ping    — lightweight liveness probe
GET /model-info     — LSTM model metadata
"""

import httpx
from fastapi import APIRouter, Request
from loguru import logger

from app.core.config import get_settings
from app.schemas.models import (
    HealthResponse,
    ModelInfoResponse,
    ServiceStatus,
)

router = APIRouter(tags=["Health"])


@router.get("/health/ping", summary="Liveness probe")
async def ping() -> dict:
    """Lightest possible check — just confirms the process is alive."""
    return {"status": "ok", "message": "pong"}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Full health check",
)
async def health_check(request: Request) -> HealthResponse:
    """
    Check status of every subsystem:
      - LSTM model (loaded in app.state)
      - Ollama LLM endpoint (HTTP GET to /api/tags)
      - RAG service (loaded in app.state)
    """
    settings = get_settings()
    services: dict[str, str] = {}

    # ── LSTM ──────────────────────────────────────────────────────
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if lstm_svc and lstm_svc.is_loaded:
        services["lstm"] = "ok"
    else:
        services["lstm"] = "unavailable"
        logger.warning("Health check: LSTM not loaded")

    # ── Ollama ────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        if resp.status_code == 200:
            services["ollama"] = "ok"
        else:
            services["ollama"] = f"degraded (HTTP {resp.status_code})"
    except Exception as e:
        services["ollama"] = f"unavailable ({type(e).__name__})"
        logger.warning(f"Health check: Ollama unreachable — {e}")

    # ── RAG ───────────────────────────────────────────────────────
    rag_svc = getattr(request.app.state, "rag_service", None)
    if rag_svc and getattr(rag_svc, "is_ready", False):
        services["rag"] = "ok"
    else:
        services["rag"] = "unavailable"

    # ── Overall status ────────────────────────────────────────────
    all_ok     = all(v == "ok" for v in services.values())
    any_ok     = any(v == "ok" for v in services.values())
    overall    = (
        ServiceStatus.OK       if all_ok  else
        ServiceStatus.DEGRADED if any_ok  else
        ServiceStatus.UNAVAILABLE
    )

    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        version=settings.app_version,
        services=services,
    )


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="LSTM model metadata",
)
async def model_info(request: Request) -> ModelInfoResponse:
    """Return architecture details, parameter count, and threshold."""
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        return ModelInfoResponse(
            architecture="LSTM",
            num_features=0,
            hidden_size=128,
            num_layers=2,
            total_params=0,
            trainable_params=0,
            checkpoint_path="not loaded",
            device="cpu",
            anomaly_threshold=get_settings().anomaly_threshold,
        )

    info = lstm_svc.model_info
    return ModelInfoResponse(
        architecture=info.get("architecture", "LSTM"),
        num_features=info.get("num_features", 0),
        hidden_size=info.get("hidden_size", 128),
        num_layers=info.get("num_layers", 2),
        total_params=info.get("total_params", 0),
        trainable_params=info.get("trainable_params", 0),
        checkpoint_path=info.get("checkpoint_path", ""),
        device=info.get("device", "cpu"),
        anomaly_threshold=info.get("anomaly_threshold", 0.5),
    )
