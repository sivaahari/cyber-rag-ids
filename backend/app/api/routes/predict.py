"""
predict.py
----------
POST /predict        — single flow inference
POST /predict/batch  — bulk inference (up to 10,000 flows)
POST /chat           — RAG cyber advisor chat
"""

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.exceptions import ModelNotLoadedError
from app.schemas.models import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    ChatRequest,
    ChatResponse,
    PredictionRequest,
    PredictionResult,
)
from app.utils.helpers import safe_divide

router  = APIRouter(tags=["Prediction"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/predict",
    response_model=PredictionResult,
    summary="Single network flow prediction",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("60/minute")
async def predict_single(
    request: Request,
    body: PredictionRequest,
) -> PredictionResult:
    """
    Run the LSTM model on a single network flow feature vector.

    Returns prediction label (NORMAL/ATTACK), probability score,
    severity, and inference time.
    """
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError("LSTM service is not ready.")

    result = lstm_svc.predict(body.features, threshold=body.threshold)
    return result


@router.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    summary="Batch network flow prediction",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("20/minute")
async def predict_batch(
    request: Request,
    body: BatchPredictionRequest,
) -> BatchPredictionResponse:
    """
    Run LSTM on a batch of flows in a single forward pass.
    Much more efficient than calling /predict in a loop.
    Limit: 10,000 flows per request.
    """
    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError("LSTM service is not ready.")

    t0      = time.perf_counter()
    results = lstm_svc.predict_batch(body.flows, threshold=body.threshold)
    total_ms = (time.perf_counter() - t0) * 1000

    anomaly_count = sum(1 for r in results if r.is_anomaly)
    normal_count  = len(results) - anomaly_count

    # Build severity breakdown for summary:
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


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with RAG Cyber Advisor",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """
    Ask the RAG-powered cybersecurity advisor a question.
    Optionally include a PredictionResult as context so the LLM
    can provide targeted advice about the specific detected threat.
    """
    rag_svc = getattr(request.app.state, "rag_service", None)
    if not rag_svc or not getattr(rag_svc, "is_ready", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG service is not ready. "
                "Ensure Ollama is running: ollama serve"
            ),
        )

    t0 = time.perf_counter()

    answer, sources = await rag_svc.query(
        question=body.question,
        history=body.history,
        prediction_context=body.prediction_context,
    )

    response_ms = (time.perf_counter() - t0) * 1000
    settings    = get_settings()

    return ChatResponse(
        answer=answer,
        sources=sources,
        model_used=settings.ollama_llm_model,
        response_ms=round(response_ms, 2),
    )
