"""
lstm_service.py
---------------
Thread-safe singleton service for LSTM model inference.

Design:
  - Model and scaler are loaded ONCE at startup (lifespan).
  - predict() and predict_batch() are the public API.
  - All tensor operations run inside torch.no_grad() for efficiency.
  - Returns typed PredictionResult objects directly.
"""

import pickle
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import FeatureExtractionError, ModelNotLoadedError
from app.schemas.models import (
    NetworkFlowFeatures,
    PredictionLabel,
    PredictionResult,
    SeverityLevel,
)
from app.utils.helpers import generate_id, get_label, get_severity

# ─── NSL-KDD Column / Encoding Metadata ──────────────────────────────────────
# These must exactly match what preprocess.py produced.

# Categorical feature encoding — same as pd.get_dummies output:
PROTOCOL_TYPES = ["icmp", "tcp", "udp"]
SERVICES = [
    "IRC", "X11", "Z39_50", "auth", "bgp", "courier", "csnet_ns",
    "ctf", "daytime", "discard", "domain", "domain_u", "echo",
    "eco_i", "ecr_i", "efs", "exec", "finger", "ftp", "ftp_data",
    "gopher", "harvest", "hostnames", "http", "http_2784",
    "http_443", "http_8001", "imap4", "iso_tsap", "klogin",
    "kshell", "ldap", "link", "login", "mtp", "name", "netbios_dgm",
    "netbios_ns", "netbios_ssn", "netstat", "nnsp", "nntp",
    "ntp_u", "other", "pm_dump", "pop_2", "pop_3", "printer",
    "private", "red_i", "remote_job", "rje", "shell", "smtp",
    "sql_net", "ssh", "sunrpc", "supdup", "systat", "telnet",
    "tftp_u", "tim_i", "time", "urh_i", "urp_i", "uucp",
    "uucp_path", "vmnet", "whois",
]
FLAGS = ["OTH", "REJ", "RSTO", "RSTOS0", "RSTR", "S0", "S1", "S2", "S3", "SF", "SH"]

# Ordered numeric features (same order as training DataFrame before get_dummies):
NUMERIC_FEATURES = [
    "duration", "src_bytes", "dst_bytes", "land", "wrong_fragment",
    "urgent", "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]


class LSTMService:
    """
    Singleton wrapper around the LSTM model and StandardScaler.
    Instantiated once in the FastAPI lifespan and stored in app.state.
    """

    def __init__(self) -> None:
        self._model:   Optional[object] = None   # LSTMClassifier
        self._scaler:  Optional[object] = None   # StandardScaler
        self._device:  Optional[torch.device] = None
        self._num_features: int = 0
        self._feature_names: List[str] = []
        self._loaded: bool = False

    # ── Startup / Shutdown ────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load model + scaler from disk.  Called once at app startup.
        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._loaded:
            return

        settings = get_settings()

        # ── Device ────────────────────────────────────────────────
        self._device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        logger.info(f"LSTM inference device: {self._device}")

        # ── Scaler ────────────────────────────────────────────────
        scaler_path = Path(settings.model_scaler_path)
        if not scaler_path.exists():
            raise FileNotFoundError(
                f"Scaler not found: {scaler_path}. "
                "Run: python ml/training/preprocess.py"
            )
        with open(scaler_path, "rb") as f:
            self._scaler = pickle.load(f)
        logger.info(f"Scaler loaded: {scaler_path}")

        # ── Feature names ─────────────────────────────────────────
        feat_path = Path("data/processed/feature_names.pkl")
        if feat_path.exists():
            with open(feat_path, "rb") as f:
                self._feature_names = pickle.load(f)
            self._num_features = len(self._feature_names)
        else:
            # Fallback: reconstruct from encoding lists
            self._feature_names = self._build_feature_names()
            self._num_features = len(self._feature_names)
        logger.info(f"Feature count: {self._num_features}")

        # ── Model ─────────────────────────────────────────────────
        ckpt_path = Path(settings.model_checkpoint_path)
        if not ckpt_path.exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {ckpt_path}. "
                "Run: python ml/training/train.py"
            )

        # Import here to avoid circular imports at module load:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from ml.training.model import load_model

        self._model = load_model(
            str(ckpt_path),
            self._num_features,
            self._device,
        )
        self._loaded = True
        logger.success("LSTM model loaded and ready for inference!")

    def unload(self) -> None:
        """Release model from memory on shutdown."""
        self._model  = None
        self._scaler = None
        self._loaded = False
        if self._device and self._device.type == "cuda":
            torch.cuda.empty_cache()
        logger.info("LSTM model unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_info(self) -> dict:
        """Return metadata dict for /model-info endpoint."""
        if not self._loaded or self._model is None:
            return {}
        info = self._model.get_model_info()
        settings = get_settings()
        return {
            **info,
            "device":            str(self._device),
            "checkpoint_path":   settings.model_checkpoint_path,
            "anomaly_threshold": settings.anomaly_threshold,
            "dataset":           "NSL-KDD",
        }

    # ── Feature Engineering ───────────────────────────────────────────────────

    def _build_feature_names(self) -> List[str]:
        """Reconstruct the ordered feature list matching preprocess.py output."""
        names = list(NUMERIC_FEATURES)
        names += [f"protocol_type_{p}" for p in sorted(PROTOCOL_TYPES)]
        names += [f"service_{s}"       for s in sorted(SERVICES)]
        names += [f"flag_{fl}"         for fl in sorted(FLAGS)]
        return sorted(names)

    def _features_to_vector(self, features: NetworkFlowFeatures) -> np.ndarray:
        """
        Convert a NetworkFlowFeatures Pydantic model into a numpy array
        matching the exact column order used during training.

        Returns:
            np.ndarray of shape (1, num_features), dtype float32
        """
        # Start with all numeric features:
        row: dict = {k: float(v) for k, v in features.model_dump().items()
                     if k in NUMERIC_FEATURES}

        # One-hot encode protocol_type:
        proto = features.protocol_type.lower()
        for p in PROTOCOL_TYPES:
            row[f"protocol_type_{p}"] = 1.0 if proto == p else 0.0

        # One-hot encode service:
        svc = features.service.lower()
        for s in SERVICES:
            row[f"service_{s}"] = 1.0 if svc == s else 0.0

        # One-hot encode flag:
        fl = features.flag.upper()
        for f in FLAGS:
            row[f"flag_{f}"] = 1.0 if fl == f else 0.0

        # Build ordered vector using the exact feature_names list:
        try:
            vector = np.array(
                [row.get(fname, 0.0) for fname in self._feature_names],
                dtype=np.float32,
            ).reshape(1, -1)
        except Exception as e:
            raise FeatureExtractionError(
                f"Failed to build feature vector: {e}"
            ) from e

        return vector

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(
        self,
        features: NetworkFlowFeatures,
        threshold: Optional[float] = None,
    ) -> PredictionResult:
        """
        Run single-flow inference.

        Args:
            features:  NetworkFlowFeatures pydantic model
            threshold: Decision threshold (defaults to settings value)

        Returns:
            PredictionResult with label, probability, severity, timing
        """
        if not self._loaded:
            raise ModelNotLoadedError("LSTM model is not loaded. Call load() first.")

        settings  = get_settings()
        threshold = threshold if threshold is not None else settings.anomaly_threshold

        t0 = time.perf_counter()

        # ── Feature extraction ────────────────────────────────────
        raw_vector = self._features_to_vector(features)

        # ── Scaling ───────────────────────────────────────────────
        scaled = self._scaler.transform(raw_vector).astype(np.float32)

        # ── Tensor + inference ────────────────────────────────────
        x = torch.tensor(scaled, dtype=torch.float32, device=self._device)
        x = x.unsqueeze(1)   # (1, features) → (1, 1, features)  [seq_len=1]

        with torch.no_grad():
            prob = self._model.predict_proba(x).item()

        elapsed_ms = (time.perf_counter() - t0) * 1000

        label      = get_label(prob, threshold)
        severity   = get_severity(prob)
        is_anomaly = label == PredictionLabel.ATTACK

        if is_anomaly:
            logger.warning(
                f"ANOMALY DETECTED — prob={prob:.4f} "
                f"severity={severity.value} threshold={threshold}"
            )

        return PredictionResult(
            prediction_id=generate_id(),
            label=label,
            probability=round(prob, 6),
            severity=severity,
            threshold=threshold,
            is_anomaly=is_anomaly,
            inference_ms=round(elapsed_ms, 3),
        )

    def predict_batch(
        self,
        flows: List[NetworkFlowFeatures],
        threshold: Optional[float] = None,
    ) -> List[PredictionResult]:
        """
        Run batch inference — much faster than calling predict() in a loop
        because all samples go through scaler + model in a single forward pass.

        Args:
            flows:     List of NetworkFlowFeatures
            threshold: Decision threshold

        Returns:
            List[PredictionResult] in the same order as input flows
        """
        if not self._loaded:
            raise ModelNotLoadedError("LSTM model is not loaded.")

        settings  = get_settings()
        threshold = threshold if threshold is not None else settings.anomaly_threshold

        t0 = time.perf_counter()

        # ── Stack all feature vectors ─────────────────────────────
        raw_matrix = np.vstack(
            [self._features_to_vector(f) for f in flows]
        )  # (N, num_features)

        # ── Scale ─────────────────────────────────────────────────
        scaled = self._scaler.transform(raw_matrix).astype(np.float32)

        # ── Tensor: (N, 1, features) ──────────────────────────────
        x = torch.tensor(scaled, dtype=torch.float32, device=self._device)
        x = x.unsqueeze(1)

        # ── Single forward pass ───────────────────────────────────
        with torch.no_grad():
            probs = self._model.predict_proba(x).cpu().numpy().flatten()

        total_ms = (time.perf_counter() - t0) * 1000
        per_ms   = total_ms / max(len(flows), 1)

        results: List[PredictionResult] = []
        for prob in probs:
            label      = get_label(float(prob), threshold)
            severity   = get_severity(float(prob))
            is_anomaly = label == PredictionLabel.ATTACK
            results.append(
                PredictionResult(
                    prediction_id=generate_id(),
                    label=label,
                    probability=round(float(prob), 6),
                    severity=severity,
                    threshold=threshold,
                    is_anomaly=is_anomaly,
                    inference_ms=round(per_ms, 3),
                )
            )

        anomaly_n = sum(1 for r in results if r.is_anomaly)
        logger.info(
            f"Batch inference: {len(flows)} flows | "
            f"{anomaly_n} anomalies | {total_ms:.1f} ms total"
        )
        return results


# ─── Module-level singleton ───────────────────────────────────────────────────
# This instance is shared across all requests (thread-safe for inference).
lstm_service = LSTMService()
