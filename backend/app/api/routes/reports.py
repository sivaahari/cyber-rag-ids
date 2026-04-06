"""
reports.py
----------
GET  /reports          — list all saved reports
GET  /reports/{id}     — get a single report by ID
DELETE /reports/{id}   — delete a report
"""

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.core.config import get_settings
from app.schemas.models import ReportSummary

router = APIRouter(tags=["Reports"])


def _get_reports_dir() -> Path:
    return Path(get_settings().reports_path)


@router.get(
    "/reports",
    response_model=List[ReportSummary],
    summary="List all analysis reports",
)
async def list_reports() -> List[ReportSummary]:
    """Return metadata for all saved analysis reports, newest first."""
    reports_dir = _get_reports_dir()
    if not reports_dir.exists():
        return []

    summaries: List[ReportSummary] = []
    for json_file in sorted(reports_dir.glob("*.json"), reverse=True):
        try:
            with open(json_file) as f:
                data = json.load(f)
            summaries.append(
                ReportSummary(
                    report_id=data["report_id"],
                    filename=data["filename"],
                    created_at=json_file.stat().st_mtime,
                    total_flows=data["total_flows"],
                    anomaly_count=data["anomaly_count"],
                    anomaly_rate=round(
                        data["anomaly_count"] / max(data["total_flows"], 1), 4
                    ),
                )
            )
        except Exception as e:
            logger.warning(f"Could not parse report {json_file.name}: {e}")

    return summaries


@router.get(
    "/reports/{report_id}",
    summary="Get full report by ID",
)
async def get_report(report_id: str) -> dict:
    """Return the full JSON report including all prediction results."""
    report_path = _get_reports_dir() / f"{report_id}.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )
    with open(report_path) as f:
        return json.load(f)


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report",
)
async def delete_report(report_id: str) -> None:
    """Permanently delete a report file."""
    report_path = _get_reports_dir() / f"{report_id}.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )
    report_path.unlink()
    logger.info(f"Report deleted: {report_id}")
