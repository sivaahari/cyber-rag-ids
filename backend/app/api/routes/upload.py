"""
upload.py
---------
POST /upload/csv   — upload a CSV file, run batch inference, save report
POST /upload/pcap  — upload a PCAP file, extract flows, run batch inference
"""

import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile, status
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    ModelNotLoadedError,
)
from app.schemas.models import UploadResponse
from app.services.pcap_service import parse_csv, parse_pcap
from app.utils.helpers import safe_divide

router = APIRouter(tags=["Upload"])

ALLOWED_CSV_TYPES  = {"text/csv", "application/csv", "application/octet-stream"}
ALLOWED_PCAP_TYPES = {"application/octet-stream", "application/vnd.tcpdump.pcap"}


@router.post(
    "/upload/csv",
    response_model=UploadResponse,
    summary="Upload CSV and run batch LSTM inference",
    status_code=status.HTTP_200_OK,
)
async def upload_csv(
    request: Request,
    file: UploadFile = File(..., description="NSL-KDD format CSV file"),
) -> UploadResponse:
    """
    Upload a CSV file (NSL-KDD format or compatible).
    Runs LSTM batch inference on all rows and returns results + saves report.
    """
    # ── Validate extension ────────────────────────────────────────
    if not file.filename.lower().endswith(".csv"):
        raise UnsupportedFileTypeError(
            f"Expected .csv file, got: {file.filename}"
        )

    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError("LSTM service is not ready.")

    t0 = time.perf_counter()

    # ── Read file ─────────────────────────────────────────────────
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:    # 50 MB
        raise FileTooLargeError(f"CSV exceeds 50 MB limit ({len(content)//1024//1024} MB)")

    # ── Parse → features ─────────────────────────────────────────
    flows = parse_csv(content, file.filename)

    # ── Batch inference ───────────────────────────────────────────
    settings = get_settings()
    results  = lstm_svc.predict_batch(flows, threshold=settings.anomaly_threshold)

    anomaly_count = sum(1 for r in results if r.is_anomaly)
    total_ms      = (time.perf_counter() - t0) * 1000

    # ── Save report ───────────────────────────────────────────────
    report_id = str(uuid.uuid4())
    _save_report(report_id, file.filename, "csv", results, settings)

    logger.info(
        f"CSV upload processed: {len(results)} flows, "
        f"{anomaly_count} anomalies, {total_ms:.0f} ms"
    )

    return UploadResponse(
        filename=file.filename,
        file_type="csv",
        rows_processed=len(results),
        anomaly_count=anomaly_count,
        normal_count=len(results) - anomaly_count,
        anomaly_rate=round(safe_divide(anomaly_count, len(results)), 4),
        results=results,
        report_id=report_id,
        processing_ms=round(total_ms, 2),
    )


@router.post(
    "/upload/pcap",
    response_model=UploadResponse,
    summary="Upload PCAP and run LSTM inference",
    status_code=status.HTTP_200_OK,
)
async def upload_pcap(
    request: Request,
    file: UploadFile = File(..., description="Wireshark/tcpdump .pcap file"),
) -> UploadResponse:
    """
    Upload a PCAP file. Scapy extracts per-packet features,
    then LSTM runs batch inference to flag anomalies.
    """
    if not file.filename.lower().endswith((".pcap", ".pcapng")):
        raise UnsupportedFileTypeError(
            f"Expected .pcap or .pcapng file, got: {file.filename}"
        )

    lstm_svc = getattr(request.app.state, "lstm_service", None)
    if not lstm_svc or not lstm_svc.is_loaded:
        raise ModelNotLoadedError("LSTM service is not ready.")

    t0      = time.perf_counter()
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:   # 100 MB
        raise FileTooLargeError("PCAP exceeds 100 MB limit.")

    flows   = parse_pcap(content, file.filename)
    settings = get_settings()
    results  = lstm_svc.predict_batch(flows, threshold=settings.anomaly_threshold)

    anomaly_count = sum(1 for r in results if r.is_anomaly)
    total_ms      = (time.perf_counter() - t0) * 1000

    report_id = str(uuid.uuid4())
    _save_report(report_id, file.filename, "pcap", results, settings)

    return UploadResponse(
        filename=file.filename,
        file_type="pcap",
        rows_processed=len(results),
        anomaly_count=anomaly_count,
        normal_count=len(results) - anomaly_count,
        anomaly_rate=round(safe_divide(anomaly_count, len(results)), 4),
        results=results,
        report_id=report_id,
        processing_ms=round(total_ms, 2),
    )


def _save_report(
    report_id: str,
    filename: str,
    file_type: str,
    results: list,
    settings,
) -> None:
    """Persist analysis report as JSON to the reports directory."""
    try:
        reports_dir = Path(settings.reports_path)
        reports_dir.mkdir(parents=True, exist_ok=True)

        report_path = reports_dir / f"{report_id}.json"
        report_data = {
            "report_id":     report_id,
            "filename":      filename,
            "file_type":     file_type,
            "total_flows":   len(results),
            "anomaly_count": sum(1 for r in results if r.is_anomaly),
            "results": [r.model_dump(mode="json") for r in results],
        }
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)
        logger.info(f"Report saved: {report_path}")
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
