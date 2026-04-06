"""
predict.py
----------
POST /predict        — single flow LSTM inference
POST /predict/batch  — bulk LSTM inference (up to 10,000 flows)
POST /chat           — RAG cyber advisor (with prompt injection defence)
"""

import time
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.exceptions import ModelNotLoadedError, RAGServiceError
from app.core.security import sanitizer
from app.schemas.models import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    ChatRequest,
    ChatResponse,
    PredictionRequest,
    PredictionResult,
)
from app.utils.helpers import safe_divide

router  = APIRouter(tags=["Prediction & Chat"])
limiter = Limiter(key_func=get_remote_address)


# ─── Single Prediction ────────────────────────────────────────────────────────

@router.post(
    "/predict",
    response_model=PredictionResult,
    summary="Single network flow LSTM prediction",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("60/minute")
async def predict_single(
    request: Request,
    body: PredictionRequest,
) -> PredictionResult:
    """
    Classify a single network flow as NORMAL or ATTACK.

    Returns probability score, severity level, and inference time.
    The LSTM model was trained on NSL-KDD (125K samples, ~98.5% accuracy).
    """
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError(
            "LSTM model is not loaded. "
            "Check that lstm_ids.pt exists and server started cleanly."
        )
    return lstm_svc.predict(body.features, threshold=body.threshold)


# ─── Batch Prediction ─────────────────────────────────────────────────────────

@router.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    summary="Batch LSTM inference (up to 10,000 flows)",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("20/minute")
async def predict_batch(
    request: Request,
    body: BatchPredictionRequest,
) -> BatchPredictionResponse:
    """
    Classify a batch of flows in a single forward pass.
    Significantly more efficient than calling /predict in a loop.
    """
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError("LSTM model is not loaded.")

    t0      = time.perf_counter()
    results = lstm_svc.predict_batch(body.flows, threshold=body.threshold)
    total_ms = (time.perf_counter() - t0) * 1000

    anomaly_count = sum(1 for r in results if r.is_anomaly)
    normal_count  = len(results) - anomaly_count

    severity_counts: dict = {}
    for r in results:
        severity_counts[r.severity.value] = (
            severity_counts.get(r.severity.value, 0) + 1
        )

    return BatchPredictionResponse(
        total=len(results),
        anomaly_count=anomaly_count,
        normal_count=normal_count,
        results=results,
        processing_ms=round(total_ms, 2),
        summary={
            "anomaly_rate": round(safe_divide(anomaly_count, len(results)), 4),
            "severity_breakdown": severity_counts,
            "avg_probability": round(
                sum(r.probability for r in results) / max(len(results), 1), 4
            ),
        },
    )


# ─── RAG Chat ─────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with RAG cybersecurity advisor",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """
    Ask the RAG-powered cybersecurity advisor a question.

    Security:
      - Question is sanitized against prompt injection attacks
      - Conversation history is also sanitized
      - Rate limited to 30 requests/minute per IP

    Optionally attach a PredictionResult as `prediction_context` so
    the LLM provides targeted advice about a specific detected threat.
    """
    rag_svc = getattr(request.app.state, "rag_service", None)

    if rag_svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
            "error": "rag_unavailable",
            "message": "RAG service is not ready.",
            "hint": "Ensure Ollama is running: ollama serve",
            },
        )

    # ── Input sanitization (prompt injection defence) ─────────────
    try:
        clean_question = sanitizer.sanitize(body.question)
        clean_history  = sanitizer.sanitize_history(body.history)
    except ValueError as e:
        logger.warning(f"Sanitization rejected input: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error":   "invalid_input",
                "message": str(e),
            },
        )

    t0 = time.perf_counter()

    try:
        answer, sources = await rag_svc.query(
            question=clean_question,
            history=clean_history,
            prediction_context=body.prediction_context,
        )
    except RAGServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "rag_query_failed", "message": str(e)},
        )

    response_ms = (time.perf_counter() - t0) * 1000
    settings    = get_settings()

    logger.info(
        f"Chat: question_len={len(clean_question)} "
        f"sources={sources} "
        f"response_ms={response_ms:.0f}"
    )

    return ChatResponse(
        answer=answer,
        sources=sources,
        model_used=settings.ollama_llm_model,
        response_ms=round(response_ms, 2),
    )
