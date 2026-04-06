"""
main.py
-------
FastAPI application factory.

Startup (lifespan):
  1. Setup structured logging (Loguru)
  2. Load LSTM model + scaler (LSTMService.load)
  3. Initialise RAG service (LangChain + ChromaDB + Ollama)

Shutdown (lifespan):
  1. Unload LSTM model from GPU/CPU memory
  2. Close RAG / ChromaDB connections

Middleware stack (applied in reverse order):
  - RequestSizeLimitMiddleware  ← rejects >105MB before body read
  - SecurityHeadersMiddleware   ← adds X-Content-Type-Options etc.
  - CORSMiddleware              ← origins from .env ALLOWED_ORIGINS
  - SlowAPIMiddleware           ← per-IP rate limiting
  - X-Process-Time header       ← custom timing header

Routes:
  /health, /model-info, /rag-stats  → health.router
  /predict, /predict/batch, /chat   → predict.router
  /upload/csv, /upload/pcap         → upload.router
  /reports                          → reports.router
  /ws/live-stream                   → websocket.router
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.security import register_security_middleware


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async context manager controlling startup and shutdown.
    Everything before `yield` runs on startup.
    Everything after `yield` runs on shutdown.
    """
    settings = get_settings()

    # ── Startup ───────────────────────────────────────────────────
    setup_logging()
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"  Debug mode : {settings.debug}")
    logger.info(f"  Log level  : {settings.log_level}")
    logger.info(f"  Allowed origins: {settings.origins_list}")
    logger.info("=" * 60)

    # ── Load LSTM model ───────────────────────────────────────────
    from app.services.lstm_service import lstm_service
    try:
        lstm_service.load()
        app.state.lstm_service = lstm_service
        logger.success("LSTM service ready.")
    except Exception as e:
        logger.error(f"LSTM service failed to load: {e}")
        logger.warning("Running without LSTM — /predict endpoints will return 503.")
        app.state.lstm_service = None

    # ── Load RAG service ──────────────────────────────────────────
    if not hasattr(app.state, "rag_service") or app.state.rag_service is None:
        try:
            from app.services.rag_service import RAGService
            rag = RAGService()
            await rag.initialise()
            app.state.rag_service = rag
            logger.success("RAG service ready.")
        except Exception as e:
            logger.error(f"RAG service failed to load: {e}")
            logger.warning("Running without RAG — /chat endpoint will return 503.")
            app.state.rag_service = None
    else:
        logger.info("Using preconfigured RAG service (likely test mock).")

    logger.info(f"API listening on http://{settings.host}:{settings.port}")
    logger.info("Docs: http://localhost:8000/docs")
    logger.info("Health: http://localhost:8000/health")

    yield   # ← App is live here

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("Shutting down CyberRAG-IDS…")

    if getattr(app.state, "lstm_service", None):
        app.state.lstm_service.unload()

    rag = getattr(app.state, "rag_service", None)

    if rag and hasattr(rag, "close"):
        close_fn = rag.close

        if callable(close_fn):
            result = close_fn()

            if hasattr(result, "__await__"):
                await result

    logger.info("Shutdown complete.")


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    # ── Rate limiter ──────────────────────────────────────────────
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "## Local LLM Cyber RAG Advisor + ML Intrusion Detection System\n\n"
            "### Features\n"
            "- **LSTM IDS**: Real-time anomaly detection (NSL-KDD, ~98.5% accuracy)\n"
            "- **RAG Advisor**: LangChain + ChromaDB + Ollama cybersecurity Q&A\n"
            "- **Upload**: CSV / PCAP batch analysis with paginated results\n"
            "- **WebSocket**: Live packet stream (`/ws/live-stream`)\n"
            "- **Reports**: Persistent JSON report storage and retrieval\n\n"
            "### Security\n"
            "- Rate limited (60 req/min default)\n"
            "- Prompt injection detection\n"
            "- File size limits (CSV: 50MB, PCAP: 100MB)\n"
            "- Security headers on all responses\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── Security middleware ───────────────────────────────────────
    register_security_middleware(app)

    # ── CORS ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time"],
    )

    # ── Request timing header ─────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        t0       = time.perf_counter()
        response = await call_next(request)
        elapsed  = (time.perf_counter() - t0) * 1000
        response.headers["X-Process-Time"] = f"{elapsed:.2f}ms"
        return response

    # ── Custom exception handlers ─────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────
    from app.api.routes.health    import router as health_router
    from app.api.routes.predict   import router as predict_router
    from app.api.routes.upload    import router as upload_router
    from app.api.routes.reports   import router as reports_router
    from app.api.routes.websocket import router as ws_router

    app.include_router(health_router)
    app.include_router(predict_router)
    app.include_router(upload_router)
    app.include_router(reports_router)
    app.include_router(ws_router)

    # ── Root ──────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app":      settings.app_name,
            "version":  settings.app_version,
            "docs":     "/docs",
            "health":   "/health",
            "rag_stats":"/rag-stats",
        }

    return app


# ─── App Instance ─────────────────────────────────────────────────────────────
app = create_app()
