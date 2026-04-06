"""
config.py
---------
Centralised application settings loaded from .env via Pydantic BaseSettings.
All environment variables are typed, validated, and documented here.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.  Values are read from .env (backend/.env).
    lru_cache ensures we parse the file only once per process lifetime.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────
    app_name:    str = Field("CyberRAG-IDS", description="Application display name")
    app_version: str = Field("1.0.0")
    debug:       bool = Field(False)
    log_level:   str = Field("INFO")

    # ── Server ────────────────────────────────────────────────────
    host: str = Field("0.0.0.0")
    port: int = Field(8000)
    allowed_origins: str = Field("http://localhost:3000,http://127.0.0.1:3000")

    @property
    def origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # ── Ollama ────────────────────────────────────────────────────
    ollama_base_url:   str = Field("http://localhost:11434")
    ollama_llm_model:  str = Field("mistral-nemo")
    ollama_embed_model: str = Field("nomic-embed-text")

    # ── RAG / ChromaDB ────────────────────────────────────────────
    chroma_db_path:      str = Field("./rag/chroma_db")
    knowledge_base_path: str = Field("./rag/knowledge_base")
    rag_chunk_size:      int = Field(1000)
    rag_chunk_overlap:   int = Field(200)
    rag_top_k:           int = Field(5)

    # ── ML / LSTM ─────────────────────────────────────────────────
    model_checkpoint_path: str = Field("./ml/checkpoints/lstm_ids.pt")
    model_scaler_path:     str = Field("./ml/checkpoints/scaler.pkl")
    anomaly_threshold:     float = Field(0.5, ge=0.0, le=1.0)

    # ── Rate Limiting ─────────────────────────────────────────────
    rate_limit_per_minute: int = Field(60)

    # ── Reports ───────────────────────────────────────────────────
    reports_path: str = Field("./reports")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper   = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.
    Call get_settings() anywhere in the app — it reads .env only once.
    """
    return Settings()
