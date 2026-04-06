"""
models.py
---------
All Pydantic v2 request / response schemas used across the API.
Every schema has full type annotations, field descriptions, and examples.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class PredictionLabel(str, Enum):
    NORMAL = "NORMAL"
    ATTACK = "ATTACK"


class SeverityLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ProtocolType(str, Enum):
    TCP  = "tcp"
    UDP  = "udp"
    ICMP = "icmp"


# ─── Single Prediction ────────────────────────────────────────────────────────

class NetworkFlowFeatures(BaseModel):
    """
    Raw network flow feature vector matching NSL-KDD schema.
    Frontend sends these values after manual entry or CSV row parsing.
    Not all features are required — missing ones default to 0.
    """
    duration:             float = Field(0.0,  ge=0,  description="Flow duration in seconds")
    protocol_type:        str   = Field("tcp",        description="Protocol: tcp/udp/icmp")
    service:              str   = Field("http",       description="Network service")
    flag:                 str   = Field("SF",         description="TCP flag combination")
    src_bytes:            float = Field(0.0,  ge=0,  description="Bytes sent source→dest")
    dst_bytes:            float = Field(0.0,  ge=0,  description="Bytes sent dest→source")
    land:                 int   = Field(0, ge=0, le=1)
    wrong_fragment:       float = Field(0.0,  ge=0)
    urgent:               float = Field(0.0,  ge=0)
    hot:                  float = Field(0.0,  ge=0)
    num_failed_logins:    float = Field(0.0,  ge=0)
    logged_in:            int   = Field(0, ge=0, le=1)
    num_compromised:      float = Field(0.0,  ge=0)
    root_shell:           float = Field(0.0,  ge=0)
    num_root:             float = Field(0.0,  ge=0)
    num_file_creations:   float = Field(0.0,  ge=0)
    num_shells:           float = Field(0.0,  ge=0)
    num_access_files:     float = Field(0.0,  ge=0)
    is_guest_login:       int   = Field(0, ge=0, le=1)
    count:                float = Field(0.0,  ge=0)
    srv_count:            float = Field(0.0,  ge=0)
    serror_rate:          float = Field(0.0,  ge=0, le=1)
    srv_serror_rate:      float = Field(0.0,  ge=0, le=1)
    rerror_rate:          float = Field(0.0,  ge=0, le=1)
    srv_rerror_rate:      float = Field(0.0,  ge=0, le=1)
    same_srv_rate:        float = Field(0.0,  ge=0, le=1)
    diff_srv_rate:        float = Field(0.0,  ge=0, le=1)
    srv_diff_host_rate:   float = Field(0.0,  ge=0, le=1)
    dst_host_count:       float = Field(0.0,  ge=0)
    dst_host_srv_count:   float = Field(0.0,  ge=0)
    dst_host_same_srv_rate:      float = Field(0.0, ge=0, le=1)
    dst_host_diff_srv_rate:      float = Field(0.0, ge=0, le=1)
    dst_host_same_src_port_rate: float = Field(0.0, ge=0, le=1)
    dst_host_srv_diff_host_rate: float = Field(0.0, ge=0, le=1)
    dst_host_serror_rate:        float = Field(0.0, ge=0, le=1)
    dst_host_srv_serror_rate:    float = Field(0.0, ge=0, le=1)
    dst_host_rerror_rate:        float = Field(0.0, ge=0, le=1)
    dst_host_srv_rerror_rate:    float = Field(0.0, ge=0, le=1)

    model_config = {
        "json_schema_extra": {
            "example": {
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
        }
    }


class PredictionRequest(BaseModel):
    """Single-flow prediction request."""
    features:  NetworkFlowFeatures
    threshold: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Decision threshold — lower = more sensitive to attacks"
    )


class PredictionResult(BaseModel):
    """Result of a single flow prediction."""
    prediction_id: str           = Field(default_factory=lambda: str(uuid.uuid4()))
    label:         PredictionLabel
    probability:   float         = Field(ge=0.0, le=1.0)
    severity:      SeverityLevel
    threshold:     float
    is_anomaly:    bool
    timestamp:     datetime      = Field(default_factory=datetime.utcnow)
    inference_ms:  float         = Field(description="Inference time in milliseconds")

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ─── Batch Prediction ─────────────────────────────────────────────────────────

class BatchPredictionRequest(BaseModel):
    """Batch prediction for multiple flows at once."""
    flows:     List[NetworkFlowFeatures] = Field(min_length=1, max_length=10_000)
    threshold: float = Field(0.5, ge=0.0, le=1.0)


class BatchPredictionResponse(BaseModel):
    """Response for batch prediction."""
    total:        int
    anomaly_count: int
    normal_count:  int
    results:       List[PredictionResult]
    processing_ms: float
    summary: Dict[str, Any] = Field(default_factory=dict)


# ─── Upload ───────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after CSV or PCAP upload + batch prediction."""
    upload_id:     str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename:      str
    file_type:     str
    rows_processed: int
    anomaly_count:  int
    normal_count:   int
    anomaly_rate:   float
    results:        List[PredictionResult]
    report_id:      Optional[str] = None
    processing_ms:  float
    timestamp:      datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ─── RAG / Chat ───────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the RAG chat."""
    role:    str = Field(description="'user' or 'assistant'")
    content: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"user", "assistant", "system"}:
            raise ValueError("role must be 'user', 'assistant', or 'system'")
        return v


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    question:         str               = Field(min_length=1, max_length=4000)
    history:          List[ChatMessage] = Field(default_factory=list, max_length=20)
    prediction_context: Optional[PredictionResult] = Field(
        None,
        description="Optional anomaly result to include as context for the advisor"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What does a high serror_rate indicate and how should I respond?",
                "history":  [],
            }
        }
    }


class ChatResponse(BaseModel):
    """Response from the RAG advisor."""
    answer:       str
    sources:      List[str] = Field(default_factory=list)
    model_used:   str
    response_ms:  float
    timestamp:    datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ─── Health ───────────────────────────────────────────────────────────────────

class ServiceStatus(str, Enum):
    OK          = "ok"
    DEGRADED    = "degraded"
    UNAVAILABLE = "unavailable"


class HealthResponse(BaseModel):
    """Full health check response."""
    status:       ServiceStatus
    app_name:     str
    version:      str
    timestamp:    datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(
        description="Status of each sub-service (lstm, rag, ollama)"
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ─── Model Info ───────────────────────────────────────────────────────────────

class ModelInfoResponse(BaseModel):
    """LSTM model metadata."""
    architecture:     str
    num_features:     int
    hidden_size:      int
    num_layers:       int
    total_params:     int
    trainable_params: int
    checkpoint_path:  str
    device:           str
    anomaly_threshold: float
    dataset:          str = "NSL-KDD"


# ─── Report ───────────────────────────────────────────────────────────────────

class ReportSummary(BaseModel):
    """Metadata for a saved analysis report."""
    report_id:    str
    filename:     str
    created_at:   datetime
    total_flows:  int
    anomaly_count: int
    anomaly_rate:  float

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ─── WebSocket ────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    """Message format pushed over the live-stream WebSocket."""
    event:   str   = Field(description="'prediction', 'error', 'ping', 'summary'")
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
